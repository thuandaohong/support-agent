# ============================================================
# Day 65 — nhận resource ĐANG CHẠY (tạo bằng CLI/console các ngày trước) vào state, KHÔNG tạo lại.
# Import chỉ thành thật khi CI apply (sau Approve). Id ngẫu nhiên lấy từ var.import_ids (import-ids.sh).
# XOÁ file này (và import-ids.sh, var.import_ids) sau khi apply xong và plan = No changes.
# ============================================================

# ---------- module.data ----------
import {
  to = module.data.aws_dynamodb_table.orders
  id = var.orders_table
}

import {
  to = module.data.aws_s3_bucket.policies
  id = local.policies_bucket
}

import {
  to = module.data.aws_s3_bucket_public_access_block.policies
  id = local.policies_bucket
}

import {
  to = module.data.aws_ecr_repository.agent
  id = var.ecr_repo
}

import {
  to = module.data.aws_ecr_lifecycle_policy.agent
  id = var.ecr_repo
}

# ---------- module.knowledge_base ----------
import {
  to = module.knowledge_base.aws_iam_role.kb
  id = "AmazonBedrockExecutionRoleForKnowledgeBase_${var.kb_role_suffix}"
}

import {
  to = module.knowledge_base.aws_iam_policy.s3
  id = "arn:aws:iam::${local.account_id}:policy/service-role/AmazonBedrockS3PolicyForKnowledgeBase_${var.kb_role_suffix}"
}

import {
  to = module.knowledge_base.aws_iam_policy.cloudwatch
  id = "arn:aws:iam::${local.account_id}:policy/service-role/AmazonBedrockCloudWatchPolicyForKnowledgeBase_${var.kb_role_suffix}"
}

import {
  to = module.knowledge_base.aws_iam_role_policy_attachment.s3
  id = "AmazonBedrockExecutionRoleForKnowledgeBase_${var.kb_role_suffix}/arn:aws:iam::${local.account_id}:policy/service-role/AmazonBedrockS3PolicyForKnowledgeBase_${var.kb_role_suffix}"
}

import {
  to = module.knowledge_base.aws_iam_role_policy_attachment.cloudwatch
  id = "AmazonBedrockExecutionRoleForKnowledgeBase_${var.kb_role_suffix}/arn:aws:iam::${local.account_id}:policy/service-role/AmazonBedrockCloudWatchPolicyForKnowledgeBase_${var.kb_role_suffix}"
}

import {
  to = module.knowledge_base.aws_bedrockagent_knowledge_base.this
  id = var.import_ids["kb"]
}

import {
  to = module.knowledge_base.aws_bedrockagent_data_source.policies
  id = "${var.import_ids["kb_ds"]},${var.import_ids["kb"]}"
}

# ---------- module.lambda_get_order / module.lambda_search_policy ----------
import {
  to = module.lambda_get_order.aws_iam_role.this
  id = "support-get-order-lambda"
}

import {
  to = module.lambda_get_order.aws_iam_role_policy.this
  id = "support-get-order-lambda:support-get-order-lambda-perms"
}

import {
  to = module.lambda_get_order.aws_cloudwatch_log_group.this
  id = "/aws/lambda/support-get-order"
}

import {
  to = module.lambda_get_order.aws_lambda_function.this
  id = "support-get-order"
}

import {
  to = module.lambda_search_policy.aws_iam_role.this
  id = "support-search-policy-lambda"
}

import {
  to = module.lambda_search_policy.aws_iam_role_policy.this
  id = "support-search-policy-lambda:support-search-policy-lambda-perms"
}

import {
  to = module.lambda_search_policy.aws_cloudwatch_log_group.this
  id = "/aws/lambda/support-search-policy"
}

import {
  to = module.lambda_search_policy.aws_lambda_function.this
  id = "support-search-policy"
}

# ---------- module.gateway ----------
import {
  to = module.gateway.aws_iam_role.gateway
  id = "support-gateway"
}

import {
  to = module.gateway.aws_iam_role_policy.gateway
  id = "support-gateway:support-gateway-perms"
}

import {
  to = module.gateway.aws_bedrockagentcore_gateway.this
  id = var.import_ids["gateway"]
}

import {
  to = module.gateway.aws_bedrockagentcore_gateway_target.this["orders"]
  id = "${var.import_ids["gateway"]},${var.import_ids["target_orders"]}"
}

import {
  to = module.gateway.aws_bedrockagentcore_gateway_target.this["policies"]
  id = "${var.import_ids["gateway"]},${var.import_ids["target_policies"]}"
}
