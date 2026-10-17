# GovMCP serverless infrastructure.
#
# NOTE: code only — do not apply without the repository owner's approval.
# Everything here is pay-per-use: S3 storage, Lambda invocations, and
# (optionally) Athena queries. No always-on resources.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ---------------------------------------------------------------------------
# S3 data lake
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "data_lake" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "data_lake" {
  bucket                  = aws_s3_bucket.data_lake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------------------------------------------------------------------------
# IAM
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "govmcp-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda_policy" {
  statement {
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.data_lake.arn, "${aws_s3_bucket.data_lake.arn}/*"]
  }
  statement {
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.data_lake.arn}/*"]
  }
  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "govmcp-lambda"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda_policy.json
}

# ---------------------------------------------------------------------------
# MCP server Lambda (streamable HTTP endpoint via Function URL)
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "server" {
  function_name = "govmcp-server"
  role          = aws_iam_role.lambda.arn
  runtime       = "python3.12"
  handler       = "govmcp_server.lambda_app.handler"
  filename      = var.lambda_package
  timeout       = 60
  memory_size   = 512

  environment {
    variables = {
      GOVMCP_DATA_DIR = "s3://${aws_s3_bucket.data_lake.bucket}"
      AWS_REGION      = var.aws_region
    }
  }
}

resource "aws_lambda_function_url" "server" {
  function_name      = aws_lambda_function.server.function_name
  authorization_type = "NONE" # PoC: public endpoint; add IAM/OIDC before production
}

# ---------------------------------------------------------------------------
# Parser Lambda (weekly ingestion, freshness-aware)
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "parser" {
  function_name = "govmcp-parser"
  role          = aws_iam_role.lambda.arn
  runtime       = "python3.12"
  handler       = "govmcp_parser.lambda_handler.handler"
  filename      = var.lambda_package
  timeout       = 900 # 15 min: large chapters fall back to per-section fetches
  memory_size   = 1024

  environment {
    variables = {
      GOVMCP_BUCKET = aws_s3_bucket.data_lake.bucket
    }
  }
}

resource "aws_cloudwatch_event_rule" "weekly_ingest" {
  name                = "govmcp-weekly-ingest"
  schedule_expression = var.ingest_schedule
}

resource "aws_cloudwatch_event_target" "parser" {
  rule = aws_cloudwatch_event_rule.weekly_ingest.name
  arn  = aws_lambda_function.parser.arn
}

resource "aws_lambda_permission" "eventbridge" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.parser.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_ingest.arn
}
