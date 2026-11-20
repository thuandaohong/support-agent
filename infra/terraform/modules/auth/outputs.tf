output "pool_id" {
  value = aws_cognito_user_pool.this.id
}

output "client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "issuer" {
  description = "iss trong token — JWT authorizer của HTTP API kiểm giá trị này"
  value       = "https://${aws_cognito_user_pool.this.endpoint}"
}
