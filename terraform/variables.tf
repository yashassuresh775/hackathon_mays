variable "aws_region" {
  description = "AWS region for most resources (Lambda, API Gateway, source_documents S3)"
  type        = string
  default     = "us-east-1"
}

variable "aws_region_west" {
  description = "Region for briefs/packets S3 buckets when they live in us-west-2"
  type        = string
  default     = "us-west-2"
}

variable "project_name" {
  description = "Project name used in resource naming"
  type        = string
  default     = "interview-ai"
}

variable "environment" {
  description = "Environment (e.g. dev, hackathon)"
  type        = string
  default     = "hackathon"
}

variable "brief_generator_lambda_memory" {
  description = "Memory in MB for brief generator Lambda"
  type        = number
  default     = 512
}

variable "brief_generator_lambda_timeout" {
  description = "Timeout in seconds for brief generator Lambda"
  type        = number
  default     = 120
}

# Optional architecture components (tune to your architecture)
variable "enable_kendra" {
  description = "Enable Amazon Kendra index for search (public + proprietary)"
  type        = bool
  default     = false
}

variable "enable_glue" {
  description = "Enable Glue for data cleaning / ETL"
  type        = bool
  default     = false
}

variable "enable_amplify" {
  description = "Enable Amplify app for frontend (Student/Faculty)"
  type        = bool
  default     = false
}

variable "packet_base_url" {
  description = "Base URL for shareable packet links (e.g. https://yourapp.amplifyapp.com)"
  type        = string
  default     = ""
}

variable "ses_from_email" {
  description = "Verified SES sender email for sending packet link (optional)"
  type        = string
  default     = ""
}
