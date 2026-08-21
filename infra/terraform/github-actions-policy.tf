data "aws_iam_policy_document" "github_actions" {
  statement {
    sid    = "ECRAccess"
    effect = "Allow"

    actions = [
      "ecr:GetAuthorizationToken"
    ]

    resources = ["*"]
  }

  statement {
    sid    = "ECRRepositoryAccess"
    effect = "Allow"

    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer"
    ]

    resources = [
      "arn:aws:ecr:${var.aws_region}:${data.aws_caller_identity.current.account_id}:repository/*"
    ]
  }
}

resource "aws_iam_role_policy" "github_actions_ecr" {
  name = "${local.name}-github-actions-ecr"
  role = aws_iam_role.github_actions.id

  policy = data.aws_iam_policy_document.github_actions.json
}