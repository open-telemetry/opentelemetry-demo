terraform {
  backend "s3" {
    bucket = "demo-terraform-eks-state-bucket-12345"
    key    = "o-tel-demo/terraform.tfstate"
    region = "us-east-1"
    dynamodb_table = "terraform-eks-state-locks"
    encrypt = true
  }
}
