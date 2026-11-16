#!/usr/bin/env bash
# Bước 3b (Day 60): nối Gateway → Lambda get_order bằng target "orders", kèm tool schema.
#   Tên tool agent thấy = "<TARGET_NAME>___get_order" (Gateway thêm tiền tố, Lambda tự cắt).
#   GATEWAY_IAM_ROLE → Gateway gọi Lambda bằng service role của nó (03-gateway.sh).
# Chạy lại được: target đã có thì cập nhật (đổi schema → chạy lại script này). (ensure_target: _env.sh)
source "$(dirname "$0")/_env.sh"

GW="$(gateway_id)"; [[ -n "$GW" ]] || { echo "Chưa có Gateway $GATEWAY_NAME → chạy 03-gateway.sh" >&2; exit 1; }
ensure_target "$GW" "$TARGET_NAME" "$LAMBDA_NAME" "$HERE/get_order.tool.json"
echo "Xong: tool ${TARGET_NAME}___get_order trên gateway $GW"
