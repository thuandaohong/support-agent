# shellcheck shell=bash
# Dùng chung cho các script infra/auth/*.sh — nạp biến, kiểm thiếu, hàm tiện ích.
# Không chạy trực tiếp: các script khác `source` file này.
# Day 65: pool + app client do Terraform quản (infra/terraform/modules/auth) — ở đây chỉ còn
# 03-test-users.sh (user test + mật khẩu: không đưa vào Terraform vì sẽ nằm plaintext trong state).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${AUTH_ENV:-$HERE/auth.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Thiếu $ENV_FILE — chạy: cp $HERE/auth.env.example $HERE/auth.env rồi kiểm giá trị" >&2
  exit 1
fi
set -a; source "$ENV_FILE"; set +a

for v in AWS_REGION POOL_NAME TEST_USERS; do
  [[ -n "${!v:-}" ]] || { echo "Biến $v trống trong $ENV_FILE" >&2; exit 1; }
done

export AWS_PAGER=""
export AWS_REGION AWS_DEFAULT_REGION="$AWS_REGION"
# Mật khẩu user test (03-test-users.sh ghi) — gitignore, chỉ chủ máy đọc được
USERS_FILE="$HERE/test-users.env"

# pool_id → id của user pool tên $POOL_NAME, rỗng nếu chưa có (tra theo tên, không lưu file trạng thái)
pool_id() {
  local id
  id="$(aws cognito-idp list-user-pools --max-results 60 \
        --query "UserPools[?Name=='$POOL_NAME'].Id | [0]" --output text)"
  [[ "$id" == "None" ]] && id=""
  echo "$id"
}
