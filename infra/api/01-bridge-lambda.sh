#!/usr/bin/env bash
# Bước 2 (Day 64): role riêng + Bridge Lambda (lambdas/chat_bridge/handler.py).
#   role   → CHỈ bedrock-agentcore:InvokeAgentRuntime trên đúng Runtime $RUNTIME_NAME + log của chính nó
#            Resource cần CẢ ARN runtime LẪN …/runtime-endpoint/DEFAULT (đo thật: thiếu một trong
#            hai → AccessDeniedException)
#            (không InvokeModel, không Gateway, không DynamoDB/KB: bị chiếm cũng chỉ hỏi được agent)
#   hàm    → python3.14 arm64, 256 MB, timeout 29 s (HTTP API cắt integration ở 30 s), biến
#            AGENT_RUNTIME_ARN tra theo tên lúc chạy
#   log    → log group tạo TRƯỚC với retention (role khỏi cần logs:CreateLogGroup)
# Chạy lại được: role cập nhật policy; hàm đã có thì cập nhật code + cấu hình.
source "$(dirname "$0")/_env.sh"

TRUST="$HERE/lambda-trust-policy.json"
PERMS="$(render "$HERE/bridge-permissions-policy.json.tpl")"
python3 -m json.tool "$TRUST" >/dev/null && python3 -m json.tool "$PERMS" >/dev/null

if aws iam get-role --role-name "$BRIDGE_ROLE" >/dev/null 2>&1; then
  echo "Role $BRIDGE_ROLE đã có → cập nhật trust policy"
  aws iam update-assume-role-policy --role-name "$BRIDGE_ROLE" --policy-document "file://$TRUST"
else
  echo "Tạo role $BRIDGE_ROLE"
  aws iam create-role --role-name "$BRIDGE_ROLE" --assume-role-policy-document "file://$TRUST" \
    --description "Bridge Lambda $BRIDGE_NAME (web to AgentCore Runtime)" \
    --tags Key=project,Value=support-agent --query Role.Arn --output text >/dev/null
fi
aws iam put-role-policy --role-name "$BRIDGE_ROLE" --policy-name "${BRIDGE_ROLE}-perms" \
  --policy-document "file://$PERMS"
ROLE_ARN="$(role_arn "$BRIDGE_ROLE")"

LOG_GROUP="/aws/lambda/$BRIDGE_NAME"
if [[ -z "$(aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" \
            --query "logGroups[?logGroupName=='$LOG_GROUP'].logGroupName" --output text)" ]]; then
  aws logs create-log-group --log-group-name "$LOG_GROUP" --tags project=support-agent
fi
aws logs put-retention-policy --log-group-name "$LOG_GROUP" --retention-in-days "${LOG_RETENTION_DAYS:-14}"

# Chỉ handler.py (boto3 có sẵn trong runtime Lambda). -X: zip giống nhau mỗi lần build
ZIP="$TMP_DIR/$BRIDGE_NAME.zip"
(cd "$REPO/lambdas/chat_bridge" && zip -qX "$ZIP" handler.py)
ENV_JSON="$(python3 -c 'import json, os; print(json.dumps({"Variables": {"AGENT_RUNTIME_ARN": os.environ["RUNTIME_ARN"]}}))')"
CONFIG=(--role "$ROLE_ARN" --timeout 29 --memory-size 256 --environment "$ENV_JSON")

if aws lambda get-function --function-name "$BRIDGE_NAME" >/dev/null 2>&1; then
  echo "Lambda $BRIDGE_NAME đã có → cập nhật code + cấu hình"
  aws lambda update-function-code --function-name "$BRIDGE_NAME" --zip-file "fileb://$ZIP" >/dev/null
  aws lambda wait function-updated-v2 --function-name "$BRIDGE_NAME"
  aws lambda update-function-configuration --function-name "$BRIDGE_NAME" "${CONFIG[@]}" >/dev/null
  aws lambda wait function-updated-v2 --function-name "$BRIDGE_NAME"
else
  echo "Tạo Lambda $BRIDGE_NAME (python3.14, arm64, timeout 29 s)"
  for i in $(seq 1 6); do   # role vừa tạo cần vài giây mới mượn được
    if aws lambda create-function --function-name "$BRIDGE_NAME" \
         --runtime python3.14 --architectures arm64 --handler handler.lambda_handler \
         --zip-file "fileb://$ZIP" "${CONFIG[@]}" \
         --description "Bridge web to AgentCore Runtime (support-agent)" \
         --tags project=support-agent >/dev/null 2>"$TMP_DIR/err"; then
      break
    fi
    grep -q "cannot be assumed" "$TMP_DIR/err" || { cat "$TMP_DIR/err" >&2; exit 1; }
    [[ $i -eq 6 ]] && { echo "Role vẫn chưa mượn được sau 60s" >&2; exit 1; }
    echo "  role chưa lan tỏa, thử lại sau 10s…"; sleep 10
  done
  aws lambda wait function-active-v2 --function-name "$BRIDGE_NAME"
fi
echo "Xong: Lambda $BRIDGE_NAME (log $LOG_GROUP giữ ${LOG_RETENTION_DAYS:-14} ngày)"
