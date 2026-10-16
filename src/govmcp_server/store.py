"""DuckDB query layer over the GovMCP data lake (parquet).

Works against a local data lake mirror (``data/parquet/**``) or, with the
DuckDB httpfs extension, directly against S3 — the layout is identical.
No always-on database is required; queries are served by an embedded DuckDB.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import duckdb


class RegulationStore:
    """Query interface over parquet chunks produced by govmcp-parser."""

    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        self._conn = duckdb.connect()
        glob = str(self.data_dir / "parquet" / "**" / "*.parquet")
        self._conn.execute(
            f"CREATE OR REPLACE VIEW chunks AS SELECT * FROM read_parquet('{glob}', hive_partitioning=true)"
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "RegulationStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get_zoning_rules(
        self, city: str, zoning_code: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Return sections governing a zoning district (e.g. Austin 'CS-1').

        Matches the zoning code in section titles and body text, ranked by
        how prominently the code appears.
        """
        return self._query(
            """
            SELECT section_id, section_title, text, source_url, effective_date,
                   document_title,
                   (length(text) - length(replace(lower(text), lower($zc), '')))
                     / greatest(length($zc), 1) AS mentions
            FROM chunks
            WHERE lower(city) = lower($city)
              AND (lower(text) LIKE '%' || lower($zc) || '%'
                   OR lower(section_title) LIKE '%' || lower($zc) || '%')
            ORDER BY mentions DESC, section_id
            LIMIT $limit
            """,
            {"city": city, "zc": zoning_code, "limit": limit},
        )

    def search_environmental_regulations(
        self, city: str, topic: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Full-text search over regulation text for a topic (noise, drainage, ...).

        Each whitespace-separated term in ``topic`` must appear in the chunk
        (AND semantics). Ranking counts total term occurrences.
        """
        terms = [t for t in topic.split() if t]
        if not terms:
            return []
        where = " AND ".join(
            f"lower(text) LIKE '%' || lower($t{i}) || '%'" for i in range(len(terms))
        )
        score = " + ".join(
            f"(length(text) - length(replace(lower(text), lower($t{i}), '')))"
            f" / greatest(length($t{i}), 1)"
            for i in range(len(terms))
        )
        params = {f"t{i}": t for i, t in enumerate(terms)}
        params.update({"city": city, "limit": limit})
        return self._query(
            f"""
            SELECT section_id, section_title, text, source_url, effective_date,
                   document_title, ({score}) AS relevance
            FROM chunks
            WHERE lower(city) = lower($city) AND {where}
            ORDER BY relevance DESC, section_id
            LIMIT $limit
            """,
            params,
        )

    def verify_source_citation(
        self, section_id: str, city: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Return the primary source (URL + verbatim text) for a section id."""
        city_filter = "AND lower(city) = lower($city)" if city else ""
        return self._query(
            f"""
            SELECT section_id, section_title, text, source_url, effective_date,
                   document_title, state, county_fips, city
            FROM chunks
            WHERE section_id = $sid {city_filter}
            ORDER BY chunk_index
            """,
            {"sid": section_id, **({"city": city} if city else {})},
        )

    def list_coverage(self) -> list[dict[str, Any]]:
        """Summarize ingested coverage by state/city."""
        return self._query(
            """
            SELECT state, city, county_fips,
                   count(DISTINCT section_id) AS sections,
                   count(*) AS chunks
            FROM chunks
            GROUP BY state, city, county_fips
            ORDER BY state, city
            """,
            {},
        )

    def _query(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        cursor = self._conn.execute(sql, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
