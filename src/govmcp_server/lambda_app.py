"""AWS Lambda entrypoint: GovMCP as a streamable HTTP MCP endpoint.

Exposed through a Lambda Function URL (see infra/terraform). The DuckDB query
layer reads parquet directly from S3 when ``GOVMCP_DATA_DIR`` is an
``s3://`` URI, so no always-on database is involved.

Requires the ``lambda`` extra: ``uv sync --extra lambda``.
"""

from __future__ import annotations

from mangum import Mangum

from govmcp_server.server import mcp

handler = Mangum(mcp.streamable_http_app())
