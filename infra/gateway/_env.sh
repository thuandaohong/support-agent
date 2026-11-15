# shellcheck shell=bash
# Dùng chung cho các script infra/gateway/*.sh — nạp biến, kiểm thiếu, hàm tiện ích.
# Không chạy trực tiếp: các script khác `source` file này.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
ENV_FILE="${GATEWAY_ENV:-$HERE/gateway.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Thiếu $ENV_FILE — chạy: cp $HERE/gateway.env.example $HERE/gateway.env rồi kiểm giá trị" >&2
  exit 1
fi
set -a; source "$ENV_FILE"; set +a

for v in AWS_REGION ORDERS_TABLE LAMBDA_NAME LAMBDA_ROLE GATEWAY_NAME GATEWAY_ROLE TARGET_NAME; do
  [[ -n "${!v:-}" ]] || { echo "Biến $v trống trong $ENV_FILE" >&2; exit 1; }
done
command -v envsubst >/dev/null || { echo "Cần envsubst (brew install gettext)" >&2; exit 1; }

export AWS_PAGER=""
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export ACCOUNT_ID

# Thư mục tạm cho policy đã render (có account ID thật) + file zip — tự xoá khi script kết thúc
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# render <file.tpl> → in đường dẫn file JSON đã thay biến (chỉ thay đúng các biến liệt kê)
render() {
  local out="$TMP_DIR/$(basename "${1%.tpl}")"
  envsubst '${ACCOUNT_ID} ${AWS_REGION} ${ORDERS_TABLE} ${LAMBDA_NAME} ${GATEWAY_NAME}' < "$1" > "$out"
  echo "$out"
}

# ensure_role <tên> <trust.json> <perms.json> <mô tả> — tạo role hoặc cập nhật trust; ghi đè inline policy
ensure_role() {
  if aws iam get-role --role-name "$1" >/dev/null 2>&1; then
    echo "Role $1 đã có → cập nhật trust policy"
    aws iam update-assume-role-policy --role-name "$1" --policy-document "file://$2"
  else
    echo "Tạo role $1"
    aws iam create-role --role-name "$1" --assume-role-policy-document "file://$2" \
      --description "$4" --tags Key=project,Value=support-agent --query Role.Arn --output text
  fi
  aws iam put-role-policy --role-name "$1" --policy-name "${1}-perms" --policy-document "file://$3"
}

lambda_arn() {
  aws lambda get-function --function-name "$LAMBDA_NAME" --query Configuration.FunctionArn --output text
}
