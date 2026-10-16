"""Municode fetcher: ingest municipal codes hosted on library.municode.com.

The Municode library is a JavaScript SPA, so plain HTTP fetching of a code
page returns only an empty shell. This module uses the same JSON API the SPA
itself calls (same-origin ``/api`` endpoints with an ``X-CSRF: 1`` header):

    GET /api/Clients/stateAbbr?stateAbbr=TX          -> client list
    GET /api/ClientContent/<clientId>                -> products (codes)
    GET /api/codesToc/fullTree/latest                -> document tree
    GET /api/CodesContent?groupChunks=true           -> full section HTML

Each ``§``-titled document in a CodesContent response becomes one section.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Iterator, Optional

import httpx

from govmcp_parser.html_parser import html_to_markdown
from govmcp_parser.sources import SourceDefinition

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://library.municode.com/api"
SECTION_TITLE_RE = re.compile(r"§\s*(?P<section_id>[\w.\-]+)\s*[-–.]?\s*(?P<title>.*)")
REQUEST_DELAY_SECONDS = 0.3


@dataclass
class Section:
    """One ordinance section extracted from any source format."""

    section_id: str
    title: str
    body: str  # markdown
    source_url: str


class MunicodeClient:
    """Minimal client for the Municode library JSON API."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        referer: Optional[str] = None,
        delay: float = REQUEST_DELAY_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self._client = httpx.Client(
            timeout=120,
            follow_redirects=True,
            headers={
                "User-Agent": "GovMCP/0.1 (+https://github.com/daikiito-dk/ZoningMCP)",
                "X-CSRF": "1",
                **({"Referer": referer} if referer else {}),
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MunicodeClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, path: str, **params: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(3):
            time.sleep(self.delay)
            try:
                response = self._client.get(f"{self.base_url}/{path}", params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                # municode occasionally returns transient 500s; retry with backoff
                last_error = exc
                wait = 2**attempt
                logger.warning("%s failed (%s), retrying in %ds", path, exc, wait)
                time.sleep(wait)
        raise RuntimeError(f"municode API request failed after retries: {path}") from last_error

    def find_client_id(self, state_abbr: str, client_name: str) -> int:
        clients = self._get("Clients/stateAbbr", stateAbbr=state_abbr)
        for client in clients:
            if client.get("ClientName", "").lower() == client_name.lower():
                return int(client["ClientID"])
        raise LookupError(f"municode client not found: {client_name}, {state_abbr}")

    def find_product_id(self, client_id: int, product_name: str) -> int:
        content = self._get(f"ClientContent/{client_id}")
        for product in content.get("codes", []):
            if product.get("productName", "").lower() == product_name.lower():
                return int(product["productId"])
        raise LookupError(
            f"municode product not found for client {client_id}: {product_name}"
        )

    def get_tree(self, product_id: int, node_id: Optional[str] = None) -> dict:
        return self._get(
            "codesToc/fullTree/latest",
            productId=product_id,
            nodeId=node_id or str(product_id),
        )

    def get_content_docs(
        self, product_id: int, node_id: str, group_chunks: bool = True
    ) -> list[dict]:
        """Documents in the chunk group containing ``node_id``.

        With ``group_chunks=False`` only the single requested node's document
        is returned; use it as a fallback for groups too large for the API
        (it answers 500 on oversized chunk groups).
        """
        data = self._get(
            "CodesContent",
            productId=product_id,
            nodeId=node_id,
            groupChunks="true" if group_chunks else "false",
        )
        return data.get("Docs", [])


def _walk_tree(node: dict, ancestry: tuple[str, ...] = ()) -> Iterator[tuple[dict, tuple[str, ...]]]:
    yield node, ancestry
    for child in node.get("Children", []):
        yield from _walk_tree(child, ancestry + (node["Id"],))


def chapter_nodes(tree: dict, include_chapters: list[str]) -> list[dict]:
    """Select chapter nodes whose heading matches e.g. 'CHAPTER 25-2.'."""
    wanted = [c.upper() for c in include_chapters]
    matches = []
    for node, _ in _walk_tree(tree):
        heading = (node.get("Heading") or "").upper().replace("-", "-")
        if any(heading.startswith(f"CHAPTER {c}") for c in wanted):
            matches.append(node)
    return matches


def docs_to_sections(
    docs: list[dict], source_url_for_node, seen: set[str]
) -> list[Section]:
    """Convert CodesContent docs into sections (deduplicated by section id)."""
    sections: list[Section] = []
    for doc in docs:
        match = SECTION_TITLE_RE.match((doc.get("Title") or "").strip())
        if not match:
            continue
        section_id = match.group("section_id")
        if section_id in seen:
            continue
        seen.add(section_id)
        title = match.group("title").strip()
        body = html_to_markdown(doc.get("Content") or "").strip()
        sections.append(
            Section(
                section_id=section_id,
                title=title,
                body=body or f"{section_id} {title}",
                source_url=source_url_for_node(doc.get("Id", "")),
            )
        )
    return sections


def fetch_municode_sections(source: SourceDefinition) -> list[Section]:
    """Fetch all sections for a ``format: municode`` source definition."""
    cfg = source.municode or {}
    state_abbr = cfg["state_abbr"]
    client_name = cfg["client_name"]
    product_name = cfg["product_name"]
    client_path = cfg.get("client_path", f"{state_abbr.lower()}/{client_name.lower()}")
    product_path = cfg.get("product_path", "code_of_ordinances")
    include_chapters = cfg.get("include_chapters") or []

    def url_for(node_id: str) -> str:
        url = f"https://library.municode.com/{client_path}/codes/{product_path}"
        return f"{url}?nodeId={node_id}" if node_id else url

    with MunicodeClient(referer=url_for("")) as client:
        client_id = client.find_client_id(state_abbr, client_name)
        product_id = client.find_product_id(client_id, product_name)
        logger.info("municode client=%s product=%s", client_id, product_id)

        tree = client.get_tree(product_id)
        chapters = chapter_nodes(tree, include_chapters) if include_chapters else [tree]
        logger.info("fetching %d chapter(s)", len(chapters))

        sections: list[Section] = []
        seen: set[str] = set()
        for chapter in chapters:
            # Large chapters are split into multiple chunk groups. Collect one
            # CodesContent response per distinct group so no section is missed
            # (a single chapter-level request returns only the first group).
            groups: dict[str, list[dict]] = {}
            for node, _ in _walk_tree(chapter):
                if node.get("HasChildren"):
                    continue
                group_id = (node.get("Data") or {}).get("ChunkGroupStartingId") or chapter["Id"]
                groups.setdefault(group_id, []).append(node)
            logger.info(
                "%s: %d chunk group(s)", chapter.get("Heading", "")[:50], len(groups)
            )
            for group_id, leaves in groups.items():
                try:
                    docs = client.get_content_docs(product_id, group_id)
                except RuntimeError:
                    # Oversized chunk groups make the API return 500 even after
                    # retries; fall back to fetching each leaf section directly.
                    logger.warning(
                        "  group %s failed; falling back to %d per-section fetches",
                        group_id, len(leaves),
                    )
                    docs = []
                    for leaf in leaves:
                        docs.extend(
                            client.get_content_docs(product_id, leaf["Id"], group_chunks=False)
                        )
                chapter_sections = docs_to_sections(docs, url_for, seen)
                logger.info(
                    "  group %s: %d sections from %d docs",
                    group_id, len(chapter_sections), len(docs),
                )
                sections.extend(chapter_sections)
        return sections
