"""Tests for the enCodePlus fetcher (fixture-based, no network)."""

import json
from pathlib import Path

import pytest

from govmcp_parser.encodeplus import (
    EncodePlusClient,
    parse_toc,
    section_html_to_markdown,
    select_toc_entries,
)
from govmcp_parser.pipeline import build_chunks
from govmcp_parser.sources import SourceDefinition

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def toc():
    return parse_toc((FIXTURES / "encodeplus_toc.html").read_text())


def test_parse_toc_dedupes_and_preserves_order(toc):
    secids = [s for s, _ in toc]
    assert secids == ["49", "857", "859", "68", "100"]


def test_select_toc_entries_filters_chapters(toc):
    selected = select_toc_entries(toc, ["4"])
    assert [s for s, _ in selected] == ["49", "857", "859"]
    assert select_toc_entries(toc, None) == toc


def test_section_html_to_markdown():
    html = (FIXTURES / "encodeplus_section.html").read_text()
    md = section_html_to_markdown(html)
    assert "Applicability." in md
    assert "60 dBA" in md
    assert "nav buttons" not in md
    assert "4.06.02 Data Centers" not in md  # h4 stripped (kept in metadata)


def test_build_chunks_with_encodeplus_format(monkeypatch):
    source = SourceDefinition(
        city="loudoun_county",
        state="VA",
        county_fips="51107",
        document_title="Loudoun County Zoning Ordinance",
        url="https://online.encodeplus.com/regs/loudouncounty-va-zo/doc-viewer.aspx",
        format="encodeplus",
        encodeplus={
            "base_url": "https://online.encodeplus.com/regs/loudouncounty-va-zo",
            "include_chapters": ["4"],
        },
    )

    class FakeClient(EncodePlusClient):
        def __init__(self, base_url, **kwargs):
            self.base_url = base_url

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def get_toc_html(self):
            return (FIXTURES / "encodeplus_toc.html").read_text()

        def get_section_html(self, secid):
            return (FIXTURES / "encodeplus_section.html").read_text()

    monkeypatch.setattr("govmcp_parser.encodeplus.EncodePlusClient", FakeClient)
    chunks = build_chunks(source)
    assert chunks
    assert {c.metadata.section_id for c in chunks} == {"chapter-4", "4.06", "4.06.02"}
    dc = next(c for c in chunks if c.metadata.section_id == "4.06.02")
    assert dc.metadata.county_fips == "51107"
    assert dc.metadata.source_url.endswith("doc-viewer.aspx?secid=859")
    assert "60 dBA" in dc.text
