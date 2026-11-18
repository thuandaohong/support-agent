# ============================================================
# module lambda_function — dùng lại cho 3 Lambda: get_order, search_policy (Day 60–61), chat_bridge (Day 64).
# Mỗi Lambda = 1 role riêng + 1 inline policy (quyền truyền vào + ghi log của chính nó) + log group + function.
# Thay cho infra/gateway/01-lambda.sh, 05-policy-lambda.sh, infra/api/01-bridge-lambda.sh.
# ============================================================

# Zip đúng 1 file handler.py (boto3 có sẵn trong Lambda). Đổi code → hash đổi → Terraform deploy lại;
# không đổi → không đụng. Zip nằm trong live/.build (gitignore), CI tự zip lại mỗi lần chạy.
data "archive_file" "code" {
  type        = "zip"
  source_file = var.source_file
  output_path = "${path.root}/.build/${var.function_name}.zip"
}

data "aws_iam_policy_document" "assume" {
  statement {
    sid     = "LambdaAssume"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = var.role_name
  description        = var.role_description
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

# Log group tạo TRƯỚC function, có hạn giữ → role không cần logs:CreateLogGroup
resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "perms" {
  dynamic "statement" {
    for_each = var.policy_statements
    content {
      sid       = statement.value.sid
      actions   = statement.value.actions
      resources = statement.value.resources
    }
  }
  statement {
    sid       = "OwnLogsOnly"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.this.arn}:*"]
  }
}

resource "aws_iam_role_policy" "this" {
  name   = "${var.role_name}-perms"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.perms.json
}

resource "aws_lambda_function" "this" {
  function_name    = var.function_name
  description      = var.description
  role             = aws_iam_role.this.arn
  runtime          = "python3.14"
  architectures    = ["arm64"] # Graviton rẻ hơn x86 ~20%
  handler          = "handler.lambda_handler"
  memory_size      = var.memory_size
  timeout          = var.timeout
  filename         = data.archive_file.code.output_path
  source_code_hash = data.archive_file.code.output_base64sha256

  dynamic "environment" {
    for_each = length(var.environment) > 0 ? [1] : []
    content {
      variables = var.environment
    }
  }

  depends_on = [aws_cloudwatch_log_group.this, aws_iam_role_policy.this]
}
