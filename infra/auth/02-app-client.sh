#!/usr/bin/env bash
# Bước 3b (Day 63): app client "support-web" — cửa để người dùng lấy token.
#   PUBLIC, KHÔNG secret        → Day 64 là SPA React: code trong trình duyệt ai cũng đọc được,
#                                 nên không giữ được secret (secret chỉ hợp với server)
#   ALLOW_USER_SRP_AUTH         → frontend chứng minh biết mật khẩu mà KHÔNG gửi mật khẩu đi
#   ALLOW_ADMIN_USER_PASSWORD_AUTH → script test (scripts/invoke_runtime.py --auth) — flow này đòi
#                                 quyền IAM cognito-idp:AdminInitiateAuth, người ngoài không dùng được
#   ALLOW_REFRESH_TOKEN_AUTH    → làm mới access token không cần nhập lại mật khẩu
#   KHÔNG bật ALLOW_USER_PASSWORD_AUTH (gửi mật khẩu thô, không cần quyền gì)
#   access/id token 60 phút · refresh 1 ngày · thu hồi được token · không lộ "user có tồn tại không"
# Chạy lại được: client đã có → update (ghi đè đủ cấu hình như dưới).
source "$(dirname "$0")/_env.sh"

POOL="$(pool_id)"; [[ -n "$POOL" ]] || { echo "Chưa có user pool $POOL_NAME — chạy 01-user-pool.sh" >&2; exit 1; }

SETTINGS=(
  --explicit-auth-flows ALLOW_USER_SRP_AUTH ALLOW_ADMIN_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH
  --prevent-user-existence-errors ENABLED
  --enable-token-revocation
  --access-token-validity 60 --id-token-validity 60 --refresh-token-validity 1
  --token-validity-units AccessToken=minutes,IdToken=minutes,RefreshToken=days
)
ID="$(client_id "$POOL")"
if [[ -n "$ID" ]]; then
  echo "App client $CLIENT_NAME đã có → cập nhật cấu hình"
  aws cognito-idp update-user-pool-client --user-pool-id "$POOL" --client-id "$ID" \
    --client-name "$CLIENT_NAME" "${SETTINGS[@]}" >/dev/null
else
  echo "Tạo app client $CLIENT_NAME (public, không secret)"
  aws cognito-idp create-user-pool-client --user-pool-id "$POOL" \
    --client-name "$CLIENT_NAME" --no-generate-secret "${SETTINGS[@]}" >/dev/null
fi
aws cognito-idp describe-user-pool-client --user-pool-id "$POOL" --client-id "$(client_id "$POOL")" \
  --query 'UserPoolClient.{secret:ClientSecret,flows:ExplicitAuthFlows,access_min:AccessTokenValidity,revocation:EnableTokenRevocation,existence_errors:PreventUserExistenceErrors}' \
  --output json
