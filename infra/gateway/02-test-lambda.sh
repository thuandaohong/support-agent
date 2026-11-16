#!/usr/bin/env bash
# Bước 2 (kiểm): gọi thẳng Lambda, giả lập context Gateway gửi (tên tool có tiền tố target___).
#   ./02-test-lambda.sh 1003 C003     → {"found": true, "order": {...}}
#   ./02-test-lambda.sh 1003 C020     → {"found": false}   (đơn của người khác)
# Không có đối số: chạy 3 ca chuẩn.
source "$(dirname "$0")/_env.sh"

# Gateway truyền metadata qua ClientContext; Python đọc ở context.client_context.custom
CLIENT_CONTEXT="$(TOOL="${TARGET_NAME}___get_order" python3 -c 'import base64, json, os
print(base64.b64encode(json.dumps({"custom": {"bedrockAgentCoreToolName": os.environ["TOOL"]}}).encode()).decode())')"

call() {
  local payload
  payload="$(O="$1" C="$2" python3 -c 'import json,os;print(json.dumps({"order_id":os.environ["O"],"customer_id":os.environ["C"]}))')"
  aws lambda invoke --function-name "$LAMBDA_NAME" --client-context "$CLIENT_CONTEXT" \
    --payload "$payload" --cli-binary-format raw-in-base64-out \
    --query FunctionError --output text "$TMP_DIR/out.json" > "$TMP_DIR/err.txt"
  [[ "$(cat "$TMP_DIR/err.txt")" == "None" ]] || echo "  (FunctionError: $(cat "$TMP_DIR/err.txt"))" >&2
  printf '%s %s → ' "$1" "$2"; cat "$TMP_DIR/out.json"; echo
}

if [[ $# -ge 2 ]]; then
  call "$1" "$2"
else
  call 1003 C003   # đơn của chính khách → found
  call 1003 C020   # đơn của người khác  → found:false
  call 9999 C003   # không tồn tại       → found:false (giống hệt dòng trên)
fi
