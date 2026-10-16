"""Ingestion pipeline: fetch -> parse -> chunk -> write to the data lake.

The data lake layout mirrors the production S3 bucket so the same code runs
locally (DuckDB over local parquet) and in AWS (Athena over S3 parquet):

    <data_dir>/
      markdown/state=TX/city=austin/<section_id>.md
      jsonld/state=TX/city=austin/<chunk_id>.json
      parquet/state=TX/city=austin/chunks.parquet
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
import pyarrow as pa
import pyarrow.parquet as pq

from govmcp_parser.chunker import chunk_text
from govmcp_parser.html_parser import html_to_markdown, split_into_sections
from govmcp_parser.models import Chunk, GroundingMetadata
from govmcp_parser.pdf_parser import parse_pdf, pdf_to_text
from govmcp_parser.sources import SourceDefinition

logger = logging.getLogger(__name__)

USER_AGENT = "GovMCP/0.1 (+https://github.com/daikiito-dk/ZoningMCP)"


def fetch(url: str, timeout: float = 60.0) -> bytes:
    """Fetch a source document over HTTP(S)."""
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        response = client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        return response.content


def build_chunks(
    source: SourceDefinition, raw: bytes
) -> list[Chunk]:
    """Parse a raw document into grounded chunks for one source."""
    if source.format == "pdf":
        sections = parse_pdf(raw, source)
    else:
        markdown = html_to_markdown(
            raw.decode("utf-8", errors="replace"), source.content_selector
        )
        sections = split_into_sections(markdown, source)

    chunks: list[Chunk] = []
    for section_id, title, body in sections:
        metadata = GroundingMetadata(
            state=source.state,
            county_fips=source.county_fips,
            city=source.city,
            section_id=section_id,
            section_title=title,
            effective_date=source.effective_date,
            source_url=source.url,
            document_title=source.document_title,
        )
        for i, text in enumerate(chunk_text(body, source.max_chunk_chars)):
            chunks.append(Chunk(metadata=metadata, text=text, chunk_index=i))
    logger.info("built %d chunks from %d sections", len(chunks), len(sections))
    return chunks


def write_outputs(chunks: list[Chunk], source: SourceDefinition, data_dir: str | Path) -> dict[str, Path]:
    """Write chunks to the local data lake mirror as markdown, JSON-LD, and parquet."""
    data_dir = Path(data_dir)
    partition = f"state={source.state}/city={source.city}"

    md_dir = data_dir / "markdown" / partition
    jsonld_dir = data_dir / "jsonld" / partition
    parquet_dir = data_dir / "parquet" / partition
    for d in (md_dir, jsonld_dir, parquet_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Markdown: one file per section, chunks concatenated with provenance header.
    by_section: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        by_section.setdefault(chunk.metadata.section_id, []).append(chunk)
    for section_id, section_chunks in by_section.items():
        meta = section_chunks[0].metadata
        header = (
            f"---\n"
            f"section_id: {meta.section_id}\n"
            f"section_title: {json.dumps(meta.section_title)}\n"
            f"state: {meta.state}\n"
            f"county_fips: {meta.county_fips}\n"
            f"effective_date: {meta.effective_date or 'unknown'}\n"
            f"source_url: {meta.source_url}\n"
            f"document: {json.dumps(meta.document_title)}\n"
            f"---\n\n"
            f"# {meta.section_id} {meta.section_title}\n\n"
        )
        body = "\n\n".join(c.text for c in section_chunks)
        safe_name = section_id.replace("/", "_")
        (md_dir / f"{safe_name}.md").write_text(header + body, encoding="utf-8")

    # JSON-LD: one file per chunk.
    for chunk in chunks:
        (jsonld_dir / f"{chunk.chunk_id}.json").write_text(
            chunk.to_json(), encoding="utf-8"
        )

    # Parquet: flat table for DuckDB/Athena.
    table = pa.Table.from_pylist([c.to_dict() for c in chunks])
    parquet_path = parquet_dir / "chunks.parquet"
    pq.write_table(table, parquet_path)

    return {"markdown": md_dir, "jsonld": jsonld_dir, "parquet": parquet_path}


def run_source(
    source: SourceDefinition,
    data_dir: str | Path,
    raw: bytes | None = None,
) -> list[Chunk]:
    """Full ingestion run for one source definition."""
    if raw is None:
        logger.info("fetching %s", source.url)
        raw = fetch(source.url)
    chunks = build_chunks(source, raw)
    paths = write_outputs(chunks, source, data_dir)
    logger.info("wrote outputs: %s", {k: str(v) for k, v in paths.items()})
    return chunks
