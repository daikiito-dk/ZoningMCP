"""Source definitions: per-municipality configuration for the ingestion pipeline.

Adding a new municipality must not require code changes — only a new YAML
file under ``sources/``. See ``sources/austin_tx.yaml`` for the schema.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class SourceDefinition:
    """Configuration for one municipal document source."""

    city: str
    state: str
    county_fips: str
    document_title: str
    url: str
    format: str = "html"  # "html" | "pdf" | "municode"
    effective_date: Optional[str] = None
    # For format="municode": {"state_abbr", "client_name", "product_name",
    # "client_path", "product_path", "include_chapters": [...]}
    municode: Optional[dict] = None
    # Regex with named groups (?P<section_id>...) and (?P<title>...) used to
    # detect section boundaries in the converted markdown/text.
    section_pattern: str = r"§\s*(?P<section_id>\d+-\d+-\d+)[.\s]+(?P<title>[^\n]+)"
    # CSS selector narrowing HTML parsing to the main content element.
    content_selector: Optional[str] = None
    max_chunk_chars: int = 1500
    tags: list[str] = field(default_factory=list)

    @property
    def section_regex(self) -> "re.Pattern[str]":
        return re.compile(self.section_pattern)


def load_source(path: str | Path) -> SourceDefinition:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return SourceDefinition(**data)


def load_sources(directory: str | Path) -> list[SourceDefinition]:
    directory = Path(directory)
    return [
        load_source(p)
        for p in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml"))
    ]
