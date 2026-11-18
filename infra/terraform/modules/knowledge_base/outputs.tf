output "id" {
  value = aws_bedrockagent_knowledge_base.this.id
}

output "arn" {
  value = aws_bedrockagent_knowledge_base.this.arn
}

output "data_source_id" {
  description = "Cho lệnh sync: aws bedrock-agent start-ingestion-job"
  value       = aws_bedrockagent_data_source.policies.data_source_id
}
