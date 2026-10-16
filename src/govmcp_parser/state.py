"""Source freshness tracking: skip re-ingestion when nothing changed.

Each source's fingerprint is stored in ``<data_dir>/.govmcp_state.json``:

- ``format: municode`` sources use the ``latestUpdatedDate`` that Municode
  publishes per product (updated whenever the municipality's code changes).
- ``format: html`` / ``pdf`` sources use the HTTP ``ETag`` or
  ``Last-Modified`` header of the source URL.

A run whose fingerprint matches the stored one is skipped unless ``--force``
is given, so scheduled jobs only re-parse municipalities that actually
changed (see the "鮮度" non-functional requirement).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

STATE_FILENAME = ".govmcp_state.json"


class SourceState:
    def __init__(self, data_dir: str | Path) -> None:
        self._path = Path(data_dir) / STATE_FILENAME
        self._data: dict = {}
        if self._path.exists():
            self._data = json.loads(self._path.read_text(encoding="utf-8"))

    @staticmethod
    def key(city: str, state: str, document_title: str) -> str:
        return f"{state}/{city}/{document_title}"

    def fingerprint(self, key: str) -> Optional[str]:
        entry = self._data.get(key)
        return entry.get("fingerprint") if entry else None

    def record(self, key: str, fingerprint: str, sections: int, chunks: int) -> None:
        self._data[key] = {
            "fingerprint": fingerprint,
            "sections": sections,
            "chunks": chunks,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("state saved to %s", self._path)
