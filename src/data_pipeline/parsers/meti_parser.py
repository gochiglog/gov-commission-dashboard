import argparse
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.data_pipeline.cleaner import clean_contractor_names  # noqa: E402
from src.utils.wareki_converter import convert_reiwa_date  # noqa: E402

_PROCESSED_DIR = _PROJECT_ROOT / 'data' / 'processed'
_DB_PATH = _PROCESSED_DIR / 'gov_commission.sqlite'

_COLUMN_MAP = {
    '掲載日': 'publish_date',
    '委託調査報告書名': 'report_title',
    '委託事業者名': 'contractor_name',
    '担当課室名': 'department',
    'HPアドレス(報告書)': 'url',
}

_OUTPUT_COLS = ['ministry', 'publish_date', 'report_title', 'contractor_name', 'department', 'url']


def _normalize_header(col: str) -> str:
    """ヘッダー文字列を正規化する: NFKC + 全角/半角スペース除去。"""
    normalized = unicodedata.normalize('NFKC', str(col))
    return re.sub(r'[\s　]', '', normalized)


def parse(excel_path: Path) -> pd.DataFrame:
    """Excel を読み込み、正規化済み DataFrame を返す。

    usecols を指定せず全列読み込みにすることで、年度によって「管理番号」列の
    有無が異なる場合でも列名ベースで正しく選択できる。
    """
    df = pd.read_excel(excel_path, header=1, engine='openpyxl')
    df.columns = [_normalize_header(c) for c in df.columns]
    df = df.rename(columns=_COLUMN_MAP)
    df['ministry'] = 'METI'
    df['publish_date'] = df['publish_date'].apply(convert_reiwa_date)
    df['contractor_name'] = clean_contractor_names(df['contractor_name'])
    # 年度によって存在しない列（url 等）は None で補完してから選択
    for col in _OUTPUT_COLS:
        if col not in df.columns:
            df[col] = None
    return df[_OUTPUT_COLS].dropna(subset=['publish_date', 'report_title'])


def save_csv(df: pd.DataFrame, excel_path: Path) -> Path:
    """クリーン CSV を data/processed/ に UTF-8 BOM付きで保存する。"""
    _PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = _PROCESSED_DIR / f'{excel_path.stem}_clean.csv'
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    return csv_path


def save_sqlite(df: pd.DataFrame) -> None:
    """contracts テーブルに追記する（テーブルが無ければ自動作成）。"""
    _PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB_PATH) as conn:
        df.to_sql('contracts', conn, if_exists='append', index=False)


def main(excel_path: Path) -> None:
    df = parse(excel_path)
    csv_path = save_csv(df, excel_path)
    print(f'クリーン CSV: {csv_path}')
    save_sqlite(df)
    print(f'SQLite 更新: {_DB_PATH}  ({len(df)} 件追記)')


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(description='経産省 Excel → クリーン CSV + SQLite')
    arg_parser.add_argument('--file', type=Path, required=True, help='処理対象の Excel ファイル (data/raw/YYYY_METI.xlsx)')
    args = arg_parser.parse_args()
    main(args.file)
