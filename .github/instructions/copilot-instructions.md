# Copilot 全体共通指示

## 言語・出力形式

- すべての出力（コード、コメント、docstring、PR本文、コミットメッセージ、コメント）は**日本語**で記述する
- ソースコメントは「なぜ」を書く。コードから自明な情報は書かない
- 文章は簡潔・箇条書き中心でまとめる

## 作業の基本原則

- 最小限の変更で目的を達成する（YAGNI・KISS）
- 既存コードの設計パターンに従う
- 新しいライブラリは必要最小限に留め、既存ライブラリを優先する
- セキュリティ上の脆弱性を導入しない
- 関係のないコードや既存テストを変更しない

## 禁止事項

- シークレット・認証情報をソースコードにコミットしない
- 一時ファイル・ビルド成果物（`__pycache__`、`.pyc`、`dist/` など）をコミットしない
- 人間向けテンプレート（`PULL_REQUEST_TEMPLATE.md` 等）を Copilot 指示ファイルに含めない
- `print` でのログ出力は行わず、`logging` モジュールを使用する

## 命名規則

- 変数・関数・クラス名は処理内容が想像できる**具体的な英単語**を使う
- インデックス番号に意味を持たせない（`i` より `time_idx` など意味ある名前を使う）
- テーブル・カラム名はプロジェクト内で統一する

## 参照先

各作業フェーズの詳細ルールは以下の instructions ファイルを参照すること：

- Issue 作成: `.github/instructions/issue.instructions.md`
- PR 作成: `.github/instructions/pr.instructions.md`
- コードレビュー: `.github/instructions/review.instructions.md`
- コーディング規約: `.github/instructions/coding.instructions.md`
- コミットメッセージ: `.github/instructions/commit.instructions.md`
- Coding Agent 運用: `AGENTS.md`
