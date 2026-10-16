"""CLI for the GovMCP ingestion pipeline.

Usage:
    govmcp-parse sources/austin_tx.yaml --data-dir data
    govmcp-parse sources/ --data-dir data
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from govmcp_parser.pipeline import run_source
from govmcp_parser.sources import load_source, load_sources


def main() -> None:
    parser = argparse.ArgumentParser(description="GovMCP ingestion pipeline")
    parser.add_argument(
        "source",
        help="Path to a source YAML file, or a directory of source YAML files",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Local data lake mirror directory (default: data/)",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="Parse a local file instead of fetching the source URL",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    source_path = Path(args.source)
    sources = (
        load_sources(source_path) if source_path.is_dir() else [load_source(source_path)]
    )

    raw = Path(args.file).read_bytes() if args.file else None
    total = 0
    for source in sources:
        chunks = run_source(source, args.data_dir, raw=raw)
        print(f"{source.city}: {len(chunks)} chunks from {source.url}")
        total += len(chunks)
    print(f"total: {total} chunks -> {args.data_dir}/")


if __name__ == "__main__":
    main()
