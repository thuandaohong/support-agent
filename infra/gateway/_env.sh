# shellcheck shell=bash
# Dùng chung cho các script infra/gateway/*.sh và infra/iam-audit.sh — nạp biến, kiểm thiếu, hàm tiện ích.
# Không chạy trực tiếp: các script khác `source` file này.
# Day 65: Gateway, target, 2 Lambda, 3 role do Terraform quản (infra/terraform/modules/gateway,
# lambda_function) — ở đây chỉ còn script test gọi thẳng Lambda, không tạo / sửa resource.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
ENV_FILE="${GATEWAY_ENV:-$HERE/gateway.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Thiếu $ENV_FILE — chạy: cp $HERE/gateway.env.example $HERE/gateway.env rồi kiểm giá trị" >&2
  exit 1
fi
set -a; source "$ENV_FILE"; set +a

# Tên dùng cho script test + iam-audit (role, bảng, KB: iam_audit.py tra theo tên)
for v in AWS_REGION ORDERS_TABLE LAMBDA_NAME LAMBDA_ROLE GATEWAY_NAME GATEWAY_ROLE TARGET_NAME \
         KB_NAME POLICY_LAMBDA_NAME POLICY_LAMBDA_ROLE POLICY_TARGET_NAME; do
  [[ -n "${!v:-}" ]] || { echo "Biến $v trống trong $ENV_FILE" >&2; exit 1; }
done

export AWS_PAGER=""
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export ACCOUNT_ID

# Thư mục tạm cho output Lambda — tự xoá khi script kết thúc
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# lambda_tool_context <tên tool đầy đủ> → ClientContext base64 như Gateway gửi
#   (Python đọc ở context.client_context.custom["bedrockAgentCoreToolName"])
lambda_tool_context() {
  TOOL="$1" python3 -c 'import base64, json, os
print(base64.b64encode(json.dumps({"custom": {"bedrockAgentCoreToolName": os.environ["TOOL"]}}).encode()).decode())'
}
