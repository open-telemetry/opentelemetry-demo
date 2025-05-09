resource "aws_s3_bucket" "statefile-s3-bucket" {
  bucket = "demo-terraform-eks-state-bucket-12345"
    lifecycle {
      prevent_destroy = false
    }
}

resource "aws_dynamodb_table" "lock-dynamodb" {
  name             = "terraform-eks-state-locks"
  hash_key         = "LockID"
  billing_mode     = "PAY_PER_REQUEST"


  attribute {
    name = "LockID"
    type = "S"
  }
}