output "role_arn" {
  description = "ARN of the IAM role"
  value       = aws_iam_role.main.arn
}

output "role_name" {
  description = "Name of the IAM role"
  value       = aws_iam_role.main.name
}

output "policy_arn" {
  description = "ARN of the IAM policy"
  value       = aws_iam_policy.main.arn
}

