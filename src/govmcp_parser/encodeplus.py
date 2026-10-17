"""enCodePlus fetcher: ingest codes hosted on online.encodeplus.com.

enCodePlus doc-viewer pages are JavaScript shells, but the print view is
server-rendered:

    GET <base>/doc-view.aspx?print=1              -> full TOC (+ front matter)
    GET <base>/doc-view.aspx?print=1&secid=<n>    -> one section, full text

TOC anchors look like
    <a href=".../doc-viewer.aspx?secid=859"><span class="toc-item">4.06.02 Data Centers</span></a>
and section content lives in ``div#thePage`` (``section[id^=secid-]``).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from govmcp_parser.html_parser import _normalize
from govmcp_parser.municode import Section
from govmcp_parser.sources import SourceDefinition
from markdownify import markdownify

logger = logging.getLogger(__name__)

REQUEST_DELAY_SECONDS = 0.4
CHAPTER_RE = re.compile(r"^Chapter\s+(?P<num>\d+)\s*:\s*(?P<title>.+)$", re.IGNORECASE)
SECTION_RE = re.compile(r"^(?P<section_id>\d+(?:\.\d+)*)\s*[-–.:]?\s+(?P<title>.+)$")


class EncodePlusClient:
    """Minimal client for enCodePlus print views."""

    def __init__(self, base_url: str, delay: float = REQUEST_DELAY_SECONDS) -> None:
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self._client = httpx.Client(
            timeout=60,
            follow_redirects=True,
            headers={
                "User-Agent": "GovMCP/0.1 (+https://github.com/daikiito-dk/ZoningMCP)"
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "EncodePlusClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get_page(self, **params: Any) -> str:
        last_error: Exception | None = None
        for attempt in range(3):
            time.sleep(self.delay)
            try:
                response = self._client.get(f"{self.base_url}/doc-view.aspx", params=params)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError as exc:
                last_error = exc
                wait = 2**attempt
                logger.warning("doc-view fetch failed (%s), retrying in %ds", exc, wait)
                time.sleep(wait)
        raise RuntimeError("encodeplus fetch failed after retries") from last_error

    def get_toc_html(self) -> str:
        return self.get_page(print="1")

    def get_section_html(self, secid: str) -> str:
        return self.get_page(print="1", secid=secid)


def parse_toc(html: str) -> list[tuple[str, str]]:
    """Extract ``(secid, label)`` pairs in document order from the TOC."""
    soup = BeautifulSoup(html, "html.parser")
    toc: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select('a[href*="secid="]'):
        href = anchor.get("href", "")
        match = re.search(r"secid=(\d+)", href)
        label_el = anchor.select_one(".toc-item") or anchor
        label = " ".join(label_el.get_text(" ", strip=True).split())
        if not match or not label:
            continue
        secid = match.group(1)
        if secid in seen:
            continue
        seen.add(secid)
        toc.append((secid, label))
    return toc


def select_toc_entries(
    toc: list[tuple[str, str]], include_chapters: Optional[list[str]]
) -> list[tuple[str, str]]:
    """Keep entries under the requested chapters (all entries when unset)."""
    if not include_chapters:
        return toc
    wanted = set(include_chapters)
    selected: list[tuple[str, str]] = []
    current_chapter: Optional[str] = None
    for secid, label in toc:
        chapter_match = CHAPTER_RE.match(label)
        if chapter_match:
            current_chapter = chapter_match.group("num")
        if current_chapter in wanted:
            selected.append((secid, label))
    return selected


def _label_to_section(label: str) -> tuple[str, str]:
    """Split a TOC label into (section_id, title)."""
    chapter_match = CHAPTER_RE.match(label)
    if chapter_match:
        return f"chapter-{chapter_match.group('num')}", label
    section_match = SECTION_RE.match(label)
    if section_match:
        return section_match.group("section_id"), section_match.group("title").strip()
    return label.strip() or "untitled", ""


def section_html_to_markdown(html: str) -> str:
    """Extract the section body from a print-view page."""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("div#thePage") or soup.body or soup
    for tag in root.select("#pageControls, #sectionBanner, script, style"):
        tag.decompose()
    # The h4 repeats the section heading already captured in metadata.
    for h4 in root.select("h4"):
        h4.decompose()
    return _normalize(markdownify(str(root), heading_style="ATX", strip=["img"]))


def fetch_encodeplus_sections(source: SourceDefinition) -> list[Section]:
    """Fetch all sections for a ``format: encodeplus`` source definition."""
    cfg = source.encodeplus or {}
    base_url = cfg["base_url"].rstrip("/")
    include_chapters = cfg.get("include_chapters") or []

    with EncodePlusClient(base_url) as client:
        toc = parse_toc(client.get_toc_html())
        entries = select_toc_entries(toc, include_chapters)
        logger.info("encodeplus TOC: %d entries, %d selected", len(toc), len(entries))

        sections: list[Section] = []
        for secid, label in entries:
            section_id, title = _label_to_section(label)
            body = section_html_to_markdown(client.get_section_html(secid))
            if not body.strip():
                logger.info("empty section, skipping: %s (%s)", section_id, secid)
                continue
            sections.append(
                Section(
                    section_id=section_id,
                    title=title,
                    body=body,
                    source_url=f"{base_url}/doc-viewer.aspx?secid={secid}",
                )
            )
        return sections
