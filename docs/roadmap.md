# GovMCP 開発ロードマップ

> 要件: [master-requirement-specification.md](master-requirement-specification.md)
> 起票済みイシュー: https://github.com/daikiito-dk/ZoningMCP/issues

## 現状 (2026-10-16)

- [x] リポジトリスキャフォールド（`govmcp-parser` / `govmcp-server` / `sources/` / `infra/`）
- [x] パース・チャンキング・Grounding Metadata 付与の実装
- [x] MCP ツール 3 種（`get_zoning_rules` / `search_environmental_regulations` / `verify_source_citation`）
- [x] DuckDB クエリレイヤー（ローカル parquet データレイク）
- [x] テスト 15 件パス（フィクスチャベース、ネットワーク不要）
- [x] Austin 実データ取り込み（2026-10-16）: Municode SPA の内部 JSON API（`/api/CodesContent` 等、`X-CSRF: 1` ヘッダ）を利用し JS レンダリング不要で取得。Chapter 25-2 (Zoning) / 25-7 (Drainage) / 25-8 (Environment) の 666 セクション / 1084 チャンク。大容量チャンクグループは API が 500 を返すためセクション単位フェッチへフォールバック
- [x] MCP ツールの実データ検証: `get_zoning_rules(austin, CS-1)` / `search_environmental_regulations` / `verify_source_citation` がセクション単位のディープリンク付き原文を返却

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

- [x] ソース定義 YAML 追加のみで取り込めることを実証（2026-10-17）: Loudoun County は Municode 未掲載のため enCodePlus（サーバーサイドレンダリングの print view）用フェッチャーを追加。Zoning Ordinance の章 2/4/5/6/7 で **251 セクション / 1209 チャンク**
- [x] データセンター固有規制（§ 4.06.02: 発電機騒音・防音壁・ファサード基準）の出典付き取得を確認
- [ ] Codified Ordinances（騒音条例等）・EPA 環境評価ガイドラインの追加ソース
- [ ] 既知の品質課題: enCodePlus 由来のリスト番号ノイズ（"1. A." 形式）とゼロ幅文字のクリーニング

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
