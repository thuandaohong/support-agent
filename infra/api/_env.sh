# shellcheck shell=bash
# Dùng chung cho các script infra/api/*.sh — nạp biến, kiểm thiếu, hàm tiện ích.
# Không chạy trực tiếp: các script khác `source` file này.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
ENV_FILE="${API_ENV:-$HERE/api.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Thiếu $ENV_FILE — chạy: cp $HERE/api.env.example $HERE/api.env rồi kiểm giá trị" >&2
  exit 1
fi
set -a; source "$ENV_FILE"; set +a

for v in AWS_REGION RUNTIME_NAME POOL_NAME CLIENT_NAME BRIDGE_NAME BRIDGE_ROLE API_NAME \
         ALLOWED_ORIGIN THROTTLE_RATE THROTTLE_BURST; do
  [[ -n "${!v:-}" ]] || { echo "Biến $v trống trong $ENV_FILE" >&2; exit 1; }
done
command -v envsubst >/dev/null || { echo "Cần envsubst (brew install gettext)" >&2; exit 1; }

export AWS_PAGER=""
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export ACCOUNT_ID

# Runtime: tra ARN theo tên mỗi lần chạy (không lưu ARN — có account ID)
RUNTIME_ARN="$(aws bedrock-agentcore-control list-agent-runtimes \
  --query "agentRuntimes[?agentRuntimeName=='$RUNTIME_NAME'].agentRuntimeArn | [0]" --output text)"
[[ -n "$RUNTIME_ARN" && "$RUNTIME_ARN" != "None" ]] || { echo "Không thấy Runtime $RUNTIME_NAME" >&2; exit 1; }
export RUNTIME_ARN BRIDGE_NAME

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# render <file.tpl> → in đường dẫn file JSON đã thay biến (chỉ thay đúng các biến liệt kê)
render() {
  local out="$TMP_DIR/$(basename "${1%.tpl}")"
  envsubst '${ACCOUNT_ID} ${AWS_REGION} ${RUNTIME_ARN} ${BRIDGE_NAME}' < "$1" > "$out"
  echo "$out"
}

role_arn() {
  aws iam get-role --role-name "$1" --query Role.Arn --output text
}

# Cognito (infra/auth): tra theo tên
pool_id() {
  local id
  id="$(aws cognito-idp list-user-pools --max-results 60 \
        --query "UserPools[?Name=='$POOL_NAME'].Id | [0]" --output text)"
  [[ "$id" == "None" ]] && id=""
  echo "$id"
}
client_id() {
  local id
  id="$(aws cognito-idp list-user-pool-clients --user-pool-id "$1" --max-results 60 \
        --query "UserPoolClients[?ClientName=='$CLIENT_NAME'].ClientId | [0]" --output text)"
  [[ "$id" == "None" ]] && id=""
  echo "$id"
}

# api_id → id HTTP API tên $API_NAME, rỗng nếu chưa có
api_id() {
  local id
  id="$(aws apigatewayv2 get-apis --query "Items[?Name=='$API_NAME'].ApiId | [0]" --output text)"
  [[ "$id" == "None" ]] && id=""
  echo "$id"
}
