#!/usr/bin/env bash
# Bước 2 (Day 60): role riêng + Lambda chứa tool get_order (lambdas/get_order/handler.py).
#   role     → CHỈ GetItem trên bảng đơn + ghi log của chính hàm này
#   log group tạo TRƯỚC với retention → role không cần logs:CreateLogGroup
# Chạy lại được: role cập nhật policy; hàm đã có thì cập nhật code + cấu hình. (deploy_lambda: _env.sh)
source "$(dirname "$0")/_env.sh"

deploy_lambda "$LAMBDA_NAME" "$LAMBDA_ROLE" "$REPO/lambdas/get_order" \
  "$HERE/lambda-permissions-policy.json.tpl" "Variables={ORDERS_TABLE=$ORDERS_TABLE}" \
  "Tool get_order cho AgentCore Gateway"
