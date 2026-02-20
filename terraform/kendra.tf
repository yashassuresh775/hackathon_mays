# -----------------------------------------------------------------------------
# DATA INGESTION: Kendra (optional)
# Public + proprietary index for search. Enable with enable_kendra = true.
# -----------------------------------------------------------------------------

resource "aws_kendra_index" "main" {
  count = var.enable_kendra ? 1 : 0

  name        = "${var.project_name}-kendra-${var.environment}"
  description = "Interview AI - Kendra index for public and proprietary content"
  role_arn    = aws_iam_role.kendra[0].arn

  edition = "DEVELOPER_EDITION"

  tags = {
    Name = "Interview AI Kendra"
  }
}

resource "aws_iam_role" "kendra" {
  count = var.enable_kendra ? 1 : 0

  name = "${var.project_name}-kendra-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "kendra.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "kendra" {
  count = var.enable_kendra ? 1 : 0

  role       = aws_iam_role.kendra[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonKendraFullAccess"
}
