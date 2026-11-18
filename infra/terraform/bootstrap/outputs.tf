output "tf_plan_role_arn" {
  description = "→ GitHub secret AWS_TF_PLAN_ROLE_ARN"
  value       = aws_iam_role.tf_plan.arn
}

output "tf_apply_role_arn" {
  description = "→ GitHub secret AWS_TF_APPLY_ROLE_ARN"
  value       = aws_iam_role.tf_apply.arn
}
