output "orders_table_name" {
  value = aws_dynamodb_table.orders.name
}

output "orders_table_arn" {
  value = aws_dynamodb_table.orders.arn
}

output "policies_bucket_name" {
  value = aws_s3_bucket.policies.bucket
}

output "policies_bucket_arn" {
  value = aws_s3_bucket.policies.arn
}

output "ecr_repository_url" {
  value = aws_ecr_repository.agent.repository_url
}

output "ecr_repository_arn" {
  value = aws_ecr_repository.agent.arn
}
