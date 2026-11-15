#!/usr/bin/env bash
# Bước 5: xem log Runtime trên CloudWatch.   ./04-logs.sh [15m]
# Kiểm: có dòng số đo (route=, latency_ms=, in_tokens=) và KHÔNG có nội dung câu hỏi.
source "$(dirname "$0")/_env.sh"

ID="$(runtime_id)"; [[ -n "$ID" ]] || { echo "Chưa có Runtime $RUNTIME_NAME" >&2; exit 1; }
GROUPS_FOUND="$(aws logs describe-log-groups --log-group-name-prefix "/aws/bedrock-agentcore/runtimes/$ID" \
  --query 'logGroups[].logGroupName' --output text)"
[[ -n "$GROUPS_FOUND" ]] || { echo "Chưa có log group cho $ID (chưa invoke lần nào?)" >&2; exit 1; }
for g in $GROUPS_FOUND; do
  echo "== $g"
  aws logs tail "$g" --since "${1:-15m}" --format short
done
