#!/usr/bin/env bash
# Dừng 1 session ngay (không chờ IDLE_TIMEOUT) — tiết kiệm khi test xong.   ./06-stop-session.sh <session-id>
source "$(dirname "$0")/_env.sh"

SID="${1:?Cách dùng: $0 <session-id> (03-invoke.sh in ra ở dòng cuối)}"
ID="$(runtime_id)"; [[ -n "$ID" ]] || { echo "Chưa có Runtime $RUNTIME_NAME" >&2; exit 1; }
aws bedrock-agentcore stop-runtime-session --agent-runtime-arn "$(runtime_arn "$ID")" \
  --runtime-session-id "$SID" --qualifier DEFAULT >/dev/null
echo "Đã dừng session $SID"
