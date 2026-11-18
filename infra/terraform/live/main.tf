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
