# Secrets Module: Manages secrets in AWS Secrets Manager

resource "aws_secretsmanager_secret" "main" {
  for_each = var.secrets
  
  name        = "${var.secrets_prefix}/${each.key}"
  description = each.value.description
  
  tags = merge(
    var.tags,
    {
      Name = "${var.secrets_prefix}/${each.key}"
    }
  )
}

resource "aws_secretsmanager_secret_version" "main" {
  for_each = var.secrets
  
  secret_id     = aws_secretsmanager_secret.main[each.key].id
  secret_string = jsonencode(each.value.secret_data)
}

