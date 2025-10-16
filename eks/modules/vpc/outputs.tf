output "vpc_id" {
  description = "VPC ID"
  value = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnet Ids"
  value = aws_subnet.public_subnet[*].id
}

output "private_subnet_ids" {
  description = "Private subnet Ids"
  value = aws_subnet.private_subnet[*].id
}