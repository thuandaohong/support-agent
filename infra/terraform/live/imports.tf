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

# ---------- module.runtime ----------
import {
  to = module.runtime.aws_iam_role.runtime
  id = "support-agent-runtime"
}

import {
  to = module.runtime.aws_iam_role_policy.runtime
  id = "support-agent-runtime:support-agent-runtime-perms"
}

import {
  to = module.runtime.aws_bedrockagentcore_agent_runtime.this
  id = var.import_ids["runtime"]
}

import {
  to = module.runtime.aws_cloudwatch_log_group.runtime
  id = "/aws/bedrock-agentcore/runtimes/${var.import_ids["runtime"]}-DEFAULT"
}

# ---------- module.auth ----------
import {
  to = module.auth.aws_cognito_user_pool.this
  id = var.import_ids["pool"]
}

import {
  to = module.auth.aws_cognito_user_pool_client.web
  id = "${var.import_ids["pool"]}/${var.import_ids["client"]}"
}

# ---------- module.lambda_bridge ----------
import {
  to = module.lambda_bridge.aws_iam_role.this
  id = "support-chat-bridge"
}

import {
  to = module.lambda_bridge.aws_iam_role_policy.this
  id = "support-chat-bridge:support-chat-bridge-perms"
}

import {
  to = module.lambda_bridge.aws_cloudwatch_log_group.this
  id = "/aws/lambda/support-chat-bridge"
}

import {
  to = module.lambda_bridge.aws_lambda_function.this
  id = "support-chat-bridge"
}

# ---------- module.web_api ----------
import {
  to = module.web_api.aws_apigatewayv2_api.this
  id = var.import_ids["api"]
}

import {
  to = module.web_api.aws_apigatewayv2_authorizer.jwt
  id = "${var.import_ids["api"]}/${var.import_ids["authorizer"]}"
}

import {
  to = module.web_api.aws_apigatewayv2_integration.bridge
  id = "${var.import_ids["api"]}/${var.import_ids["integration"]}"
}

import {
  to = module.web_api.aws_apigatewayv2_route.chat
  id = "${var.import_ids["api"]}/${var.import_ids["route"]}"
}

import {
  to = module.web_api.aws_cloudwatch_log_group.access
  id = "/aws/apigateway/${var.api_name}"
}

import {
  to = module.web_api.aws_apigatewayv2_stage.default
  id = "${var.import_ids["api"]}/$default"
}

import {
  to = module.web_api.aws_lambda_permission.apigw
  id = "support-chat-bridge/apigw-${var.api_name}-post-chat"
}
