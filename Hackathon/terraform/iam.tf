# -----------------------------------------------------------------------------
# Orchestrator role (invokes worker Lambdas only)
# -----------------------------------------------------------------------------

resource "aws_iam_role" "orchestrator" {
  name = "${var.project_name}-orchestrator-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "orchestrator_basic" {
  role       = aws_iam_role.orchestrator.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "orchestrator_invoke" {
  name = "${var.project_name}-orchestrator-invoke"
  role = aws_iam_role.orchestrator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = [
          aws_lambda_function.brief_generator.arn,
          aws_lambda_function.document_processor.arn,
          aws_lambda_function.upload_url.arn,
          aws_lambda_function.get_interview.arn,
          aws_lambda_function.packet_response.arn,
          aws_lambda_function.send_packet.arn,
          aws_lambda_function.external_ingest.arn
        ]
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# Lambda execution role (workers: Data Ingestion + Intelligence Generation)
# -----------------------------------------------------------------------------

resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# -----------------------------------------------------------------------------
# Combined policy: S3, DynamoDB, Bedrock, Textract, Comprehend
# -----------------------------------------------------------------------------

resource "aws_iam_role_policy" "lambda_services" {
  name = "${var.project_name}-lambda-services"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject"
        ]
        Resource = [
          aws_s3_bucket.source_documents.arn,
          "${aws_s3_bucket.source_documents.arn}/*",
          aws_s3_bucket.generated_briefs.arn,
          "${aws_s3_bucket.generated_briefs.arn}/*",
          aws_s3_bucket.pre_interview_packets.arn,
          "${aws_s3_bucket.pre_interview_packets.arn}/*"
        ]
      },
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:ConditionCheckItem"
        ]
        Resource = [
          aws_dynamodb_table.interview_metadata.arn,
          "${aws_dynamodb_table.interview_metadata.arn}/index/*",
          aws_dynamodb_table.user_profiles.arn
        ]
      },
      {
        Sid    = "Bedrock"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = ["arn:aws:bedrock:${var.aws_region}::foundation-model/*"]
      },
      {
        Sid    = "Textract"
        Effect = "Allow"
        Action = [
          "textract:DetectDocumentText",
          "textract:StartDocumentAnalysis",
          "textract:GetDocumentAnalysis",
          "textract:StartDocumentTextDetection",
          "textract:GetDocumentTextDetection"
        ]
        Resource = ["*"]
      },
      {
        Sid    = "Comprehend"
        Effect = "Allow"
        Action = [
          "comprehend:DetectEntities",
          "comprehend:DetectKeyPhrases",
          "comprehend:DetectSentiment",
          "comprehend:BatchDetectEntities",
          "comprehend:BatchDetectKeyPhrases"
        ]
        Resource = ["*"]
      },
      {
        Sid    = "Kendra"
        Effect = "Allow"
        Action = ["kendra:Query"]
        Resource = ["*"]
      },
      {
        Sid    = "SES"
        Effect = "Allow"
        Action = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = ["*"]
      },
      {
        Sid    = "InvokeExternalIngest"
        Effect = "Allow"
        Action = ["lambda:InvokeFunction"]
        Resource = [aws_lambda_function.external_ingest.arn]
      }
    ]
  })
}
