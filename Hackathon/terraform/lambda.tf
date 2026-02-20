# -----------------------------------------------------------------------------
# Orchestrator Lambda (API Gateway → Orchestrator → workers)
# -----------------------------------------------------------------------------

data "archive_file" "orchestrator" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/orchestrator"
  output_path = "${path.module}/build/orchestrator.zip"
}

resource "aws_lambda_function" "orchestrator" {
  filename         = data.archive_file.orchestrator.output_path
  function_name    = "${var.project_name}-orchestrator"
  role             = aws_iam_role.orchestrator.arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.orchestrator.output_base64sha256
  runtime          = "python3.11"
  timeout          = 120
  memory_size      = 256

  environment {
    variables = {
      BRIEF_GENERATOR_FUNCTION    = aws_lambda_function.brief_generator.function_name
      DOCUMENT_PROCESSOR_FUNCTION = aws_lambda_function.document_processor.function_name
      UPLOAD_URL_FUNCTION         = aws_lambda_function.upload_url.function_name
      GET_INTERVIEW_FUNCTION      = aws_lambda_function.get_interview.function_name
      PACKET_RESPONSE_FUNCTION    = aws_lambda_function.packet_response.function_name
      SEND_PACKET_FUNCTION        = aws_lambda_function.send_packet.function_name
      EXTERNAL_INGEST_FUNCTION    = aws_lambda_function.external_ingest.function_name
    }
  }
}

# -----------------------------------------------------------------------------
# Lambda: Brief Generator (Intelligence Generation Layer - Bedrock → brief + packet)
# -----------------------------------------------------------------------------

data "archive_file" "brief_generator" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/brief_generator"
  output_path = "${path.module}/build/brief_generator.zip"
}

resource "aws_lambda_function" "brief_generator" {
  filename         = data.archive_file.brief_generator.output_path
  function_name    = "${var.project_name}-brief-generator"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.brief_generator.output_base64sha256
  runtime          = "python3.11"
  timeout          = var.brief_generator_lambda_timeout
  memory_size      = var.brief_generator_lambda_memory

  environment {
    variables = merge(
      {
        BRIEFS_BUCKET            = aws_s3_bucket.generated_briefs.id
        PACKETS_BUCKET           = aws_s3_bucket.pre_interview_packets.id
        METADATA_TABLE           = aws_dynamodb_table.interview_metadata.name
        SOURCE_BUCKET            = aws_s3_bucket.source_documents.id
        EXTERNAL_INGEST_FUNCTION = aws_lambda_function.external_ingest.function_name
      },
      var.enable_kendra ? { KENDRA_INDEX_ID = aws_kendra_index.main[0].id } : {}
    )
  }
}

# -----------------------------------------------------------------------------
# Lambda: Document Processor (Data Ingestion - S3 + Textract)
# -----------------------------------------------------------------------------

data "archive_file" "document_processor" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/document_processor"
  output_path = "${path.module}/build/document_processor.zip"
}

resource "aws_lambda_function" "document_processor" {
  filename         = data.archive_file.document_processor.output_path
  function_name    = "${var.project_name}-document-processor"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.document_processor.output_base64sha256
  runtime          = "python3.11"
  timeout          = 120
  memory_size      = 256

  environment {
    variables = {
      SOURCE_BUCKET = aws_s3_bucket.source_documents.id
    }
  }
}

# Optional: trigger document processor on S3 upload (disable if Terraform runner lacks s3:GetBucketNotification/s3:PutBucketNotification)
resource "aws_s3_bucket_notification" "source_documents" {
  count  = var.enable_s3_bucket_notification ? 1 : 0
  bucket = aws_s3_bucket.source_documents.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.document_processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "uploads/"
    filter_suffix       = ".pdf"
  }

  depends_on = [aws_lambda_permission.allow_s3_document_processor]
}

resource "aws_lambda_permission" "allow_s3_document_processor" {
  count         = var.enable_s3_bucket_notification ? 1 : 0
  statement_id  = "AllowExecutionFromS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.document_processor.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.source_documents.arn
}

