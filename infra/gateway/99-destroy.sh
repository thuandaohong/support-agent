#!/usr/bin/env bash
# XOÁ HẲN mọi thứ của infra/gateway: target → Gateway → Lambda → log group → 2 role.
# Không hoàn tác được → bắt gõ lại tên Gateway để xác nhận. DynamoDB, Runtime KHÔNG bị đụng tới.
# Thứ tự ngược lúc tạo: Gateway còn target thì không xoá được; role xoá sau cùng.
# TRƯỚC KHI XOÁ: Runtime đang ORDER_BACKEND=gateway thì chuyển về direct trước
#   (infra/runtime/runtime.env → 01-create-role.sh → 05-update-image.sh), không thì khách nhận "đang bận".
source "$(dirname "$0")/_env.sh"

read -r -p "Gõ '$GATEWAY_NAME' để xoá Gateway + Lambda $LAMBDA_NAME + role $GATEWAY_ROLE, $LAMBDA_ROLE: " ans
[[ "$ans" == "$GATEWAY_NAME" ]] || { echo "Huỷ."; exit 1; }

GW="$(gateway_id)"
if [[ -n "$GW" ]]; then
  TID="$(target_id "$GW")"
  if [[ -n "$TID" ]]; then
    aws bedrock-agentcore-control delete-gateway-target --gateway-identifier "$GW" --target-id "$TID" >/dev/null
    echo "Đã yêu cầu xoá target $TARGET_NAME ($TID)"
    # Xoá target là bất đồng bộ — đợi biến mất rồi mới xoá được Gateway
    for _ in $(seq 1 30); do [[ -z "$(target_id "$GW")" ]] && break; sleep 5; done
  fi
  aws bedrock-agentcore-control delete-gateway --gateway-identifier "$GW" >/dev/null
  echo "Đã yêu cầu xoá Gateway $GW"
fi

if aws lambda get-function --function-name "$LAMBDA_NAME" >/dev/null 2>&1; then
  aws lambda delete-function --function-name "$LAMBDA_NAME"
  echo "Đã xoá Lambda $LAMBDA_NAME"
fi
LOG_GROUP="/aws/lambda/$LAMBDA_NAME"
if [[ "$(aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" \
        --query "logGroups[?logGroupName=='$LOG_GROUP'] | length(@)" --output text)" == 1 ]]; then
  aws logs delete-log-group --log-group-name "$LOG_GROUP"
  echo "Đã xoá log group $LOG_GROUP"
fi

for role in "$GATEWAY_ROLE" "$LAMBDA_ROLE"; do
  if aws iam get-role --role-name "$role" >/dev/null 2>&1; then
    aws iam delete-role-policy --role-name "$role" --policy-name "${role}-perms" || true
    aws iam delete-role --role-name "$role"
    echo "Đã xoá role $role"
  fi
done
