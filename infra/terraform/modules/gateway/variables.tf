variable "name" {
  type = string
}

variable "description" {
  type = string
}

variable "role_name" {
  type = string
}

variable "targets" {
  description = "tên target → Lambda + file schema tool (JSON kiểu MCP: name, description, inputSchema)"
  type = map(object({
    lambda_arn       = string
    description      = string
    tool_schema_file = string
  }))
}

variable "account_id" {
  type = string
}

variable "region" {
  type = string
}
