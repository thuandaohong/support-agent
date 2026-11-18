# ============================================================
# module runtime — AgentCore Runtime chạy image agent (Day 58–62) + execution role + log group.
# Thay cho infra/runtime/01-create-role.sh, 02-create-runtime.sh, 05-update-image.sh, 07-log-retention.sh.
# Đổi image = sửa var.image_tag qua PR → Terraform update-agent-runtime (ARN giữ nguyên, version +1).
# ============================================================

locals {
  arn_prefix = "arn:aws:bedrock-agentcore:${var.region}:${var.account_id}"
}

# ---------- Execution role: Runtime "mượn" để kéo image, ghi log, gọi model + Gateway ----------
data "aws_iam_policy_document" "assume" {
  statement {
    sid     = "AgentCoreRuntimeAssume"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
    # Chống confused deputy (Day 63): đúng account + đúng Runtime tên này
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [var.account_id]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["${local.arn_prefix}:runtime/${var.name}-*"]
    }
  }
}

resource "aws_iam_role" "runtime" {
  name               = var.role_name
  description        = "Execution role cho AgentCore Runtime ${var.name}"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

data "aws_iam_policy_document" "perms" {
  statement {
    sid       = "EcrPullThisRepo"
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    resources = [var.ecr_repository_arn]
  }
  statement {
    sid       = "EcrToken"
    actions   = ["ecr:GetAuthorizationToken"] # API này không giới hạn theo resource được
    resources = ["*"]
  }
  statement {
    sid       = "LogsGroup"
    actions   = ["logs:DescribeLogStreams", "logs:CreateLogGroup"]
    resources = ["arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"]
  }
  statement {
    sid       = "LogsDescribe"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["arn:aws:logs:${var.region}:${var.account_id}:log-group:*"]
  }
  statement {
    sid       = "LogsWrite"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"]
  }
  statement {
    sid       = "XRay"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"]
    resources = ["*"]
  }
  statement {
    sid       = "Metrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["bedrock-agentcore"]
    }
  }
  statement {
    sid       = "AppModelOnly"
    actions   = ["bedrock:InvokeModel"]
    resources = ["arn:aws:bedrock:${var.region}::foundation-model/${var.model_id}"]
  }
  statement {
    sid       = "AppGatewayInvoke"
    actions   = ["bedrock-agentcore:InvokeGateway"]
    resources = [var.gateway_arn]
  }
}

resource "aws_iam_role_policy" "runtime" {
  name   = "${var.role_name}-perms"
  role   = aws_iam_role.runtime.id
  policy = data.aws_iam_policy_document.perms.json
}

# ---------- Runtime ----------
resource "aws_bedrockagentcore_agent_runtime" "this" {
  agent_runtime_name    = var.name
  description           = "support-agent (LangGraph) image ${var.image_tag}"
  role_arn              = aws_iam_role.runtime.arn
  environment_variables = var.environment

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${var.ecr_repository_url}:${var.image_tag}"
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  lifecycle_configuration = [{
    idle_runtime_session_timeout = var.idle_timeout
    max_lifetime                 = var.max_lifetime
  }]

  # Policy phải có trước khi Runtime khởi động microVM (kéo image, ghi log)
  depends_on = [aws_iam_role_policy.runtime]
}

# Log group do AgentCore tự tạo khi Runtime ghi log lần đầu (tên có runtime id) → ở đây quản hạn giữ.
# Lưu ý dựng mới từ đầu: nếu Runtime đã kịp tạo log group trước, phải import thay vì tạo.
resource "aws_cloudwatch_log_group" "runtime" {
  name              = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.this.agent_runtime_id}-DEFAULT"
  retention_in_days = var.log_retention_days
}
