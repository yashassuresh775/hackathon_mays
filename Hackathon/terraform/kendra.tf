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

# Kendra role must read from S3 (external ingest + cleaned uploads)
resource "aws_iam_role_policy" "kendra_s3" {
  count = var.enable_kendra ? 1 : 0

  name   = "${var.project_name}-kendra-s3"
  role   = aws_iam_role.kendra[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.source_documents.arn,
          "${aws_s3_bucket.source_documents.arn}/external/*",
          "${aws_s3_bucket.source_documents.arn}/cleaned/*"
        ]
      }
    ]
  })
}

# S3 data source: external/kendra_docs (ingest + Glue) and cleaned/ (uploads)
resource "aws_kendra_data_source" "s3_docs" {
  count = var.enable_kendra ? 1 : 0

  index_id   = aws_kendra_index.main[0].id
  name       = "${var.project_name}-s3-docs-${var.environment}"
  type       = "S3"
  role_arn   = aws_iam_role.kendra[0].arn
  description = "S3 docs: external ingest (Google/News) + cleaned uploads for Kendra search"

  configuration {
    s3_configuration {
      bucket_name         = aws_s3_bucket.source_documents.id
      inclusion_prefixes  = ["external/kendra_docs/", "cleaned/"]
    }
  }
}
