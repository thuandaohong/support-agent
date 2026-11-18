output "gateway_id" {
  value = aws_bedrockagentcore_gateway.this.gateway_id
}

output "gateway_arn" {
  value = aws_bedrockagentcore_gateway.this.gateway_arn
}

output "gateway_url" {
  description = "URL MCP — Runtime đọc qua biến môi trường GATEWAY_URL"
  value       = aws_bedrockagentcore_gateway.this.gateway_url
}
