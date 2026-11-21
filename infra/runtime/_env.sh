# shellcheck shell=bash
# Dùng chung cho các script infra/runtime/*.sh — nạp biến, kiểm thiếu, hàm tiện ích.
# Không chạy trực tiếp: các script khác `source` file này.
# Day 65: Runtime + role do Terraform quản (infra/terraform/modules/runtime) — ở đây chỉ còn script
# vận hành (invoke, logs, stop session), không tạo / sửa resource.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${RUNTIME_ENV:-$HERE/runtime.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Thiếu $ENV_FILE — chạy: cp $HERE/runtime.env.example $HERE/runtime.env rồi điền giá trị" >&2
  exit 1
fi
set -a; source "$ENV_FILE"; set +a

for v in AWS_REGION RUNTIME_NAME; do
  [[ -n "${!v:-}" ]] || { echo "Biến $v trống trong $ENV_FILE" >&2; exit 1; }
done

export AWS_PAGER=""          # không mở less cho output CLI
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"

# Thư mục tạm cho output invoke — tự xoá khi script kết thúc
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# runtime_id → id của Runtime tên $RUNTIME_NAME, rỗng nếu chưa có (tra theo tên, không lưu file trạng thái)
runtime_id() {
  local id
  id="$(aws bedrock-agentcore-control list-agent-runtimes \
        --query "agentRuntimes[?agentRuntimeName=='$RUNTIME_NAME'].agentRuntimeId | [0]" --output text)"
  [[ "$id" == "None" ]] && id=""
  echo "$id"
}

runtime_arn() {
  aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id "$1" --query agentRuntimeArn --output text
}
