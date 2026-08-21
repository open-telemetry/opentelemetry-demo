module "aws_lb_controller_pod_identity" {
  source = "terraform-aws-modules/eks-pod-identity/aws"

  name = "${local.name}-aws-lbc"

  attach_aws_lb_controller_policy = true

  associations = {
    aws_load_balancer_controller = {
      cluster_name    = module.eks.cluster_name
      namespace       = "kube-system"
      service_account = "aws-load-balancer-controller-sa"
    }
  }

  tags = {
    Environment = "dev"
  }
}