# Cấu hình hạ tầng support-agent — KHÔNG bí mật, KHÔNG id (repo public).
# Id ngẫu nhiên do AWS sinh (pool, KB, gateway…) không nằm ở đây: Terraform giữ trong state.

aws_region         = "us-east-1"
log_retention_days = 14

orders_table           = "support-orders"
policies_bucket_prefix = "support-agent-policies"
ecr_repo               = "support-agent"

kb_name        = "support-policy-kb"
kb_role_suffix = "1uz0d"

gateway_name = "support-gateway"

runtime_name = "support_agent"
image_tag    = "a83ee77" # Day 62 bước 6
model_id     = "amazon.nova-lite-v1:0"
as_of_date   = "2026-11-08" # demo / eval khớp dữ liệu mẫu
idle_timeout = 300
max_lifetime = 1800

pool_name   = "support-users"
client_name = "support-web"

api_name       = "support-chat-api"
allowed_origin = "http://localhost:5173"
throttle_rate  = 5
throttle_burst = 10