# -----------------------------------------------------------------------------
# Lambda: Upload URL (presigned PUT for document upload)
# -----------------------------------------------------------------------------
data "archive_file" "upload_url" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/upload_url"
  output_path = "${path.module}/build/upload_url.zip"
}
resource "aws_lambda_function" "upload_url" {
  filename         = data.archive_file.upload_url.output_path
  function_name    = "${var.project_name}-upload-url"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.upload_url.output_base64sha256
  runtime          = "python3.11"
  timeout          = 10
  memory_size      = 128
  environment {
    variables = { SOURCE_BUCKET = aws_s3_bucket.source_documents.id }
  }
}

# -----------------------------------------------------------------------------
# Lambda: Get Interview (brief + packet + packet_response)
# -----------------------------------------------------------------------------
data "archive_file" "get_interview" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/get_interview"
  output_path = "${path.module}/build/get_interview.zip"
}
resource "aws_lambda_function" "get_interview" {
  filename         = data.archive_file.get_interview.output_path
  function_name    = "${var.project_name}-get-interview"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.get_interview.output_base64sha256
  runtime          = "python3.11"
  timeout          = 15
  memory_size      = 256
  environment {
    variables = {
      BRIEFS_BUCKET   = aws_s3_bucket.generated_briefs.id
      PACKETS_BUCKET  = aws_s3_bucket.pre_interview_packets.id
      METADATA_TABLE  = aws_dynamodb_table.interview_metadata.name
    }
  }
}

# -----------------------------------------------------------------------------
# Lambda: Packet Response (interviewee corrections + selected questions)
# -----------------------------------------------------------------------------
data "archive_file" "packet_response" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/packet_response"
  output_path = "${path.module}/build/packet_response.zip"
}
resource "aws_lambda_function" "packet_response" {
  filename         = data.archive_file.packet_response.output_path
  function_name    = "${var.project_name}-packet-response"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.packet_response.output_base64sha256
  runtime          = "python3.11"
  timeout          = 10
  memory_size      = 128
  environment {
    variables = { METADATA_TABLE = aws_dynamodb_table.interview_metadata.name }
  }
}

# -----------------------------------------------------------------------------
# Lambda: External Ingest (Google CSE / News API -> S3 raw + kendra_docs for Kendra + Glue)
# -----------------------------------------------------------------------------
data "archive_file" "external_ingest" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/external_ingest"
  output_path = "${path.module}/build/external_ingest.zip"
}
resource "aws_lambda_function" "external_ingest" {
  filename         = data.archive_file.external_ingest.output_path
  function_name    = "${var.project_name}-external-ingest"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.external_ingest.output_base64sha256
  runtime          = "python3.11"
  timeout          = 45
  memory_size      = 256
  environment {
    variables = {
      SOURCE_BUCKET          = aws_s3_bucket.source_documents.id
      GOOGLE_CSE_API_KEY     = var.google_cse_api_key
      GOOGLE_CSE_CX          = var.google_cse_cx
      BING_SUBSCRIPTION_KEY  = var.bing_subscription_key
      NEWS_API_KEY           = var.news_api_key
    }
  }
}

# -----------------------------------------------------------------------------
# Lambda: Send Packet (shareable link + optional email)
# -----------------------------------------------------------------------------
data "archive_file" "send_packet" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/send_packet"
  output_path = "${path.module}/build/send_packet.zip"
}
resource "aws_lambda_function" "send_packet" {
  filename         = data.archive_file.send_packet.output_path
  function_name    = "${var.project_name}-send-packet"
  role             = aws_iam_role.lambda.arn
  handler          = "index.handler"
  source_code_hash = data.archive_file.send_packet.output_base64sha256
  runtime          = "python3.11"
  timeout          = 10
  memory_size      = 128
  environment {
    variables = {
      METADATA_TABLE   = aws_dynamodb_table.interview_metadata.name
      PACKET_BASE_URL  = var.packet_base_url
      SES_FROM_EMAIL   = var.ses_from_email
    }
  }
}
