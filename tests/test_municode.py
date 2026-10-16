"""Tests for the Municode fetcher (fixture-based, no network)."""

import json
from pathlib import Path

import pytest

from govmcp_parser.municode import (
    MunicodeClient,
    chapter_nodes,
    docs_to_sections,
)
from govmcp_parser.pipeline import build_chunks
from govmcp_parser.sources import SourceDefinition

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def tree():
    return json.loads((FIXTURES / "municode_tree.json").read_text())


@pytest.fixture()
def docs():
    return json.loads((FIXTURES / "municode_codes_content.json").read_text())["Docs"]


def test_chapter_nodes_filters_by_heading(tree):
    chapters = chapter_nodes(tree, ["25-8"])
    assert [c["Id"] for c in chapters] == ["TIT25LADE_CH25-8EN"]
    assert chapter_nodes(tree, ["99-1"]) == []


def test_docs_to_sections_extracts_and_dedupes(docs):
    seen = set()
    sections = docs_to_sections(docs, lambda nid: f"https://example.test/{nid}", seen)
    ids = [s.section_id for s in sections]
    assert "25-8-1" in ids
    assert len(ids) == len(set(ids))  # no duplicates
    s1 = next(s for s in sections if s.section_id == "25-8-1")
    assert s1.title.startswith("DEFINITIONS")
    assert "APPLICANT means a person" in s1.body  # HTML converted to markdown text
    assert s1.source_url.startswith("https://example.test/")


def test_docs_to_sections_skips_non_section_docs(docs):
    sections = docs_to_sections(docs, lambda nid: "", set())
    assert all(s.section_id for s in sections)
    assert not any("CHAPTER" in s.title for s in sections)


def test_build_chunks_with_municode_format(docs, monkeypatch):
    source = SourceDefinition(
        city="austin",
        state="TX",
        county_fips="48453",
        document_title="Austin Land Development Code (Title 25)",
        url="https://library.municode.com/tx/austin/codes/land_development_code",
        format="municode",
        municode={
            "state_abbr": "TX",
            "client_name": "Austin",
            "product_name": "Land Development Code",
            "include_chapters": ["25-8"],
        },
    )

    class FakeClient(MunicodeClient):
        def __init__(self, **kwargs):
            pass  # no network

        def close(self):
            pass

        def find_client_id(self, state_abbr, client_name):
            return 1113

        def find_product_id(self, client_id, product_name):
            return 15303

        def get_tree(self, product_id, node_id=None):
            return json.loads((FIXTURES / "municode_tree.json").read_text())

        def get_content_docs(self, product_id, node_id):
            return docs

    monkeypatch.setattr("govmcp_parser.municode.MunicodeClient", FakeClient)
    chunks = build_chunks(source)
    assert chunks
    assert all(c.metadata.state == "TX" for c in chunks)
    assert {c.metadata.section_id for c in chunks} >= {"25-8-1"}
    assert "nodeId=" in chunks[0].metadata.source_url
