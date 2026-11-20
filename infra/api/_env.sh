# shellcheck shell=bash
# Dùng chung cho các script infra/api/*.sh — nạp biến, kiểm thiếu, hàm tiện ích.
# Không chạy trực tiếp: các script khác `source` file này.
# Day 65: Bridge Lambda + HTTP API do Terraform quản (infra/terraform/modules/web_api, lambda_function)
# — ở đây chỉ còn 03-frontend-env.sh (ghi frontend/.env.local), không tạo / sửa resource.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
ENV_FILE="${API_ENV:-$HERE/api.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Thiếu $ENV_FILE — chạy: cp $HERE/api.env.example $HERE/api.env rồi kiểm giá trị" >&2
  exit 1
fi
set -a; source "$ENV_FILE"; set +a

for v in AWS_REGION POOL_NAME CLIENT_NAME API_NAME ALLOWED_ORIGIN; do
  [[ -n "${!v:-}" ]] || { echo "Biến $v trống trong $ENV_FILE" >&2; exit 1; }
done

export AWS_PAGER=""
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"

# Cognito (Terraform modules/auth): tra theo tên
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
