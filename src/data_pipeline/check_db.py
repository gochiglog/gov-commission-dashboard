"""SQLite DB の内容を簡易確認するスクリプト（要件2: データ整合性確認）。

使い方:
    python src/data_pipeline/check_db.py
"""
import sqlite3
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DB_PATH = _PROJECT_ROOT / 'data' / 'processed' / 'gov_commission.sqlite'


def main() -> None:
    if not _DB_PATH.exists():
        print(f'DB が見つかりません: {_DB_PATH}')
        sys.exit(1)

    with sqlite3.connect(_DB_PATH) as conn:
        # 総件数
        total = conn.execute('SELECT COUNT(*) FROM contracts').fetchone()[0]
        print(f'総件数: {total}\n')

        # 年度・省庁別件数
        print('=== 年度・省庁別件数 ===')
        rows = conn.execute("""
            SELECT
                CASE
                    WHEN CAST(strftime('%m', publish_date) AS INTEGER) >= 4
                    THEN CAST(strftime('%Y', publish_date) AS INTEGER)
                    ELSE CAST(strftime('%Y', publish_date) AS INTEGER) - 1
                END AS fiscal_year,
                ministry,
                COUNT(*) AS cnt
            FROM contracts
            GROUP BY fiscal_year, ministry
            ORDER BY fiscal_year, ministry
        """).fetchall()
        for fy, ministry, cnt in rows:
            print(f'  FY{fy}  {ministry:<8}  {cnt:4d} 件')

        # ユニーク事業者数
        n_contractors = conn.execute(
            'SELECT COUNT(DISTINCT contractor_name) FROM contracts'
        ).fetchone()[0]
        print(f'\nユニーク事業者数: {n_contractors}\n')

        # 受託件数上位10社
        print('=== 受託件数上位 10 社 ===')
        rows = conn.execute("""
            SELECT contractor_name, COUNT(*) AS cnt
            FROM contracts
            GROUP BY contractor_name
            ORDER BY cnt DESC
            LIMIT 10
        """).fetchall()
        for name, cnt in rows:
            print(f'  {cnt:4d} 件  {name}')

        # 連名（コンマ区切り）の残存チェック
        remaining = conn.execute(
            "SELECT COUNT(*) FROM contracts WHERE contractor_name LIKE '%,%'"
        ).fetchone()[0]
        print(f'\n連名残存チェック（contractor_name にコンマを含む行）: {remaining} 件')
        if remaining:
            print('  ⚠ 連名が残っています。meti_parser.py を再実行してください。')
        else:
            print('  OK: 連名なし（1行=1事業者の原則を満たしています）')


if __name__ == '__main__':
    main()
