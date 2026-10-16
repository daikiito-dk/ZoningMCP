"""Tests for freshness tracking and differential re-ingestion (issue #2)."""

import json
from pathlib import Path

import pytest

from govmcp_parser.pipeline import run_source
from govmcp_parser.sources import SourceDefinition
from govmcp_parser.state import SourceState

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def municode_source():
    return SourceDefinition(
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


@pytest.fixture()
def fake_client(monkeypatch):
    """Offline MunicodeClient double backed by fixtures."""
    from govmcp_parser.municode import MunicodeClient

    class FakeClient(MunicodeClient):
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def close(self):
            pass

        def find_client_id(self, state_abbr, client_name):
            return 1113

        def find_product_id(self, client_id, product_name):
            return 15303

        def get_product_latest_update(self, client_id, product_id):
            return "2026-08-27T14:01:17"

        def get_tree(self, product_id, node_id=None):
            return json.loads((FIXTURES / "municode_tree.json").read_text())

        def get_content_docs(self, product_id, node_id, group_chunks=True):
            return json.loads((FIXTURES / "municode_codes_content.json").read_text())["Docs"]

    monkeypatch.setattr("govmcp_parser.municode.MunicodeClient", FakeClient)


def test_state_roundtrip(tmp_path):
    state = SourceState(tmp_path)
    key = SourceState.key("austin", "TX", "Doc")
    assert state.fingerprint(key) is None
    state.record(key, "fp1", sections=10, chunks=12)
    state.save()
    reloaded = SourceState(tmp_path)
    assert reloaded.fingerprint(key) == "fp1"


def test_run_source_skips_unchanged(municode_source, fake_client, tmp_path):
    chunks = run_source(municode_source, tmp_path)
    assert chunks  # first run ingests

    second = run_source(municode_source, tmp_path)
    assert second is None  # unchanged fingerprint -> skipped

    forced = run_source(municode_source, tmp_path, force=True)
    assert forced  # --force re-ingests


def test_run_source_reingests_on_change(municode_source, fake_client, tmp_path, monkeypatch):
    run_source(municode_source, tmp_path)
    monkeypatch.setattr(
        "govmcp_parser.pipeline.compute_fingerprint", lambda source: "2026-10-01T00:00:00"
    )
    chunks = run_source(municode_source, tmp_path)
    assert chunks is not None  # new fingerprint -> re-ingested

    state = SourceState(tmp_path)
    key = SourceState.key("austin", "TX", "Austin Land Development Code (Title 25)")
    assert state.fingerprint(key) == "2026-10-01T00:00:00"


def test_raw_file_runs_are_not_tracked(municode_source, fake_client, tmp_path):
    chunks = run_source(municode_source, tmp_path, raw=b"<p>ignored</p>")
    assert chunks is not None
    assert not (tmp_path / ".govmcp_state.json").exists()
