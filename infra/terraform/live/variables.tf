# Giá trị đặt trong terraform.tfvars (không bí mật — thay cho các file infra/*/*.env cũ)

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "log_retention_days" {
  description = "Số ngày giữ log CloudWatch của Lambda, Runtime, API"
  type        = number
  default     = 14
}

# ---------- dữ liệu (Day 51, 53, 58) ----------
variable "orders_table" {
  type = string
}

variable "policies_bucket_prefix" {
  description = "Tên bucket chính sách = <prefix>-<account id>"
  type        = string
}

variable "ecr_repo" {
  type = string
}

# ---------- Knowledge Base (Day 51 — tạo bằng console) ----------
variable "kb_name" {
  type = string
}

variable "kb_role_suffix" {
  description = "Hậu tố ngẫu nhiên console gán cho role + policy + data source của KB"
  type        = string
}

# ---------- Gateway + tool Lambda (Day 60–61) ----------
variable "gateway_name" {
  type = string
}

# ---------- Runtime (Day 58–62) ----------
variable "runtime_name" {
  description = "Chỉ chữ, số, '_' (AgentCore không nhận '-')"
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_]*$", var.runtime_name))
    error_message = "runtime_name chỉ được chữ, số, '_'."
  }
}

variable "image_tag" {
  description = "Git SHA của image trên ECR mà Runtime chạy. Đổi image = sửa giá trị này qua PR"
  type        = string
}

variable "model_id" {
  description = "Model router + writer — role Runtime chỉ được gọi đúng model này"
  type        = string
}

variable "as_of_date" {
  description = "\"Hôm nay\" cho luật đổi trả (khớp dữ liệu mẫu). Để trống = ngày thật"
  type        = string
  default     = ""
}

variable "idle_timeout" {
  description = "Session rảnh bao lâu thì tắt (giây)"
  type        = number
  default     = 300
}

variable "max_lifetime" {
  description = "Session sống tối đa (giây)"
  type        = number
  default     = 1800
}

# ---------- Cognito (Day 63) ----------
variable "pool_name" {
  type = string
}

variable "client_name" {
  type = string
}

# ---------- Web (Day 64) ----------
variable "api_name" {
  type = string
}

variable "allowed_origin" {
  description = "Origin duy nhất được gọi API từ trình duyệt"
  type        = string
}

variable "throttle_rate" {
  description = "req/giây cho cả API (cộng chung mọi người dùng)"
  type        = number
}

variable "throttle_burst" {
  type = number
}

# ---------- import (Day 65, xoá cùng imports.tf) ----------
variable "import_ids" {
  description = "Id ngẫu nhiên của resource đang chạy, do import-ids.sh tra theo tên (file gitignore)"
  type        = map(string)
  default     = {}
}
