data "aws_iam_policy_document" "breakglass_deploy" {
  statement {
    effect = "Allow"
    actions = [
      "iam:*",
      "sts:AssumeRole"
    ]
    resources = ["*"]
  }

  statement {
    effect = "Allow"
    actions = ["s3:GetObject", "logs:GetLogEvents"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "key_admin" {
  name = "prod-key-admin"
  policy = jsonencode({
    Statement = [{
      Effect   = "Allow"
      Action   = "kms:*"
      Resource = "*"
    }]
  })
}
