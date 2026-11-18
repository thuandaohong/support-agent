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
