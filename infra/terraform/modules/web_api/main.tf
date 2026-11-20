# ============================================================
# module web_api — HTTP API trước Bridge Lambda (Day 64): CORS → JWT authorizer + scope → throttle → Lambda.
# Thay cho infra/api/02-http-api.sh. Bridge Lambda dựng bằng module lambda_function (live/main.tf).
# ============================================================

resource "aws_apigatewayv2_api" "this" {
  name          = var.name
  protocol_type = "HTTP" # rẻ hơn REST API, có sẵn JWT authorizer + CORS

  # CORS chỉ bảo vệ trình duyệt của người dùng (curl bỏ qua được) — lớp chặn thật là authorizer
  cors_configuration {
    allow_origins     = [var.allowed_origin]
    allow_methods     = ["POST"]
    allow_headers     = ["authorization", "content-type"]
    allow_credentials = false
    max_age           = 600 # trình duyệt nhớ kết quả preflight 10 phút
  }
}

# Token sai chữ ký / iss / client / hết hạn → 401 NGAY TẠI ĐÂY, Lambda không chạy, không tốn tiền
resource "aws_apigatewayv2_authorizer" "jwt" {
  api_id           = aws_apigatewayv2_api.this.id
  name             = "cognito-${var.client_name}"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    issuer   = var.issuer
    audience = [var.client_id] # access token không có aud → authorizer so client_id
  }
}

resource "aws_apigatewayv2_integration" "bridge" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_method     = "POST"
  integration_uri        = var.lambda_arn
  payload_format_version = "2.0" # claims nằm ở event.requestContext.authorizer.jwt.claims
  timeout_milliseconds   = 29000 # HTTP API cắt ở 30 s; Bridge đọc tối đa 25 s
}

resource "aws_apigatewayv2_route" "chat" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "POST /chat"
  target             = "integrations/${aws_apigatewayv2_integration.bridge.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
  # Authorizer KHÔNG kiểm token_use → bắt scope chỉ access token có → ID token bị 403
  authorization_scopes = ["aws.cognito.signin.user.admin"]
}

resource "aws_cloudwatch_log_group" "access" {
  name              = "/aws/apigateway/${var.name}"
  retention_in_days = var.log_retention_days
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true # sửa route là có hiệu lực, không cần deploy tay

  # Access log: mã, thời gian, lỗi authorizer — KHÔNG body, token, username
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access.arn
    format = jsonencode({
      requestId         = "$context.requestId"
      time              = "$context.requestTime"
      route             = "$context.routeKey"
      status            = "$context.status"
      latencyMs         = "$context.responseLatency"
      integrationStatus = "$context.integrationStatus"
      integrationMs     = "$context.integrationLatency"
      authError         = "$context.authorizer.error"
      error             = "$context.error.message"
    })
  }

  # Throttle cả API (xấp xỉ, đo Day 64) — request bị authorizer chặn không bị đếm
  default_route_settings {
    throttling_rate_limit  = var.throttle_rate
    throttling_burst_limit = var.throttle_burst
  }
}

# Resource policy của Lambda: chỉ đúng API này, method POST, path /chat được gọi Bridge
resource "aws_lambda_permission" "apigw" {
  statement_id   = "apigw-${var.name}-post-chat"
  action         = "lambda:InvokeFunction"
  function_name  = var.lambda_function_name
  principal      = "apigateway.amazonaws.com"
  source_arn     = "${aws_apigatewayv2_api.this.execution_arn}/*/POST/chat"
  source_account = var.account_id
}
