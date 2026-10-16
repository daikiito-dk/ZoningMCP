# GovMCP 開発ロードマップ

> 要件: [master-requirement-specification.md](master-requirement-specification.md)
> 起票済みイシュー: https://github.com/daikiito-dk/ZoningMCP/issues

## 現状 (2026-10-16)

- [x] リポジトリスキャフォールド（`govmcp-parser` / `govmcp-server` / `sources/` / `infra/`）
- [x] パース・チャンキング・Grounding Metadata 付与の実装
- [x] MCP ツール 3 種（`get_zoning_rules` / `search_environmental_regulations` / `verify_source_citation`）
- [x] DuckDB クエリレイヤー（ローカル parquet データレイク）
- [x] テスト 11 件パス（フィクスチャベース、ネットワーク不要）
- [ ] Austin 実データ取り込み（Municode が JS レンダリングのため素の HTTP 取得では条文を取得できないことを確認済み）

## マイルストーン

### M1: Phase 1 PoC 完了（Austin, TX）

ゴール: Austin Land Development Code の実データで end-to-end（取得 → パース → S3 レイアウト → MCP 回答 + 一次出典）を通す。

- Municode の JS レンダリング対応（公式 API / print view / 代替一次ソースの選定）
- 実データでのパース品質検証（表組み・条文番号・施行日の抽出精度）
- Claude / Copilot からの実利用デモ

### M2: 本番インフラ（サーバーレス化）

ゴール: 常時起動コストゼロの AWS 構成で MCP エンドポイントを公開する。

- Terraform / CDK で S3・Lambda・EventBridge をコード化
- Lambda + streamable HTTP MCP transport へのデプロイ
- ETag / Last-Modified による条例改定検知と差分再パース（週次）
- DuckDB httpfs で S3 の parquet を直接クエリ

### M3: Phase 2 展開（Loudoun County, VA）

- ソース定義 YAML 追加のみで取り込めることを実証（拡張性要件の検証）
- 騒音制限・高圧送電線規制・EPA 環境評価ガイドライン

### M4: Phase 3 展開（San Jose, CA）

- CEQA 適合チェック条文 + 都市計画 Zoning
- 複数都市横断クエリの UX 検証

### 横断課題

- CI 整備（GitHub Actions で pytest）
- パース品質メトリクス（セクション抽出率・出典付与率）の計測

## 優先順位

1. M1（PMF 検証の前提）
2. 横断課題の CI（以降の開発効率の土台）
3. M2 → M3 → M4
