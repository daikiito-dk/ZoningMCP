"""AWS Lambda entrypoint for scheduled ingestion (EventBridge weekly).

Runs every configured source, writing the data lake to a local temp dir and
syncing it to the S3 bucket. The freshness state file is downloaded before
and uploaded after the run so unchanged sources are skipped across
invocations (see issue #2).

Environment variables:
    GOVMCP_BUCKET        data lake bucket name (required)
    GOVMCP_SOURCES_DIR   directory of source YAML files in the deployment
                         package (default: sources)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import boto3

from govmcp_parser.pipeline import run_source
from govmcp_parser.sources import load_sources
from govmcp_parser.state import STATE_FILENAME

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TMP_DATA_DIR = "/tmp/govmcp-data"


def _download_state(s3: Any, bucket: str, dest: Path) -> None:
    try:
        s3.download_file(bucket, STATE_FILENAME, str(dest))
        logger.info("restored freshness state from s3://%s/%s", bucket, STATE_FILENAME)
    except s3.exceptions.ClientError:
        logger.info("no existing freshness state in bucket")


def handler(event: dict, context: Any) -> dict:
    bucket = os.environ["GOVMCP_BUCKET"]
    sources_dir = os.environ.get("GOVMCP_SOURCES_DIR", "sources")
    data_dir = Path(TMP_DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    s3 = boto3.client("s3")

    _download_state(s3, bucket, data_dir / STATE_FILENAME)

    results = []
    for source in load_sources(sources_dir):
        chunks = run_source(source, data_dir)
        status = "skipped" if chunks is None else f"{len(chunks)} chunks"
        results.append({"source": f"{source.state}/{source.city}", "status": status})
        logger.info("%s/%s: %s", source.state, source.city, status)

    uploaded = 0
    for path in data_dir.rglob("*"):
        if path.is_file():
            s3.upload_file(str(path), bucket, str(path.relative_to(data_dir)))
            uploaded += 1
    logger.info("uploaded %d files to s3://%s", uploaded, bucket)
    return {"sources": results, "uploaded_files": uploaded}
