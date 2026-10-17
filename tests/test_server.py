"""Tests for the MCP server entrypoints (no network, no server launch)."""

import pytest

from govmcp_server import server


def test_streamable_http_app_builds():
    app = server.mcp.streamable_http_app()
    assert app is not None


def test_main_rejects_unknown_transport():
    with pytest.raises(ValueError, match="unknown transport"):
        server.main(data_dir="data", transport="bogus")


def test_tools_registered():
    tool_names = {t.name for t in server.mcp._tool_manager.list_tools()}
    assert tool_names == {
        "get_zoning_rules",
        "search_environmental_regulations",
        "verify_source_citation",
    }
