# ZoningMCP (GovMCP)

全米自治体の Zoning Code・環境規制データを自動取得・構造化し、Model Context Protocol (MCP) 経由で **一次出典（条文番号 + URL）付き** で AI エージェントに供給するデータパイプライン。

US municipal zoning & environmental regulation data, structured and served over the Model Context Protocol with mandatory primary-source citations.

## Architecture

```
 [Municipal open data (PDF/HTML)]
                 │
                 ▼
  govmcp-parser   Parse & chunk, attach grounding metadata
                 │  (state / county_fips / section_id / effective_date / source_url)
                 ▼
  Data lake       Parquet + Markdown + JSON-LD (S3, or local data/ mirror)
                 │  No always-on DB: DuckDB / Athena query on demand
                 ▼
  govmcp-server   MCP tools for Claude / M365 Copilot / OpenAI Agents
```

## Quickstart

```bash
uv sync                      # install dependencies (Python 3.10+)

# Phase 1 PoC: ingest Austin, TX Land Development Code
uv run govmcp-parse sources/austin_tx.yaml --data-dir data

# Inspect ingested coverage
uv run govmcp-serve --coverage --data-dir data

# Run the MCP server (stdio transport; point your MCP client at it)
uv run govmcp-serve --data-dir data
```

## MCP Tools

| Tool | Args | Description |
|---|---|---|
| `get_zoning_rules` | `city`, `zoning_code` | Building limits / permitted uses for a zoning district (e.g. Austin `CS-1`) |
| `search_environmental_regulations` | `city`, `topic` | Search environmental, noise, drainage regulations |
| `verify_source_citation` | `section_id`, `city?` | Return the primary source URL + verbatim text for a section |

## Adding a municipality

Drop a YAML file into `sources/` — no code changes required. Three source formats are supported:

- `format: municode` — municipalities hosted on library.municode.com (the majority of US cities). Uses the library's JSON API; JS rendering is not required. See `sources/austin_tx.yaml`.
- `format: encodeplus` — municipalities hosted on online.encodeplus.com (e.g. Loudoun County, VA). Crawls the server-rendered print view. See `sources/loudoun_county_va.yaml`.
- `format: html` — a static HTML page; configure `section_pattern` (regex with `section_id` / `title` groups) and optionally `content_selector`.
- `format: pdf` — a PDF code document; section boundaries come from `section_pattern`.

Phase 1 ingests Austin's Land Development Code chapters 25-2 (Zoning), 25-7 (Drainage), and 25-8 (Environment): 666 sections / 1084 chunks.
Phase 2 ingests Loudoun County's Zoning Ordinance chapters 2, 4, 5, 6, 7: 251 sections / 1209 chunks.

## Development

```bash
uv run pytest
```

## Documentation

- [Master Requirement Specification (要件定義書)](docs/master-requirement-specification.md)
- [Infra: S3 layout, Athena DDL, Lambda deployment](infra/README.md)

## License

MIT
