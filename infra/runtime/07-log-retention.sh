#!/usr/bin/env bash
# Đặt thời hạn giữ log CloudWatch của Runtime (mặc định log group tạo ra KHÔNG BAO GIỜ hết hạn →
# tiền lưu trữ cộng dồn mãi; Runtime health-check /ping ~230 dòng/giờ).
#   ./07-log-retention.sh        → dùng LOG_RETENTION_DAYS trong runtime.env (mặc định 14)
# Log group chỉ xuất hiện sau lần invoke đầu → chạy script này SAU 03-invoke.sh. Chạy lại được.
source "$(dirname "$0")/_env.sh"

DAYS="${LOG_RETENTION_DAYS:-14}"   # CloudWatch chỉ nhận: 1 3 5 7 14 30 60 90 120 150 180 365 …
ID="$(runtime_id)"; [[ -n "$ID" ]] || { echo "Chưa có Runtime $RUNTIME_NAME" >&2; exit 1; }
GROUPS_FOUND="$(aws logs describe-log-groups --log-group-name-prefix "/aws/bedrock-agentcore/runtimes/$ID" \
  --query 'logGroups[].logGroupName' --output text)"
[[ -n "$GROUPS_FOUND" ]] || { echo "Chưa có log group cho $ID — invoke 1 lần (03-invoke.sh) rồi chạy lại" >&2; exit 1; }

for g in $GROUPS_FOUND; do
  aws logs put-retention-policy --log-group-name "$g" --retention-in-days "$DAYS"
  echo "$g → giữ $DAYS ngày"
done
