# GovMCP Infrastructure

サーバーレス構成。常時起動リソース（ベクター DB / RDS）は持たず、S3 + Athena/DuckDB + Lambda の従量課金のみで運用する。

## S3 Data Lake Layout

ローカルの `data/` ミラーと同一レイアウトを S3 に配置する。

```
s3://govmcp-data-lake/
├── parquet/                     # クエリ用フラットテーブル (DuckDB / Athena)
│   └── state=TX/
│       └── city=austin/
│           └── chunks.parquet
├── markdown/                    # 人間可読・RAG 用
│   └── state=TX/city=austin/<section_id>.md
└── jsonld/                      # チャンク単位の JSON-LD (schema.org Legislation)
    └── state=TX/city=austin/<chunk_id>.json
```

Parquet schema (hive partitioning on `state`, `city`):

| column | type | notes |
|---|---|---|
| `chunk_id` | string | sha256(fips\|section_id\|index)[:16] |
| `section_id` | string | e.g. `25-2-491` |
| `section_title` | string | |
| `text` | string | markdown body |
| `chunk_index` | int64 | |
| `state` | string | partition key |
| `city` | string | partition key |
| `county_fips` | string | e.g. `48453` |
| `effective_date` | string | ISO-8601, nullable |
| `source_url` | string | primary source |
| `document_title` | string | |

## Athena DDL

```sql
CREATE EXTERNAL TABLE govmcp_chunks (
  chunk_id        string,
  section_id      string,
  section_title   string,
  text            string,
  chunk_index     bigint,
  county_fips     string,
  effective_date  string,
  source_url      string,
  document_title  string
)
PARTITIONED BY (state string, city string)
STORED AS PARQUET
LOCATION 's3://govmcp-data-lake/parquet/';
```

## DuckDB (local / Lambda embedded)

`govmcp-server` の `RegulationStore` がそのまま使える。S3 直参照は httpfs 拡張で対応予定。

## Lambda Deployment (MCP endpoint)

1. `govmcp-parser` をスケジュール実行（EventBridge: 週次）し、差分検知（ETag / Last-Modified）で変更自治体のみ再パース → S3 へ書き込み。
2. `govmcp-server` を Lambda + Function URL（または API Gateway）で streamable HTTP MCP transport として公開。
3. コスト目安: S3 ストレージ (数 GB 未満) + Athena/DuckDB クエリ従量 + Lambda 実行時間のみ。

## Roadmap

- [ ] Terraform / CDK で S3 バケット・Lambda・EventBridge をコード化
- [ ] ETag / Last-Modified による改定検知と差分再パース
- [ ] Phase 2: Loudoun County, VA / Phase 3: San Jose, CA のソース定義追加
- [ ] DuckDB httpfs による S3 直クエリ
