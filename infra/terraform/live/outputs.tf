output "orders_table" {
  value = module.data.orders_table_name
}

output "ecr_repository_url" {
  value     = module.data.ecr_repository_url
  sensitive = true # chứa account id
}

output "kb_id" {
  value     = module.knowledge_base.id
  sensitive = true # repo public: plan/apply log trên Actions ai cũng xem được
}
