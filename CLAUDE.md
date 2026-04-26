# CLAUDE.md — 官公庁委託調査ダッシュボード

## プロジェクト概要

官公庁が民間企業に発注する「委託調査」の案件数・委託先の時系列推移を可視化するWebダッシュボード。
フェーズ1は経済産業省（METI）のデータから着手し、将来的に他省庁へ拡張する。

利用者は note 等経由で ID/Password を取得してアクセスする想定。

## 技術スタック

| 用途 | ライブラリ / サービス |
|---|---|
| データ処理 | Python 3.10+, pandas, openpyxl |
| データベース | SQLite（初期）→ PostgreSQL（将来） |
| Webアプリ | Streamlit |
| デプロイ | Render または Streamlit Community Cloud |
| CI/CD | GitHub Actions |

## ディレクトリ構成

```
.
├── .github/
│   └── instructions/       # Issue/PR/Reviewのルール定義
├── config/
│   └── mapping.json        # 事業者名の名寄せ辞書
├── data/
│   ├── raw/                # 生のExcel（Git管理外推奨）
│   └── processed/          # 整形済みSQLite DB等
├── src/
│   ├── data_pipeline/
│   │   ├── parsers/        # 省庁別パーサー（meti_parser.py 等）
│   │   └── cleaner.py      # 名寄せ・クレンジング処理
│   ├── app/                # Streamlit ダッシュボード
│   └── utils/              # 共通ユーティリティ（和暦西暦変換等）
├── CLAUDE.md
├── requirements.txt
└── README.md
```

## 開発ルール

- **main への直接コミット禁止。** 必ず GitHub Issue を作成し、`feature/issue-{番号}` ブランチを切ること。
- Issue のタイトル・本文は `.github/instructions/issue.instructions.md` に従う。
- PR は `.github/instructions/pr.instructions.md` に従う。
- コミットメッセージは `.github/commit.instructions.md` に従う。

## コーディング規約

- Python 3.10+ の型ヒントを活用する。
- 変数名・関数名はスネークケース（`snake_case`）、クラス名はパスカルケース（`PascalCase`）。
- コメントは日本語でも可。
- 省庁固有のロジックは必ず `src/data_pipeline/parsers/` 配下に閉じ込め、共通スキーマへの変換を担う Adapter パターンを維持する。
- `data/raw/` 配下のファイルは Git にコミットしない（`.gitignore` 参照）。

## 理想DBスキーマ

| カラム名 | 型 | 説明 |
|---|---|---|
| `ministry` | String | 省庁コード（METI 等） |
| `publish_date` | Date | 掲載日（西暦変換済み） |
| `report_title` | String | 委託調査報告書名 |
| `contractor_name` | String | 委託事業者名（名寄せ済み） |
| `department` | String | 担当課室名 |
| `url` | String | HPアドレス |

## よく使うコマンド

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# Streamlitアプリの起動（開発中）
streamlit run src/app/main.py

# 経産省データのETL実行（Issue #2 実装後）
python src/data_pipeline/parsers/meti_parser.py
```

## 重要な設計上の注意点

- **名寄せは必須:** 「みずほリサーチ&テクノロジーズ」等の表記揺れが多数あるため、`config/mapping.json` を用いたキーワードマッチングで統一すること。
- **経産省フォーマットへの依存禁止:** 他省庁は局ごとに分散したデータ形式のため、METIパーサーに固有の仮定を埋め込まない。
- **和暦変換:** 掲載日が和暦表記の場合は `src/utils/` の変換ユーティリティを必ず通すこと。
