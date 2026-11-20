# Id/URL đánh dấu sensitive: log plan/apply trên Actions của repo public ai cũng xem được.
# Xem ở máy: terraform output -raw <tên>   (infra/api/03-frontend-env.sh tra theo tên, không cần output)

output "orders_table" {
  value = module.data.orders_table_name
}

output "ecr_repository_url" {
  value     = module.data.ecr_repository_url
  sensitive = true
}

output "kb_id" {
  value     = module.knowledge_base.id
  sensitive = true
}

output "gateway_url" {
  value     = module.gateway.gateway_url
  sensitive = true
}

output "runtime_arn" {
  value     = module.runtime.agent_runtime_arn
  sensitive = true
}

output "user_pool_id" {
  value     = module.auth.pool_id
  sensitive = true
}

output "user_pool_client_id" {
  value     = module.auth.client_id
  sensitive = true
}

output "api_url" {
  value     = module.web_api.api_endpoint
  sensitive = true
}
