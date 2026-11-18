# ============================================================
# module gateway — AgentCore Gateway (MCP server) bọc 2 tool Lambda (Day 60–61).
# Runtime gọi Gateway bằng SigV4 (AWS_IAM); Gateway gọi Lambda bằng role riêng của nó.
# Thay cho infra/gateway/03-gateway.sh, 04-target.sh, 07-policy-target.sh.
# ============================================================

# ---------- Service role: Gateway "mượn" để gọi Lambda ----------
data "aws_iam_policy_document" "assume" {
  statement {
    sid     = "AgentCoreGatewayAssume"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
    # Chống confused deputy: chỉ Gateway tên này trong account này
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [var.account_id]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:bedrock-agentcore:${var.region}:${var.account_id}:gateway/${var.name}-*"]
    }
  }
}

resource "aws_iam_role" "gateway" {
  name               = var.role_name
  description        = "Service role cho AgentCore Gateway ${var.name}"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

data "aws_iam_policy_document" "perms" {
  statement {
    sid       = "InvokeToolLambdasOnly"
    actions   = ["lambda:InvokeFunction"]
    resources = [for t in values(var.targets) : t.lambda_arn]
  }
}

resource "aws_iam_role_policy" "gateway" {
  name   = "${var.role_name}-perms"
  role   = aws_iam_role.gateway.id
  policy = data.aws_iam_policy_document.perms.json
}

# ---------- Gateway ----------
resource "aws_bedrockagentcore_gateway" "this" {
  name            = var.name
  description     = var.description
  protocol_type   = "MCP"
  authorizer_type = "AWS_IAM" # caller ký SigV4; chỉ role có bedrock-agentcore:InvokeGateway gọi được
  role_arn        = aws_iam_role.gateway.arn
}

# ---------- Target: mỗi Lambda = 1 target, tên target thành tiền tố tool (orders___get_order) ----------
locals {
  # Schema tool đọc từ infra/gateway/*.tool.json (một nguồn duy nhất, test cũng đọc file này)
  schemas = { for k, t in var.targets : k => jsondecode(file(t.tool_schema_file)) }
}

resource "aws_bedrockagentcore_gateway_target" "this" {
  for_each = var.targets

  gateway_identifier = aws_bedrockagentcore_gateway.this.gateway_id
  name               = each.key
  description        = each.value.description

  credential_provider_configuration {
    gateway_iam_role {}
  }

  target_configuration {
    mcp {
      lambda {
        lambda_arn = each.value.lambda_arn
        tool_schema {
          inline_payload {
            name        = local.schemas[each.key].name
            description = local.schemas[each.key].description
            input_schema {
              type = local.schemas[each.key].inputSchema.type
              dynamic "property" {
                for_each = local.schemas[each.key].inputSchema.properties
                content {
                  name        = property.key
                  type        = property.value.type
                  description = property.value.description
                  required    = contains(local.schemas[each.key].inputSchema.required, property.key)
                }
              }
            }
          }
        }
      }
    }
  }
}
