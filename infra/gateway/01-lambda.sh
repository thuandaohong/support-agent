#!/usr/bin/env bash
# Bước 2 (Day 60): role riêng + Lambda chứa tool get_order (lambdas/get_order/handler.py).
#   role     → CHỈ GetItem trên bảng đơn + ghi log của chính hàm này
#   log group tạo TRƯỚC với retention → role không cần logs:CreateLogGroup
# Chạy lại được: role cập nhật policy; hàm đã có thì cập nhật code + cấu hình.
source "$(dirname "$0")/_env.sh"

TRUST="$HERE/lambda-trust-policy.json"
PERMS="$(render "$HERE/lambda-permissions-policy.json.tpl")"
python3 -m json.tool "$TRUST" >/dev/null && python3 -m json.tool "$PERMS" >/dev/null
ensure_role "$LAMBDA_ROLE" "$TRUST" "$PERMS" "Lambda $LAMBDA_NAME (tool get_order sau AgentCore Gateway)"
ROLE_ARN="$(aws iam get-role --role-name "$LAMBDA_ROLE" --query Role.Arn --output text)"

LOG_GROUP="/aws/lambda/$LAMBDA_NAME"
if [[ -z "$(aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" \
            --query "logGroups[?logGroupName=='$LOG_GROUP'].logGroupName" --output text)" ]]; then
  aws logs create-log-group --log-group-name "$LOG_GROUP" --tags project=support-agent
fi
aws logs put-retention-policy --log-group-name "$LOG_GROUP" --retention-in-days "${LOG_RETENTION_DAYS:-14}"
echo "Log group $LOG_GROUP giữ ${LOG_RETENTION_DAYS:-14} ngày"

# Gói chỉ handler.py (boto3 có sẵn trong runtime Lambda). -X: bỏ metadata → zip giống nhau mỗi lần build
ZIP="$TMP_DIR/get_order.zip"
(cd "$REPO/lambdas/get_order" && zip -qX "$ZIP" handler.py)

if aws lambda get-function --function-name "$LAMBDA_NAME" >/dev/null 2>&1; then
  echo "Lambda $LAMBDA_NAME đã có → cập nhật code"
  aws lambda update-function-code --function-name "$LAMBDA_NAME" --zip-file "fileb://$ZIP" \
    --query LastUpdateStatus --output text
  aws lambda wait function-updated-v2 --function-name "$LAMBDA_NAME"
  aws lambda update-function-configuration --function-name "$LAMBDA_NAME" \
    --role "$ROLE_ARN" --timeout 10 --memory-size 256 \
    --environment "Variables={ORDERS_TABLE=$ORDERS_TABLE}" --query LastUpdateStatus --output text
  aws lambda wait function-updated-v2 --function-name "$LAMBDA_NAME"
else
  echo "Tạo Lambda $LAMBDA_NAME (python3.14, arm64)"
  # Role vừa tạo cần vài giây mới mượn được → thử lại tối đa ~60s
  for i in $(seq 1 6); do
    if aws lambda create-function --function-name "$LAMBDA_NAME" \
         --runtime python3.14 --architectures arm64 \
         --handler handler.lambda_handler --zip-file "fileb://$ZIP" \
         --role "$ROLE_ARN" --timeout 10 --memory-size 256 \
         --environment "Variables={ORDERS_TABLE=$ORDERS_TABLE}" \
         --description "Tool get_order cho AgentCore Gateway (support-agent)" \
         --tags project=support-agent --query FunctionArn --output text 2>"$TMP_DIR/err"; then
      break
    fi
    grep -q "cannot be assumed" "$TMP_DIR/err" || { cat "$TMP_DIR/err" >&2; exit 1; }
    [[ $i -eq 6 ]] && { echo "Role vẫn chưa mượn được sau 60s" >&2; exit 1; }
    echo "  role chưa lan tỏa, thử lại sau 10s…"; sleep 10
  done
  aws lambda wait function-active-v2 --function-name "$LAMBDA_NAME"
fi

echo "Xong: $(lambda_arn)"
