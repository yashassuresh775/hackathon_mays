# -----------------------------------------------------------------------------
# DATA INGESTION: Glue (optional)
# Data cleaning / ETL. Enable with enable_glue = true.
# -----------------------------------------------------------------------------

resource "aws_glue_catalog_database" "main" {
  count = var.enable_glue ? 1 : 0

  name = "${replace(var.project_name, "-", "_")}_${var.environment}"
}

resource "aws_iam_role" "glue" {
  count = var.enable_glue ? 1 : 0

  name = "${var.project_name}-glue-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  count = var.enable_glue ? 1 : 0

  role       = aws_iam_role.glue[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Upload cleaning script to S3 so Glue job can run
resource "aws_s3_object" "glue_script" {
  count = var.enable_glue ? 1 : 0

  bucket = aws_s3_bucket.source_documents.id
  key    = "glue/scripts/cleaning.py"
  source = "${path.module}/../glue/scripts/cleaning.py"
  etag   = filemd5("${path.module}/../glue/scripts/cleaning.py")
}

# Glue Python shell job: clean/normalize data from uploads for AI consumption
resource "aws_glue_job" "cleaning" {
  count = var.enable_glue ? 1 : 0

  name              = "${var.project_name}-cleaning-job"
  role_arn          = aws_iam_role.glue[0].arn
  glue_version = "4.0"

  command {
    name            = "pythonshell"
    script_location = "s3://${aws_s3_bucket.source_documents.id}/glue/scripts/cleaning.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--job-bookmark-option"              = "job-bookmark-disable"
    "--TempDir"                          = "s3://${aws_s3_bucket.source_documents.id}/glue/temp/"
    "--source_bucket"                    = aws_s3_bucket.source_documents.id
    "--clean_output_prefix"              = "cleaned/"
    "--enable-metrics"                    = "true"
    "--enable-continuous-cloudwatch-log" = "true"
  }

  execution_property {
    max_concurrent_runs = 1
  }
}

# Allow Glue to read/write source bucket
resource "aws_iam_role_policy" "glue_s3" {
  count = var.enable_glue ? 1 : 0

  name   = "${var.project_name}-glue-s3"
  role   = aws_iam_role.glue[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:DeleteObject"]
        Resource = [
          aws_s3_bucket.source_documents.arn,
          "${aws_s3_bucket.source_documents.arn}/*"
        ]
      }
    ]
  })
}
