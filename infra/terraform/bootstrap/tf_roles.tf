# ============================================================
# 2 role cho .github/workflows/terraform.yml, xác thực qua OIDC (không access key)
#
#   support-agent-tf-plan  : job `plan` trên Pull Request         → CHỈ ĐỌC (+ ghi file khoá state)
#   support-agent-tf-apply : job `apply` trong environment production → GHI
#
# Tách 2 role (bài học Project 1): role plan assume được từ MỌI PR. Nếu nó ghi được, ai mở PR cũng sửa
# workflow trong PR để `apply` mà bỏ qua bước duyệt. Quyền ghi chỉ lấy được khi job đã vào environment
# production — tức đã có người bấm Approve (Required reviewers).
# ============================================================

# ---------- 1) PLAN ----------
data "aws_iam_policy_document" "tf_plan_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Job chạy trên PR có sub = <prefix>:pull_request
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [for p in local.github_sub_prefixes : "${p}:pull_request"]
    }
  }
}

resource "aws_iam_role" "tf_plan" {
  name                 = "${var.project}-tf-plan"
  description          = "GitHub Actions terraform plan on PRs (read-only)"
  assume_role_policy   = data.aws_iam_policy_document.tf_plan_assume.json
  max_session_duration = 3600
}

# Đọc mọi resource để refresh state + so với code
resource "aws_iam_role_policy_attachment" "tf_plan_readonly" {
  role       = aws_iam_role.tf_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

data "aws_iam_policy_document" "tf_plan_extra" {
  # Ghi DUY NHẤT file khoá state của live/ (use_lockfile tạo/xoá <key>.tflock khi plan)
  statement {
    sid       = "StateLockFile"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["arn:aws:s3:::${var.state_bucket}/${var.live_state_key}.tflock"]
  }
  # ReadOnlyAccess chưa chắc phủ service mới → liệt kê rõ các API đọc AgentCore mà provider gọi khi refresh
  statement {
    sid = "ReadAgentCore"
    actions = [
      "bedrock-agentcore:GetAgentRuntime",
      "bedrock-agentcore:GetAgentRuntimeEndpoint",
      "bedrock-agentcore:ListAgentRuntimes",
      "bedrock-agentcore:ListAgentRuntimeEndpoints",
      "bedrock-agentcore:ListAgentRuntimeVersions",
      "bedrock-agentcore:GetGateway",
      "bedrock-agentcore:ListGateways",
      "bedrock-agentcore:GetGatewayTarget",
      "bedrock-agentcore:ListGatewayTargets",
      "bedrock-agentcore:GetWorkloadIdentity",
      "bedrock-agentcore:ListTagsForResource",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "tf_plan_extra" {
  name   = "${var.project}-tf-plan-extra"
  role   = aws_iam_role.tf_plan.id
  policy = data.aws_iam_policy_document.tf_plan_extra.json
}

# ---------- 2) APPLY ----------
data "aws_iam_policy_document" "tf_apply_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Job có `environment: production` có sub = <prefix>:environment:production
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [for p in local.github_sub_prefixes : "${p}:environment:production"]
    }
  }
}

resource "aws_iam_role" "tf_apply" {
  name                 = "${var.project}-tf-apply"
  description          = "GitHub Actions terraform apply on main after approval"
  assume_role_policy   = data.aws_iam_policy_document.tf_apply_assume.json
  max_session_duration = 3600
}

# Mọi dịch vụ TRỪ IAM/Organizations/Account (S3, DynamoDB, Lambda, API GW, Cognito, Bedrock, AgentCore…)
resource "aws_iam_role_policy_attachment" "tf_apply_poweruser" {
  role       = aws_iam_role.tf_apply.name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

# IAM: chỉ trên role / policy của Project 2 — không phải toàn account, không đụng role của Project 1
data "aws_iam_policy_document" "tf_apply_iam" {
  statement {
    sid     = "ManageProjectIam"
    actions = ["iam:*"]
    resources = [
      # support-agent-runtime, support-gateway, support-get-order-lambda, support-search-policy-lambda, support-chat-bridge
      "arn:aws:iam::${local.account_id}:role/support-*",
      # role + 2 managed policy console tạo cho KB support-policy-kb (Day 51) — đúng hậu tố, không wildcard
      "arn:aws:iam::${local.account_id}:role/service-role/AmazonBedrockExecutionRoleForKnowledgeBase_${var.kb_role_suffix}",
      "arn:aws:iam::${local.account_id}:policy/service-role/AmazonBedrock*PolicyForKnowledgeBase_${var.kb_role_suffix}",
    ]
  }
  # support-* khớp cả 2 role pipeline → CẤM apply tự nới quyền của chính nó / của role plan
  statement {
    sid         = "NoSelfEscalation"
    effect      = "Deny"
    not_actions = ["iam:Get*", "iam:List*"]
    resources   = ["arn:aws:iam::${local.account_id}:role/${var.project}-tf-*"]
  }
  # Đọc managed policy AWS mà role của mình gắn (vd AWSLambdaBasicExecutionRole nếu có)
  statement {
    sid       = "ReadAwsManagedPolicies"
    actions   = ["iam:GetPolicy", "iam:GetPolicyVersion", "iam:ListPolicyVersions"]
    resources = ["arn:aws:iam::aws:policy/*"]
  }
}

resource "aws_iam_role_policy" "tf_apply_iam" {
  name   = "${var.project}-tf-apply-iam"
  role   = aws_iam_role.tf_apply.id
  policy = data.aws_iam_policy_document.tf_apply_iam.json
}
