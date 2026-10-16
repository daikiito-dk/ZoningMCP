"""PDF parsing: municipal code PDFs -> structured text sections."""

from __future__ import annotations

import io

from pypdf import PdfReader

from govmcp_parser.html_parser import split_into_sections
from govmcp_parser.sources import SourceDefinition


def pdf_to_text(pdf_bytes: bytes) -> str:
    """Extract plain text from a PDF, one block per page."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(p for p in pages if p)


def parse_pdf(
    pdf_bytes: bytes, source: SourceDefinition
) -> list[tuple[str, str, str]]:
    """Parse a regulation PDF into ``(section_id, title, body)`` tuples."""
    text = pdf_to_text(pdf_bytes)
    return split_into_sections(text, source)
