# ============================================================
# module auth — Cognito cho NGƯỜI DÙNG (Day 63): user pool + app client public cho web (SRP).
# Thay cho infra/auth/01-user-pool.sh, 02-app-client.sh. User test + mật khẩu KHÔNG ở đây
# (03-test-users.sh): đưa vào Terraform thì mật khẩu nằm plaintext trong state.
# Nhiều thuộc tính pool KHÔNG sửa được (username, schema…) → lệch = tạo lại pool = mất user, đổi pool id.
# ============================================================

resource "aws_cognito_user_pool" "this" {
  name                = var.pool_name
  user_pool_tier      = "LITE" # đủ cho SRP + JWT; ESSENTIALS/PLUS tính tiền theo MAU
  mfa_configuration   = "OFF"  # khoá học; production nên bật
  deletion_protection = "INACTIVE"

  # Username = mã khách (C003). Không phân biệt hoa/thường → Cognito lưu "c003" (Bridge .upper() lại)
  username_configuration {
    case_sensitive = false
  }

  # Chỉ admin tạo user (không tự đăng ký) — mã khách phải là khách thật
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    password_history_size            = 0
    temporary_password_validity_days = 1
  }

  sign_in_policy {
    allowed_first_auth_factors = ["PASSWORD"]
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
    recovery_mechanism {
      name     = "verified_phone_number"
      priority = 2
    }
  }

  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# App client cho SPA React: PUBLIC (không secret — code trình duyệt không giữ được bí mật)
resource "aws_cognito_user_pool_client" "web" {
  name         = var.client_name
  user_pool_id = aws_cognito_user_pool.this.id

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",            # web: chứng minh biết mật khẩu mà không gửi mật khẩu
    "ALLOW_REFRESH_TOKEN_AUTH",       # Amplify tự làm mới access token
    "ALLOW_ADMIN_USER_PASSWORD_AUTH", # script test (auth/cognito.py) — cần quyền IAM, trình duyệt không dùng được
  ]
  prevent_user_existence_errors = "ENABLED" # sai user hay sai mật khẩu đều cùng một lỗi
  enable_token_revocation       = true

  access_token_validity  = 60
  id_token_validity      = 60
  refresh_token_validity = 1
  auth_session_validity  = 3
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}
