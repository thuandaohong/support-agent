#!/usr/bin/env bash
# Bước 3 (Day 61): target thứ hai "policies" trên CÙNG Gateway → Lambda search_policy.
#   Tên tool agent thấy = "<POLICY_TARGET_NAME>___search_policy". Agent vẫn 1 URL, 1 quyền InvokeGateway.
#   Role Gateway phải được gọi Lambda này trước → chạy lại 03-gateway.sh (cập nhật policy) trước script này.
# Chạy lại được: target đã có thì cập nhật.
source "$(dirname "$0")/_env.sh"

GW="$(gateway_id)"; [[ -n "$GW" ]] || { echo "Chưa có Gateway $GATEWAY_NAME → chạy 03-gateway.sh" >&2; exit 1; }
ensure_target "$GW" "$POLICY_TARGET_NAME" "$POLICY_LAMBDA_NAME" "$HERE/search_policy.tool.json"
echo "Xong: tool ${POLICY_TARGET_NAME}___search_policy trên gateway $GW"
