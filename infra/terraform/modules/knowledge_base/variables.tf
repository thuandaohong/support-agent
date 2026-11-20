variable "name" {
  type = string
}

variable "suffix" {
  description = "Hậu tố ngẫu nhiên console gán (role, policy, data source)"
  type        = string
}

variable "bucket_name" {
  description = "Bucket chứa file chính sách (module data)"
  type        = string
}

variable "account_id" {
  type = string
}

variable "region" {
  type = string
}
