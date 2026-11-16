#!/usr/bin/env bash
# Bước 4 (Day 63): user test = các khách có trong eval (TEST_USERS trong auth.env).
#   username = customer_id → access token có sẵn claim "username". Pool không phân biệt hoa/thường
#   nên Cognito LƯU CHỮ THƯỜNG: claim là "c003" → auth/tokens.py chuẩn hoá .upper(). Vì sao dùng
#   username mà không dùng thuộc tính tự đặt (custom:customer_id)? Access token có scope
#   aws.cognito.signin.user.admin → người dùng TỰ SỬA được thuộc tính của mình; username thì không.
#   GIỚI HẠN BÀI HỌC:
#   production để username là email/sub và ánh xạ sub → customer_id (bảng, hoặc Pre Token
#   Generation trigger — cần tier Essentials). Xem README.
#   --message-action SUPPRESS → không gửi email mời (user không có email thật)
#   mật khẩu ngẫu nhiên đủ loại ký tự, đặt vĩnh viễn (không bắt đổi lần đầu), ghi vào
#   test-users.env (gitignore, chmod 600) — KHÔNG in ra màn hình, không lưu chỗ nào khác
# Chạy lại được: user đã có + đã có mật khẩu trong file → bỏ qua; thiếu mật khẩu → đặt lại.
source "$(dirname "$0")/_env.sh"

POOL="$(pool_id)"; [[ -n "$POOL" ]] || { echo "Chưa có user pool $POOL_NAME — chạy 01-user-pool.sh" >&2; exit 1; }
umask 077; touch "$USERS_FILE"; chmod 600 "$USERS_FILE"

new_password() {   # 24 ký tự ngẫu nhiên + chắc chắn đủ 4 loại (policy của pool)
  python3 -c 'import secrets, string; a = string.ascii_letters + string.digits
print("".join(secrets.choice(a) for _ in range(24)) + "Aa1!")'
}

for u in $TEST_USERS; do
  if ! aws cognito-idp admin-get-user --user-pool-id "$POOL" --username "$u" >/dev/null 2>&1; then
    aws cognito-idp admin-create-user --user-pool-id "$POOL" --username "$u" \
      --message-action SUPPRESS >/dev/null
    echo "Tạo user $u"
  elif grep -q "^$u=" "$USERS_FILE"; then
    echo "User $u đã có (mật khẩu trong test-users.env) → bỏ qua"; continue
  fi
  pw="$(new_password)"
  aws cognito-idp admin-set-user-password --user-pool-id "$POOL" --username "$u" \
    --password "$pw" --permanent
  { grep -v "^$u=" "$USERS_FILE" || true; echo "$u=$pw"; } > "$USERS_FILE.tmp" && mv "$USERS_FILE.tmp" "$USERS_FILE"
  echo "  đặt mật khẩu cho $u (ghi vào test-users.env)"
done
aws cognito-idp list-users --user-pool-id "$POOL" --query 'Users[].[Username,UserStatus,Enabled]' --output text
