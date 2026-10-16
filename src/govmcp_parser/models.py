"""Core data models for GovMCP chunks and grounding metadata."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class GroundingMetadata:
    """Metadata that grounds every chunk to its authoritative primary source.

    Every answer produced through GovMCP must be traceable to these fields.
    """

    state: str  # US state, e.g. "TX"
    county_fips: str  # FIPS code of the county/municipality, e.g. "48453" (Travis County, TX)
    city: str  # e.g. "austin"
    section_id: str  # ordinance section number, e.g. "25-2-491"
    section_title: str  # human-readable section heading
    effective_date: Optional[str]  # ISO-8601 date the section took effect, if known
    source_url: str  # primary source URL published by the municipality
    document_title: str  # e.g. "Austin Land Development Code, Title 25"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Chunk:
    """A semantically coherent unit of regulation text with grounding metadata."""

    metadata: GroundingMetadata
    text: str  # markdown-formatted body text
    chunk_index: int = 0  # position of this chunk within its section
    chunk_id: str = field(init=False)

    def __post_init__(self) -> None:
        key = f"{self.metadata.county_fips}|{self.metadata.section_id}|{self.chunk_index}"
        self.chunk_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        row = self.metadata.to_dict()
        row.update(
            {
                "chunk_id": self.chunk_id,
                "chunk_index": self.chunk_index,
                "text": self.text,
            }
        )
        return row

    def to_jsonld(self) -> dict[str, Any]:
        """JSON-LD representation for the S3 data lake (schema.org Legislation)."""
        return {
            "@context": {
                "@vocab": "https://schema.org/",
                "govmcp": "https://govmcp.dev/ns#",
            },
            "@type": "Legislation",
            "@id": f"govmcp:chunk/{self.chunk_id}",
            "identifier": self.metadata.section_id,
            "name": self.metadata.section_title,
            "text": self.text,
            "url": self.metadata.source_url,
            "inForce": self.metadata.effective_date,
            "isPartOf": {"@type": "Legislation", "name": self.metadata.document_title},
            "govmcp:state": self.metadata.state,
            "govmcp:countyFips": self.metadata.county_fips,
            "govmcp:city": self.metadata.city,
            "govmcp:chunkIndex": self.chunk_index,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_jsonld(), ensure_ascii=False, indent=2)
