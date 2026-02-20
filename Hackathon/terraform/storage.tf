# -----------------------------------------------------------------------------
# DATA INGESTION & PROCESSING LAYER
# S3 (uploads) <- Textract <- Uploaded Docs
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "source_documents" {
  bucket = "${var.project_name}-source-docs-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "Source documents - uploads"
  }
}

resource "aws_s3_bucket_cors_configuration" "source_documents" {
  count  = var.enable_s3_cors ? 1 : 0
  bucket = aws_s3_bucket.source_documents.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "HEAD"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
  }
}

data "aws_caller_identity" "current" {}

# -----------------------------------------------------------------------------
# STORAGE + OUTPUT LAYER
# DynamoDB (metadata), S3 (generated briefs & packets)
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "generated_briefs" {
  bucket = "${var.project_name}-briefs-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "Generated interviewer briefs"
  }
}

resource "aws_s3_bucket" "pre_interview_packets" {
  bucket = "${var.project_name}-packets-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "Pre-interview packets"
  }
}

# -----------------------------------------------------------------------------
# DynamoDB Tables (metadata)
# -----------------------------------------------------------------------------

resource "aws_dynamodb_table" "interview_metadata" {
  name         = "${var.project_name}-interview-metadata"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "interview_id"

  attribute {
    name = "interview_id"
    type = "S"
  }

  attribute {
    name = "company_name"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "company-name-index"
    hash_key        = "company_name"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  tags = {
    Name = "Interview metadata"
  }
}

resource "aws_dynamodb_table" "user_profiles" {
  name         = "${var.project_name}-user-profiles"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  tags = {
    Name = "User profiles"
  }
}
