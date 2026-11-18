# ============================================================
# Nối các module: output của module này là input của module kia → Terraform tự biết thứ tự
# (thay cho các hàm tra id theo tên trong infra/*/_env.sh cũ).
# ============================================================

module "data" {
  source          = "../modules/data"
  orders_table    = var.orders_table
  policies_bucket = local.policies_bucket
  ecr_repo        = var.ecr_repo
}

module "knowledge_base" {
  source      = "../modules/knowledge_base"
  name        = var.kb_name
  suffix      = var.kb_role_suffix
  bucket_name = module.data.policies_bucket_name
  account_id  = local.account_id
  region      = local.region
}

# ---------- 2 tool Lambda sau Gateway (Day 60–61) ----------
module "lambda_get_order" {
  source             = "../modules/lambda_function"
  function_name      = "support-get-order"
  description        = "Tool get_order cho AgentCore Gateway (support-agent)"
  role_name          = "support-get-order-lambda"
  role_description   = "Lambda support-get-order (tool get_order sau AgentCore Gateway)"
  source_file        = "${path.root}/../../../lambdas/get_order/handler.py"
  timeout            = 10
  environment        = { ORDERS_TABLE = module.data.orders_table_name }
  log_retention_days = var.log_retention_days
  policy_statements = [{
    sid       = "OrdersTableReadOne"
    actions   = ["dynamodb:GetItem"] # chỉ đọc 1 đơn theo khoá — không Scan/Query cả bảng
    resources = [module.data.orders_table_arn]
  }]
}

module "lambda_search_policy" {
  source             = "../modules/lambda_function"
  function_name      = "support-search-policy"
  description        = "Tool search_policy cho AgentCore Gateway (support-agent)"
  role_name          = "support-search-policy-lambda"
  role_description   = "Lambda support-search-policy (Tool search_policy cho AgentCore Gateway)"
  source_file        = "${path.root}/../../../lambdas/search_policy/handler.py"
  timeout            = 10
  environment        = { POLICY_KB_ID = module.knowledge_base.id }
  log_retention_days = var.log_retention_days
  policy_statements = [{
    sid       = "PolicyKBRetrieveOnly"
    actions   = ["bedrock:Retrieve"] # chỉ tra đúng 1 KB, không RetrieveAndGenerate (không gọi model)
    resources = [module.knowledge_base.arn]
  }]
}

# ---------- Gateway MCP (Day 60–61) ----------
module "gateway" {
  source      = "../modules/gateway"
  name        = var.gateway_name
  description = "MCP tools cho support-agent (get_order)"
  role_name   = "support-gateway"
  account_id  = local.account_id
  region      = local.region
  targets = {
    orders = {
      lambda_arn       = module.lambda_get_order.function_arn
      description      = "Lambda support-get-order"
      tool_schema_file = "${path.root}/../../gateway/get_order.tool.json"
    }
    policies = {
      lambda_arn       = module.lambda_search_policy.function_arn
      description      = "Lambda support-search-policy"
      tool_schema_file = "${path.root}/../../gateway/search_policy.tool.json"
    }
  }
}

# ---------- AgentCore Runtime (Day 58–62) ----------
module "runtime" {
  source             = "../modules/runtime"
  name               = var.runtime_name
  role_name          = "support-agent-runtime"
  ecr_repository_url = module.data.ecr_repository_url
  ecr_repository_arn = module.data.ecr_repository_arn
  image_tag          = var.image_tag
  model_id           = var.model_id
  gateway_arn        = module.gateway.gateway_arn
  idle_timeout       = var.idle_timeout
  max_lifetime       = var.max_lifetime
  log_retention_days = var.log_retention_days
  account_id         = local.account_id
  region             = local.region
  environment = merge(
    {
      GATEWAY_URL     = module.gateway.gateway_url # Gateway tạo lại → URL mới tự vào đây
      ORDER_BACKEND   = "gateway"
      POLICY_BACKEND  = "gateway"
      ROUTER_MODEL_ID = var.model_id
      WRITER_MODEL_ID = var.model_id
    },
    var.as_of_date == "" ? {} : { AS_OF_DATE = var.as_of_date },
  )
}
