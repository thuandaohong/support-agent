#!/usr/bin/env bash
# Bước 2 (Day 61): role riêng + Lambda chứa tool search_policy (lambdas/search_policy/handler.py).
#   role → CHỈ bedrock:Retrieve trên đúng KB chính sách + ghi log của chính hàm này
#   KB ID tra theo KB_NAME lúc chạy (_env.sh), truyền vào Lambda qua biến POLICY_KB_ID
# Chạy lại được: role cập nhật policy; hàm đã có thì cập nhật code + cấu hình.
source "$(dirname "$0")/_env.sh"

deploy_lambda "$POLICY_LAMBDA_NAME" "$POLICY_LAMBDA_ROLE" "$REPO/lambdas/search_policy" \
  "$HERE/lambda-policy-permissions-policy.json.tpl" "Variables={POLICY_KB_ID=$KB_ID}" \
  "Tool search_policy cho AgentCore Gateway"
