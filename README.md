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

Drop a YAML file into `sources/` — no code changes required. See `sources/austin_tx.yaml` for the schema (section numbering regex, FIPS code, document title, source URL).

## Development

```bash
uv run pytest
```

## Documentation

- [Master Requirement Specification (要件定義書)](docs/master-requirement-specification.md)
- [Infra: S3 layout, Athena DDL, Lambda deployment](infra/README.md)

## License

MIT
