data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "github_actions_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type = "Federated"

      identifiers = [
        "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
      ]
    }

    actions = [
      "sts:AssumeRoleWithWebIdentity"
    ]

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"

      values = [
        "sts.amazonaws.com"
      ]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"

      values = [
        "repo:SanthoshKumar1903/opentelemetry-demo-project:*"
      ]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name = "${local.name}-github-actions"

  assume_role_policy = data.aws_iam_policy_document.github_actions_assume_role.json

  tags = {
    Environment = "dev"
    Purpose     = "GitHub Actions CI/CD"
  }
}

data "aws_iam_policy_document" "github_actions_eks" {
  statement {
    sid    = "DescribeEKSCluster"
    effect = "Allow"

    actions = [
      "eks:DescribeCluster"
    ]

    resources = [
      module.eks.cluster_arn
    ]
  }
}

resource "aws_iam_role_policy" "github_actions_eks" {
  name = "${local.name}-github-actions-eks"
  role = aws_iam_role.github_actions.id

  policy = data.aws_iam_policy_document.github_actions_eks.json
}