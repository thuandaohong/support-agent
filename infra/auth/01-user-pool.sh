#!/usr/bin/env bash
# Bước 3a (Day 63): Cognito user pool cho NGƯỜI DÙNG — trả lời "ai đang hỏi?" (AuthN).
#   tier LITE                → đủ dùng, miễn phí tới 10k MAU
#   AllowAdminCreateUserOnly → KHÔNG tự đăng ký: người lạ không tự tạo được tài khoản mang tên
#                              một customer_id (username = customer_id, xem README)
#   mật khẩu ≥ 12 ký tự, đủ loại · username không phân biệt hoa/thường (khuyến nghị AWS)
#   không MFA (bài học) · không xoá được khi bật deletion protection → để INACTIVE cho khoá học
# Chạy lại được: pool đã có thì giữ nguyên, chỉ in id/issuer.
source "$(dirname "$0")/_env.sh"

ID="$(pool_id)"
if [[ -n "$ID" ]]; then
  echo "User pool $POOL_NAME đã có"
else
  echo "Tạo user pool $POOL_NAME (LITE, chỉ admin tạo user)"
  ID="$(aws cognito-idp create-user-pool --pool-name "$POOL_NAME" \
    --user-pool-tier LITE \
    --admin-create-user-config AllowAdminCreateUserOnly=true \
    --policies 'PasswordPolicy={MinimumLength=12,RequireUppercase=true,RequireLowercase=true,RequireNumbers=true,RequireSymbols=true,TemporaryPasswordValidityDays=1}' \
    --username-configuration CaseSensitive=false \
    --mfa-configuration OFF \
    --deletion-protection INACTIVE \
    --user-pool-tags project=support-agent \
    --query UserPool.Id --output text)"
fi
echo "Xong. issuer: $(issuer "$ID" | sed -E 's/_[A-Za-z0-9]+$/_<…>/')"
echo "      JWKS:   <issuer>/.well-known/jwks.json"
