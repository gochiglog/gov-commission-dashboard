import argparse
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.data_pipeline.cleaner import clean_contractor_names, expand_multi_contractors  # noqa: E402
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
    """Excel を読み込み、正規化・連名展開済みの DataFrame を返す。

    usecols を指定せず全列読み込みにすることで、年度によって「管理番号」列の
    有無が異なる場合でも列名ベースで正しく選択できる。
    連名（コンマ・全角読点区切り）の contractor_name は 1 社 1 行に展開する。
    """
    df = pd.read_excel(excel_path, header=1, engine='openpyxl')
    df.columns = [_normalize_header(c) for c in df.columns]
    df = df.rename(columns=_COLUMN_MAP)
    df['ministry'] = 'METI'
    df['publish_date'] = df['publish_date'].apply(convert_reiwa_date)
    df['contractor_name'] = clean_contractor_names(df['contractor_name'])
    for col in _OUTPUT_COLS:
        if col not in df.columns:
            df[col] = None
    df = df[_OUTPUT_COLS].dropna(subset=['publish_date', 'report_title'])
    # 「（続き）」のみの継続タイトル行と、contractor_name が nan の不正行を除去
    df = df[~df['report_title'].astype(str).str.strip().isin(['（続き）', '(続き)'])]
    df = df[~df['contractor_name'].isin(['nan', 'NaN', 'None', ''])]
    # 連名行を 1 社 1 行に展開（コンマ・全角読点区切り）
    df = expand_multi_contractors(df)
    # 展開後の各ピースに再マッピングを適用（多社行から分割された社名が未マッピングになる問題を防ぐ）
    df['contractor_name'] = clean_contractor_names(df['contractor_name'])
    # "Co., Ltd." 等のカンマ分割で生じた法人種別サフィックスのゴミフラグメントを除去
    _JUNK_FRAGMENTS = {'Ltd.', 'Ltd', 'Pvt.', 'Pvt', 'Pte.', 'Pte', 'Co.', 'Inc.', 'Inc', 'Corp.', 'Corp', 'nan', ''}
    df = df[~df['contractor_name'].isin(_JUNK_FRAGMENTS)]
    return df


def save_csv(df: pd.DataFrame, excel_path: Path) -> Path:
    """クリーン CSV を data/processed/ に UTF-8 BOM付きで保存する。"""
    _PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = _PROCESSED_DIR / f'{excel_path.stem}_clean.csv'
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    return csv_path


def save_sqlite(df: pd.DataFrame, fiscal_year: int | None = None) -> None:
    """contracts テーブルを更新する。

    fiscal_year を指定した場合は対象年度・省庁の既存レコードを削除してから
    挿入する（べき等性の確保）。指定しない場合は従来通り追記する。
    """
    _PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB_PATH) as conn:
        if fiscal_year is not None:
            # 同一ファイルの再実行で重複しないよう、同年度の METI レコードを先に削除
            start_date = f'{fiscal_year}-04-01'
            end_date = f'{fiscal_year + 1}-03-31'
            deleted = conn.execute(
                "DELETE FROM contracts WHERE ministry = 'METI' "
                'AND publish_date >= ? AND publish_date <= ?',
                (start_date, end_date),
            ).rowcount
            if deleted:
                print(f'  既存レコード削除: FY{fiscal_year}  {deleted} 件')
        df.to_sql('contracts', conn, if_exists='append', index=False)


def rebuild_all(raw_dir: Path) -> None:
    """raw_dir 配下の全 METI Excel を一括処理し DB を再構築する。

    各ファイルが年度をまたぐ累積データを含む場合でも重複を排除して
    正しいレコードセットを構築する。
    """
    xlsx_files = sorted(raw_dir.glob('*_METI.xlsx'))
    if not xlsx_files:
        print(f'Excel ファイルが見つかりません: {raw_dir}/*_METI.xlsx')
        return

    frames: list[pd.DataFrame] = []
    for f in xlsx_files:
        df = parse(f)
        save_csv(df, f)
        print(f'  パース完了: {f.name}  {len(df)} 件')
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    before = len(combined)
    combined = combined.drop_duplicates(
        subset=['ministry', 'publish_date', 'report_title', 'contractor_name'],
        keep='first',
    )
    after = len(combined)
    print(f'\n結合後: {before} 件  →  重複排除後: {after} 件（{before - after} 件削除）')

    _PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB_PATH) as conn:
        deleted = conn.execute("DELETE FROM contracts WHERE ministry = 'METI'").rowcount
        if deleted:
            print(f'既存 METI レコード全削除: {deleted} 件')
        combined.to_sql('contracts', conn, if_exists='append', index=False)
    print(f'SQLite 再構築完了: {_DB_PATH}  ({after} 件)')


def main(excel_path: Path) -> None:
    # ファイル名先頭の 4 桁を年度として扱う（例: 2024_METI.xlsx → FY2024）
    year_match = re.match(r'(\d{4})', excel_path.stem)
    fiscal_year = int(year_match.group(1)) if year_match else None

    df = parse(excel_path)
    csv_path = save_csv(df, excel_path)
    print(f'クリーン CSV: {csv_path}  ({len(df)} 件, 連名展開後)')
    save_sqlite(df, fiscal_year)
    if fiscal_year:
        print(f'SQLite 更新: {_DB_PATH}  (FY{fiscal_year} を入れ替え, {len(df)} 件)')
    else:
        print(f'SQLite 更新: {_DB_PATH}  ({len(df)} 件追記)')


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(description='経産省 Excel → クリーン CSV + SQLite')
    mode = arg_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--file', type=Path, help='処理対象の Excel ファイル (data/raw/YYYY_METI.xlsx)')
    mode.add_argument(
        '--rebuild-all',
        metavar='RAW_DIR',
        type=Path,
        nargs='?',
        const=_PROJECT_ROOT / 'data' / 'raw',
        help='data/raw 配下の全 Excel を一括処理して DB を再構築する（デフォルト: data/raw）',
    )
    args = arg_parser.parse_args()
    if args.file:
        main(args.file)
    else:
        rebuild_all(args.rebuild_all)
