"""GovMCP server: MCP protocol endpoint for regulation data.

Exposes three tools over the Model Context Protocol, backed by the DuckDB
query layer. Every response carries grounding metadata (section_id +
source_url) so consuming agents (Claude, Microsoft 365 Copilot, OpenAI
Agents) can cite the municipality's primary source.

Run locally over stdio:
    govmcp-serve --data-dir data

Deployment as an AWS Lambda MCP endpoint is described in infra/README.md.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from govmcp_server.store import RegulationStore

DEFAULT_DATA_DIR = os.environ.get("GOVMCP_DATA_DIR", "data")

mcp = FastMCP(
    "govmcp",
    instructions=(
        "GovMCP provides authoritative US municipal zoning and environmental "
        "regulation text. Always cite section_id and source_url from tool "
        "responses; never answer zoning questions from memory."
    ),
)


def _store() -> RegulationStore:
    return RegulationStore(DEFAULT_DATA_DIR)


@mcp.tool()
def get_zoning_rules(city: str, zoning_code: str) -> dict[str, Any]:
    """Get building limits and permitted uses for a zoning district.

    Args:
        city: Municipality name, e.g. "austin".
        zoning_code: Zoning district code, e.g. "CS-1" (Austin commercial).
    """
    with _store() as store:
        results = store.get_zoning_rules(city, zoning_code)
    return {
        "city": city,
        "zoning_code": zoning_code,
        "results": results,
        "citation_required": True,
    }


@mcp.tool()
def search_environmental_regulations(city: str, topic: str) -> dict[str, Any]:
    """Search environmental, noise, drainage, and similar regulations.

    Args:
        city: Municipality name, e.g. "austin".
        topic: Free-text topic, e.g. "noise limits" or "drainage detention".
    """
    with _store() as store:
        results = store.search_environmental_regulations(city, topic)
    return {"city": city, "topic": topic, "results": results, "citation_required": True}


@mcp.tool()
def verify_source_citation(
    section_id: str, city: Optional[str] = None
) -> dict[str, Any]:
    """Return the municipality's primary source URL and verbatim text for a
    section id, so an answer's legal basis can be verified.

    Args:
        section_id: Ordinance section number, e.g. "25-2-491".
        city: Optional municipality name to disambiguate.
    """
    with _store() as store:
        results = store.verify_source_citation(section_id, city)
    if not results:
        return {"section_id": section_id, "found": False, "results": []}
    meta = results[0]
    return {
        "section_id": section_id,
        "found": True,
        "source_url": meta["source_url"],
        "section_title": meta["section_title"],
        "effective_date": meta["effective_date"],
        "document_title": meta["document_title"],
        "verbatim_text": "\n\n".join(r["text"] for r in results),
    }


def main(data_dir: str = DEFAULT_DATA_DIR) -> None:
    global DEFAULT_DATA_DIR
    DEFAULT_DATA_DIR = data_dir
    mcp.run()
