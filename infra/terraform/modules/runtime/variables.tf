variable "name" {
  type = string
}

variable "role_name" {
  type = string
}

variable "ecr_repository_url" {
  type = string
}

variable "ecr_repository_arn" {
  type = string
}

variable "image_tag" {
  type = string
}

variable "model_id" {
  type = string
}

variable "gateway_arn" {
  type = string
}

variable "environment" {
  description = "Biến môi trường cho serve.py (GATEWAY_URL, model, backend, AS_OF_DATE)"
  type        = map(string)
}

variable "idle_timeout" {
  type = number
}

variable "max_lifetime" {
  type = number
}

variable "log_retention_days" {
  type = number
}

variable "account_id" {
  type = string
}

variable "region" {
  type = string
}
