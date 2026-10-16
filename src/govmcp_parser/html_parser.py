"""HTML parsing: municipal code web pages -> structured markdown sections."""

from __future__ import annotations

from bs4 import BeautifulSoup
from markdownify import markdownify

from govmcp_parser.sources import SourceDefinition


def html_to_markdown(html: str, content_selector: str | None = None) -> str:
    """Convert an HTML document to clean markdown, preserving tables."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    root = soup.select_one(content_selector) if content_selector else soup.body or soup
    md = markdownify(
        str(root),
        heading_style="ATX",
        strip=["img"],
    )
    return _normalize(md)


def split_into_sections(
    markdown: str, source: SourceDefinition
) -> list[tuple[str, str, str]]:
    """Split markdown into ``(section_id, section_title, body)`` tuples.

    Section boundaries are detected with the source's ``section_pattern``
    regex. Text before the first match is discarded as front matter.
    """
    regex = source.section_regex
    matches = list(regex.finditer(markdown))
    sections: list[tuple[str, str, str]] = []
    for i, match in enumerate(matches):
        section_id = match.group("section_id").strip()
        title = match.group("title").strip() if "title" in match.groupdict() else ""
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        body = markdown[start:end].strip()
        if body:
            sections.append((section_id, title, body))
    return sections


def _normalize(md: str) -> str:
    lines = [line.rstrip() for line in md.splitlines()]
    out: list[str] = []
    blank = 0
    for line in lines:
        if line.strip():
            blank = 0
            out.append(line)
        else:
            blank += 1
            if blank <= 1:
                out.append("")
    return "\n".join(out).strip() + "\n"
