# -----------------------------------------------------------------------------
# API Gateway (User -> Amplify -> API Gateway -> Orchestrator)
# -----------------------------------------------------------------------------

resource "aws_apigatewayv2_api" "main" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"
  description   = "Interview AI - generate briefs and process documents"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["content-type", "authorization"]
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
}

# -----------------------------------------------------------------------------
# All routes -> Orchestrator Lambda (dispatches to workers)
# -----------------------------------------------------------------------------

resource "aws_apigatewayv2_integration" "orchestrator" {
  api_id                  = aws_apigatewayv2_api.main.id
  integration_type        = "AWS_PROXY"
  integration_uri         = aws_lambda_function.orchestrator.invoke_arn
  integration_method      = "POST"
  payload_format_version  = "2.0"
}

resource "aws_apigatewayv2_route" "generate_brief" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /generate-brief"
  target    = "integrations/${aws_apigatewayv2_integration.orchestrator.id}"
}

resource "aws_apigatewayv2_route" "extract_document" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /extract-document"
  target    = "integrations/${aws_apigatewayv2_integration.orchestrator.id}"
}

resource "aws_apigatewayv2_route" "ingest_external" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /ingest-external"
  target    = "integrations/${aws_apigatewayv2_integration.orchestrator.id}"
}

resource "aws_apigatewayv2_route" "upload_url" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /upload-url"
  target    = "integrations/${aws_apigatewayv2_integration.orchestrator.id}"
}

resource "aws_apigatewayv2_route" "send_packet" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /send-packet"
  target    = "integrations/${aws_apigatewayv2_integration.orchestrator.id}"
}

resource "aws_apigatewayv2_route" "get_interview" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /interview/{id}"
  target    = "integrations/${aws_apigatewayv2_integration.orchestrator.id}"
}

resource "aws_apigatewayv2_route" "packet_response" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /interview/{id}/packet-response"
  target    = "integrations/${aws_apigatewayv2_integration.orchestrator.id}"
}

resource "aws_lambda_permission" "api_orchestrator" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.orchestrator.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

