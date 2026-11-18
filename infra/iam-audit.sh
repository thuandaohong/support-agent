#!/usr/bin/env bash
# Day 63: rà IAM của cả hệ, CHỈ ĐỌC (không sửa gì trên AWS).
#   bản đồ quyền 6 role + IAM Access Analyzer + ma trận simulate được/chặn → lệch thì exit 1
# Tên role / bảng / model / Lambda lấy từ infra/runtime/runtime.env + infra/gateway/gateway.env.
# Logic ở scripts/iam_audit.py; script này chỉ nạp biến.
#   ./infra/iam-audit.sh
set -euo pipefail
INFRA="$(cd "$(dirname "$0")" && pwd)"

set -a; source "$INFRA/runtime/runtime.env"; set +a      # ROLE_NAME, MODEL_ID, RUNTIME_NAME
source "$INFRA/gateway/_env.sh"                           # gateway.env + ACCOUNT_ID (+ TMP_DIR tự xoá)
export ROLE_NAME MODEL_ID GATEWAY_NAME GATEWAY_ROLE LAMBDA_ROLE POLICY_LAMBDA_ROLE \
       LAMBDA_NAME POLICY_LAMBDA_NAME ORDERS_TABLE KB_NAME

# cần boto3: ưu tiên .venv của repo, không có thì python3 trên PATH
PY="$REPO/.venv/bin/python"; [[ -x "$PY" ]] || PY=python3
"$PY" "$REPO/scripts/iam_audit.py"
