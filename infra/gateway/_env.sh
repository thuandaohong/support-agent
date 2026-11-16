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

role_arn() {
  aws iam get-role --role-name "$1" --query Role.Arn --output text
}

# gateway_id → id của Gateway tên $GATEWAY_NAME, rỗng nếu chưa có (tra theo tên, không lưu file trạng thái)
gateway_id() {
  local id
  id="$(aws bedrock-agentcore-control list-gateways \
        --query "items[?name=='$GATEWAY_NAME'].gatewayId | [0]" --output text)"
  [[ "$id" == "None" ]] && id=""
  echo "$id"
}

# target_id <gateway_id> → id của target tên $TARGET_NAME, rỗng nếu chưa có
target_id() {
  local id
  id="$(aws bedrock-agentcore-control list-gateway-targets --gateway-identifier "$1" \
        --query "items[?name=='$TARGET_NAME'].targetId | [0]" --output text)"
  [[ "$id" == "None" ]] && id=""
  echo "$id"
}

# wait_status <mô tả> <lệnh get…> — chờ READY (tối đa ~5 phút), in statusReasons nếu hỏng
wait_status() {
  local what="$1" status; shift
  for _ in $(seq 1 30); do
    status="$("$@" --query status --output text)"
    echo "  $what: $status"
    case "$status" in
      READY) return 0 ;;
      *FAILED*|*UNSUCCESSFUL*) "$@" --query statusReasons --output text >&2; return 1 ;;
    esac
    sleep 10
  done
  echo "Quá 5 phút chưa READY" >&2
  return 1
}
