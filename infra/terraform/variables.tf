variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "S3 data lake bucket name (globally unique)"
  type        = string
  default     = "govmcp-data-lake"
}

variable "lambda_package" {
  description = "Path to the Lambda deployment zip (build with scripts/build_lambda.sh)"
  type        = string
  default     = "../../dist/govmcp_lambda.zip"
}

variable "ingest_schedule" {
  description = "EventBridge schedule expression for the weekly ingestion run"
  type        = string
  default     = "rate(7 days)"
}
