"""Tests for the DuckDB query layer and MCP tool semantics."""

from pathlib import Path

import pytest

from govmcp_parser.pipeline import run_source
from govmcp_parser.sources import SourceDefinition
from govmcp_server.store import RegulationStore

FIXTURE = Path(__file__).parent / "fixtures" / "austin_sample.html"


@pytest.fixture()
def store(tmp_path):
    source = SourceDefinition(
        city="austin",
        state="TX",
        county_fips="48453",
        document_title="Austin Land Development Code (Code of Ordinances, Title 25)",
        url="https://example.test/austin/title25",
        format="html",
        content_selector="main#code-content",
        section_pattern=r"§\s*(?P<section_id>\d+-\d+-\d+)\.\s*(?P<title>[^\n]+)",
    )
    run_source(source, tmp_path, raw=FIXTURE.read_bytes())
    with RegulationStore(tmp_path) as s:
        yield s


def test_get_zoning_rules(store):
    results = store.get_zoning_rules("austin", "CS-1")
    assert results
    top = results[0]
    assert top["section_id"] in {"25-2-491", "25-2-492"}
    assert "CS-1" in top["text"] or "CS-1" in top["section_title"]
    assert top["source_url"].startswith("https://")


def test_search_environmental_regulations(store):
    results = store.search_environmental_regulations("austin", "drainage")
    assert results
    assert any(r["section_id"] == "25-8-211" for r in results)


def test_search_requires_all_terms(store):
    results = store.search_environmental_regulations("austin", "drainage nonexistentterm")
    assert results == []


def test_verify_source_citation(store):
    results = store.verify_source_citation("25-8-211")
    assert results
    assert results[0]["source_url"] == "https://example.test/austin/title25"
    assert "stormwater" in results[0]["text"]


def test_verify_source_citation_not_found(store):
    assert store.verify_source_citation("99-9-999") == []


def test_list_coverage(store):
    coverage = store.list_coverage()
    assert coverage == [
        {
            "state": "TX",
            "city": "austin",
            "county_fips": "48453",
            "sections": 3,
            "chunks": 3,
        }
    ]
