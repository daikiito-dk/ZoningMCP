# プロジェクト要件定義書: GovMCP (ZoningMCP)

> Master Requirement Specification — ZoningMCP の要件定義と、プロダクトポートフォリオ全体における位置付けを定める。
> バージョン: 1.0 / ステータス: Draft / 最終更新: 2026-10-11

---

## 1. プロジェクト目的 & 背景

全米の自治体（州・郡・市）が公開する建築規制（Zoning Code）、環境保全基準（EPA/CEQA）、許認可ガイドラインなどの**パブリックデータ**を自動取得・構造化し、Model Context Protocol (MCP) 規格および Microsoft 365 Copilot / Enterprise RAG が **100% 正確に一次出典（条文・セクション番号）付きで参照できる**データパイプラインを構築する。

### 背景

- AI・データセンター建設ラッシュに伴い、自治体の Zoning Code や環境規制の改定頻度が上昇している。
- 開発者・建設事業者・コンサルタントは、自治体ごとに形式の異なる PDF / HTML の条文を人手で読み解く必要があり、調査コストが膨大。
- 生成 AI / Copilot 系ツールは一次出典を正確に引用できず、ハルシネーションによる誤った法規解釈のリスクがある。
- GovMCP は「条文チャンク + Grounding メタデータ」を MCP 経由で供給することで、この問題を解決する。

### システム構成

```
 [全米自治体の公開データ (PDF/HTML/CSV)]
                 │
                 ▼
 ┌─────────────────────────────────────────────────────────┐
 │ 1. GovMCP Parser / Chunking Engine                      │
 │    - 表組み/構造化パース + メタデータ(自治体コード/適用日)付与│
 └─────────────────────────┬───────────────────────────────┘
                           │
                           ▼
 ┌─────────────────────────────────────────────────────────┐
 │ 2. AWS S3 Data Lake (Parquet / Markdown / JSON-LD)      │
 │    - 低コスト・常時起動DB不要のサーバーレスアーキテクチャ   │
 └─────────────────────────┬───────────────────────────────┘
                           │
                           ▼
 ┌─────────────────────────────────────────────────────────┐
 │ 3. GovMCP Server (MCP Protocol Endpoint / AWS Lambda)   │
 │    - Copilot / Claude / OpenAI Agents へのコンテキスト供給│
 └─────────────────────────────────────────────────────────┘
```

---

## 2. フェーズ別・対象都市展開ロードマップ

初期のプロダクトマーケットフィット（PMF）獲得のため、**AI・データセンター建設ラッシュと法改定が激しいエリア**から順次展開する。

| フェーズ | 対象都市・エリア | 選定理由 & ターゲットデータ |
|---|---|---|
| Phase 1 (PoC) | Austin, TX（テキサス州オースティン） | HOME Initiative 等で条例変化が激しい。Land Development Code（商業・産業 Zoning および排水・環境規制） |
| Phase 2 | Loudoun County, VA（バージニア州ラウドン郡） | 世界最大のデータセンター拠点。騒音制限・高圧送電線規制・EPA 環境評価ガイドライン |
| Phase 3 | San Jose, CA（カリフォルニア州サンノゼ） | カリフォルニア州環境品質法（CEQA）適合チェックおよび都市計画 Zoning |

---

## 3. 機能要件 (Functional Requirements)

### ① データ取得・パースエンジン (`govmcp-parser`)

- **非構造化 PDF / HTML の構造化**
  - 複雑な表組み、条文番号（例: `Section 25-2-491`）、注釈を含むドキュメントを、意味単位を保持した Markdown および Chunk JSON に自動変換する。
- **メタデータ自動付与 (Grounding Metadata)**
  - すべてのデータチャンクに対し、以下を付与する。
    - `state`（州）
    - `county_fips`（自治体コード）
    - `section_id`（条文番号）
    - `effective_date`（施行日）
    - `source_url`（一次出典 URL）

### ② データストレージ & クエリ設計 (S3 Data Lake)

- **サーバーレス & データレイク構成**
  - 固定費のかかるベクター DB / RDS は常時起動せず、パース済みデータを AWS S3 に Parquet / JSON-LD / Markdown 形式で保管する。
- **軽量検索インターフェース**
  - メタデータ検索には AWS Athena および埋め込み DuckDB を採用し、クエリ従量課金により運用インフラコストを最小化する。

### ③ MCP (Model Context Protocol) サーバー実装 (`govmcp-server`)

AI エージェント / Copilot からコール可能な以下の標準 MCP インターフェース（Tools）を提供する。

| Tool | 引数 | 説明 |
|---|---|---|
| `get_zoning_rules` | `city`, `zoning_code` | 特定区画（例: Austin `CS-1`）の建築上限・許容用途を取得する |
| `search_environmental_regulations` | `city`, `topic` | 環境・騒音・排水等の制約条文を検索する |
| `verify_source_citation` | `section_id` | 回答の根拠となる自治体一次出典 URL・原文を返却する |

---

## 4. プロダクトポートフォリオ全体図

これまで策定してきたプロダクト群を、「空間・医療アプリケーション層」と「データ・インフラ層」の 2 つの階層に体系化する。

```
【空間・医療・Physical AI アプリケーション層】
 │
 ├── USD-OmniSpatial   : 空間・医療・6DoF を OpenUSD で統合する最上位標準規格
 ├── Lookwright        : 6DoF 頭部移動・視界・空間UIの自動テストツール (CI/CD)
 └── fhir-hud-sdk      : FHIR カルテデータをスマートグラス HUD に描画するフロントエンド SDK

【AI コンテキスト & パブリックデータ インフラ層】
 │
 └── GovMCP            : 全米の Zoning・環境規制データを AWS S3 に蓄積し、
                         MCP / Copilot へ一次出典付きで供給するパイプライン (本プロジェクト)
```

### ポートフォリオ内での位置付け

- GovMCP はポートフォリオ唯一の**データ・インフラ層**プロダクトであり、アプリケーション層（USD-OmniSpatial / Lookwright / fhir-hud-sdk）が依存しうる「正確な一次データ供給基盤」としての役割を持つ。
- 中期的には、GovMCP が提供する空間規制データ（Zoning 区画・高さ制限等）を USD-OmniSpatial の空間モデルと統合し、「法規制を考慮した 3D 都市シミュレーション」への展開が視野に入る。

---

## 5. 非機能要件 (Non-Functional Requirements)

| 項目 | 要件 |
|---|---|
| 正確性 | すべての回答に一次出典（`section_id` + `source_url`）を付与し、出典のない回答を生成させない |
| コスト | 常時起動リソースゼロ。S3 + Athena/DuckDB + Lambda の従量課金のみで運用する |
| 鮮度 | 自治体の条例改定を検知し、差分のみ再パースできる仕組みを持つ（ETag / Last-Modified 監視） |
| 拡張性 | 自治体追加はコード変更なしに設定ファイル（ソース定義 YAML）の追加のみで行える |
| 互換性 | MCP 仕様準拠。Claude / Microsoft 365 Copilot / OpenAI Agents から利用可能 |

---

## 6. 用語集

| 用語 | 説明 |
|---|---|
| Zoning Code | 自治体が定める土地用途・建築規制の条例 |
| MCP (Model Context Protocol) | LLM アプリケーションと外部データ・ツールを接続するためのオープン標準プロトコル |
| Grounding Metadata | 生成 AI の回答を一次出典に紐付けるためのメタデータ |
| CEQA | California Environmental Quality Act（カリフォルニア州環境品質法） |
| FIPS | Federal Information Processing Standards。郡・自治体を一意に識別する連邦コード |
