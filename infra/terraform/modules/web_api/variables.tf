variable "name" {
  type = string
}

variable "allowed_origin" {
  type = string
}

variable "issuer" {
  type = string
}

variable "client_id" {
  type = string
}

variable "client_name" {
  description = "Chỉ để đặt tên authorizer"
  type        = string
}

variable "lambda_arn" {
  type = string
}

variable "lambda_function_name" {
  type = string
}

variable "throttle_rate" {
  type = number
}

variable "throttle_burst" {
  type = number
}

variable "log_retention_days" {
  type = number
}

variable "account_id" {
  type = string
}
