# ============================================================
# module knowledge_base — KB chính sách loại MANAGED (Day 51, tạo bằng console "quick start").
# Console tự đặt tên role / policy / data source có hậu tố ngẫu nhiên (suffix) → GIỮ NGUYÊN tên:
# đổi tên role hay KB = Terraform xoá rồi tạo lại → KB id mới, phải sync lại, Lambda search_policy vỡ.
# Nội dung (5 file trên S3) + ingestion job (sync) không do Terraform quản.
# ============================================================

locals {
  bucket_arn = "arn:aws:s3:::${var.bucket_name}"
}

# ---------- Role Bedrock dùng để đọc S3 khi sync ----------
data "aws_iam_policy_document" "assume" {
  statement {
    sid     = "TrustPolicyStatement"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [var.account_id]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:bedrock:${var.region}:${var.account_id}:knowledge-base/*"]
    }
  }
}

resource "aws_iam_role" "kb" {
  name               = "AmazonBedrockExecutionRoleForKnowledgeBase_${var.suffix}"
  path               = "/service-role/"
  description        = "Bedrock Knowledge Base access"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

# 2 managed policy console tạo — chỉ đọc đúng bucket chính sách + ghi metric KB
data "aws_iam_policy_document" "s3" {
  statement {
    sid       = "S3ListBucketStatement"
    actions   = ["s3:ListBucket"]
    resources = [local.bucket_arn]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [var.account_id]
    }
  }
  statement {
    sid       = "S3GetObjectStatement"
    actions   = ["s3:GetObject"]
    resources = ["${local.bucket_arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceAccount"
      values   = [var.account_id]
    }
  }
}

resource "aws_iam_policy" "s3" {
  name   = "AmazonBedrockS3PolicyForKnowledgeBase_${var.suffix}"
  path   = "/service-role/"
  policy = data.aws_iam_policy_document.s3.json
}

data "aws_iam_policy_document" "cloudwatch" {
  statement {
    sid       = "CloudWatchWritePermissionStatement"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["AWS/Bedrock/KnowledgeBases"]
    }
  }
}

resource "aws_iam_policy" "cloudwatch" {
  name   = "AmazonBedrockCloudWatchPolicyForKnowledgeBase_${var.suffix}"
  path   = "/service-role/"
  policy = data.aws_iam_policy_document.cloudwatch.json
}

resource "aws_iam_role_policy_attachment" "s3" {
  role       = aws_iam_role.kb.name
  policy_arn = aws_iam_policy.s3.arn
}

resource "aws_iam_role_policy_attachment" "cloudwatch" {
  role       = aws_iam_role.kb.name
  policy_arn = aws_iam_policy.cloudwatch.arn
}

# ---------- Knowledge Base MANAGED: Bedrock tự lo embedding + vector store ----------
resource "aws_bedrockagent_knowledge_base" "this" {
  name     = var.name
  role_arn = aws_iam_role.kb.arn

  knowledge_base_configuration {
    type = "MANAGED"
    managed_knowledge_base_configuration {
      embedding_model_type = "MANAGED"
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

# ---------- Data source: connector S3 trỏ vào bucket chính sách ----------
resource "aws_bedrockagent_data_source" "policies" {
  knowledge_base_id    = aws_bedrockagent_knowledge_base.this.id
  name                 = "knowledge-base-quick-start-${var.suffix}-data-source"
  data_deletion_policy = "DELETE" # xoá data source → xoá luôn vector của nó

  data_source_configuration {
    type = "MANAGED_KNOWLEDGE_BASE_CONNECTOR"
    managed_knowledge_base_connector_configuration {
      connector_parameters = jsonencode({
        type    = "S3"
        version = "1"
        connectionConfiguration = {
          bucketArn            = local.bucket_arn
          bucketName           = var.bucket_name
          bucketOwnerAccountId = var.account_id
        }
        filterConfiguration = { maxFileSizeInMegaBytes = "10240" }
        aclEnabled          = false
      })

      deletion_protection_configuration {
        deletion_protection_status    = "DISABLED"
        deletion_protection_threshold = 15
      }

      media_extraction_configuration {
        audio_extraction_configuration {
          audio_extraction_status = "ENABLED"
        }
        image_extraction_configuration {
          image_extraction_status = "ENABLED"
        }
        video_extraction_configuration {
          video_extraction_status = "ENABLED"
        }
      }
    }
  }

  vector_ingestion_configuration {
    parsing_configuration {
      parsing_strategy = "SMART_PARSING"
    }
  }
}
