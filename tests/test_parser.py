"""Tests for the GovMCP parser pipeline (fixture-based, no network)."""

from pathlib import Path

import pytest

from govmcp_parser.chunker import chunk_text
from govmcp_parser.html_parser import html_to_markdown, split_into_sections
from govmcp_parser.pipeline import build_chunks, run_source
from govmcp_parser.sources import SourceDefinition

FIXTURE = Path(__file__).parent / "fixtures" / "austin_sample.html"


@pytest.fixture()
def source() -> SourceDefinition:
    return SourceDefinition(
        city="austin",
        state="TX",
        county_fips="48453",
        document_title="Austin Land Development Code (Code of Ordinances, Title 25)",
        url="https://example.test/austin/title25",
        format="html",
        content_selector="main#code-content",
        section_pattern=r"§\s*(?P<section_id>\d+-\d+-\d+)\.\s*(?P<title>[^\n]+)",
    )


def test_html_to_markdown_preserves_table(source):
    html = FIXTURE.read_text()
    md = html_to_markdown(html, source.content_selector)
    assert "| Standard | CS-1 Requirement |" in md
    assert "60 feet" in md
    assert "Site navigation" not in md  # nav stripped


def test_split_into_sections(source):
    html = FIXTURE.read_text()
    md = html_to_markdown(html, source.content_selector)
    sections = split_into_sections(md, source)
    ids = [s[0] for s in sections]
    assert ids == ["25-2-491", "25-2-492", "25-8-211"]
    assert sections[0][1].startswith("PERMITTED USES")


def test_build_chunks_grounding_metadata(source):
    chunks = build_chunks(source, FIXTURE.read_bytes())
    assert len(chunks) >= 3
    for chunk in chunks:
        assert chunk.metadata.state == "TX"
        assert chunk.metadata.county_fips == "48453"
        assert chunk.metadata.section_id
        assert chunk.metadata.source_url.startswith("https://")
        assert len(chunk.chunk_id) == 16
    # chunk ids are deterministic
    ids_first = [c.chunk_id for c in build_chunks(source, FIXTURE.read_bytes())]
    assert [c.chunk_id for c in chunks] == ids_first


def test_chunk_text_respects_max_and_boundaries():
    text = "\n\n".join(f"Paragraph {i}. " + "lorem ipsum dolor sit amet. " * 10 for i in range(20))
    chunks = chunk_text(text, max_chars=500)
    assert all(len(c) <= 500 or c.startswith("Paragraph") for c in chunks)
    assert "".join(chunks).count("Paragraph") == 20


def test_run_source_writes_data_lake(source, tmp_path):
    chunks = run_source(source, tmp_path, raw=FIXTURE.read_bytes())
    assert (tmp_path / "parquet/state=TX/city=austin/chunks.parquet").exists()
    md_files = list((tmp_path / "markdown/state=TX/city=austin").glob("*.md"))
    assert len(md_files) == 3
    jsonld_files = list((tmp_path / "jsonld/state=TX/city=austin").glob("*.json"))
    assert len(jsonld_files) == len(chunks)
