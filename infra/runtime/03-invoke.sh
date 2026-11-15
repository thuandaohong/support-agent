#!/usr/bin/env bash
# Bước 4: gọi Runtime 1 câu.   ./03-invoke.sh "Đơn #1003 còn đổi trả được không?" C003
# customer_id: ở đây MÌNH đóng vai backend đã xác thực (production: backend lấy từ JWT).
# Runtime chuyển nguyên payload vào POST /invocations của serve.py. Container trả 4xx/5xx → CLI báo
# lỗi 424 RuntimeClientError.
source "$(dirname "$0")/_env.sh"

QUESTION="${1:?Cách dùng: $0 \"câu hỏi\" [customer_id]}"
CUSTOMER="${2:-C003}"
ID="$(runtime_id)"; [[ -n "$ID" ]] || { echo "Chưa có Runtime $RUNTIME_NAME" >&2; exit 1; }

# json.dumps để escape đúng dấu nháy / tiếng Việt trong câu hỏi
PAYLOAD="$(Q="$QUESTION" C="$CUSTOMER" python3 -c 'import json,os;print(json.dumps({"question":os.environ["Q"],"customer_id":os.environ["C"]},ensure_ascii=False))')"
SID="${SESSION_ID:-cli-$(python3 -c 'import uuid;print(uuid.uuid4().hex)')}"   # >= 33 ký tự

aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn "$(runtime_arn "$ID")" --qualifier DEFAULT \
  --runtime-session-id "$SID" \
  --content-type application/json --accept application/json \
  --payload "$PAYLOAD" --cli-binary-format raw-in-base64-out \
  "$TMP_DIR/out.json" >/dev/null
cat "$TMP_DIR/out.json"; echo
echo "session: $SID" >&2
