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
