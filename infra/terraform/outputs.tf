output "mcp_endpoint_url" {
  description = "Streamable HTTP MCP endpoint (point MCP clients here)"
  value       = aws_lambda_function_url.server.function_url
}

output "data_lake_bucket" {
  description = "S3 bucket holding parquet / markdown / jsonld"
  value       = aws_s3_bucket.data_lake.bucket
}

output "parser_lambda" {
  description = "Weekly ingestion Lambda"
  value       = aws_lambda_function.parser.function_name
}
