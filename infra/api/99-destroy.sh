#!/usr/bin/env bash
# XOÁ HẲN web API của infra/api: HTTP API (kéo theo route, integration, authorizer, stage) →
# quyền gọi Lambda → Bridge Lambda → role → 2 log group. Không hoàn tác được → bắt gõ lại tên API.
# Runtime, Gateway, Cognito KHÔNG bị đụng tới. frontend/.env.local giữ nguyên (xoá tay nếu muốn).
source "$(dirname "$0")/_env.sh"

read -r -p "Gõ '$API_NAME' để xoá HTTP API + Lambda $BRIDGE_NAME + role $BRIDGE_ROLE + log: " ans
[[ "$ans" == "$API_NAME" ]] || { echo "Huỷ."; exit 1; }

API="$(api_id)"
if [[ -n "$API" ]]; then
  aws apigatewayv2 delete-api --api-id "$API"
  echo "Đã xoá HTTP API $API_NAME"
fi

if aws lambda get-function --function-name "$BRIDGE_NAME" >/dev/null 2>&1; then
  aws lambda delete-function --function-name "$BRIDGE_NAME"
  echo "Đã xoá Lambda $BRIDGE_NAME"
fi

if aws iam get-role --role-name "$BRIDGE_ROLE" >/dev/null 2>&1; then
  aws iam delete-role-policy --role-name "$BRIDGE_ROLE" --policy-name "${BRIDGE_ROLE}-perms" || true
  aws iam delete-role --role-name "$BRIDGE_ROLE"
  echo "Đã xoá role $BRIDGE_ROLE"
fi

for lg in "/aws/lambda/$BRIDGE_NAME" "/aws/apigateway/$API_NAME"; do
  aws logs delete-log-group --log-group-name "$lg" 2>/dev/null && echo "Đã xoá log group $lg" || true
done
