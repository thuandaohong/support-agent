variable "function_name" {
  type = string
}

variable "description" {
  type = string
}

variable "role_name" {
  type = string
}

variable "role_description" {
  type = string
}

variable "source_file" {
  description = "Đường dẫn handler.py"
  type        = string
}

variable "timeout" {
  description = "Giây"
  type        = number
}

variable "memory_size" {
  type    = number
  default = 256
}

variable "environment" {
  type    = map(string)
  default = {}
}

variable "policy_statements" {
  description = "Quyền riêng của Lambda (least privilege). Quyền ghi log của chính nó module tự thêm"
  type = list(object({
    sid       = string
    actions   = list(string)
    resources = list(string)
  }))
}

variable "log_retention_days" {
  type = number
}
