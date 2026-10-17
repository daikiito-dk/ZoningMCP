"""CLI entrypoint for the GovMCP server.

Usage:
    govmcp-serve --data-dir data          # stdio MCP transport
    govmcp-serve --coverage --data-dir data   # print ingested coverage
"""

from __future__ import annotations

import argparse

from govmcp_server.store import RegulationStore


def main() -> None:
    parser = argparse.ArgumentParser(description="GovMCP MCP server")
    parser.add_argument("--data-dir", default="data", help="Data lake mirror directory")
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Print ingested coverage summary and exit (no server)",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="MCP transport: stdio (default) or streamable HTTP",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP transport bind host")
    parser.add_argument("--port", type=int, default=8000, help="HTTP transport port")
    args = parser.parse_args()

    if args.coverage:
        with RegulationStore(args.data_dir) as store:
            for row in store.list_coverage():
                print(
                    f"{row['state']}/{row['city']} (FIPS {row['county_fips']}): "
                    f"{row['sections']} sections, {row['chunks']} chunks"
                )
        return

    from govmcp_server.server import main as serve

    serve(data_dir=args.data_dir, transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
