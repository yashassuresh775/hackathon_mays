output "source_documents_bucket_name" {
  description = "S3 bucket for uploaded source documents"
  value       = aws_s3_bucket.source_documents.id
}

output "generated_briefs_bucket_name" {
  description = "S3 bucket for generated interviewer briefs"
  value       = aws_s3_bucket.generated_briefs.id
}

output "pre_interview_packets_bucket_name" {
  description = "S3 bucket for pre-interview packets"
  value       = aws_s3_bucket.pre_interview_packets.id
}

output "interview_metadata_table_name" {
  description = "DynamoDB table for interview metadata"
  value       = aws_dynamodb_table.interview_metadata.name
}

output "api_gateway_url" {
  description = "HTTP API Gateway invoke URL"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "api_gateway_id" {
  description = "API Gateway API ID"
  value       = aws_apigatewayv2_api.main.id
}

output "generate_brief_invoke_url" {
  description = "Full URL for POST /generate-brief"
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/generate-brief"
}

output "orchestrator_function_name" {
  description = "Orchestrator Lambda function name"
  value       = aws_lambda_function.orchestrator.function_name
}

output "extract_document_invoke_url" {
  description = "Full URL for POST /extract-document"
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/extract-document"
}

output "upload_url_invoke_url" {
  description = "Full URL for POST /upload-url (presigned upload)"
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/upload-url"
}

output "send_packet_invoke_url" {
  description = "Full URL for POST /send-packet"
  value       = "${aws_apigatewayv2_api.main.api_endpoint}/send-packet"
}
