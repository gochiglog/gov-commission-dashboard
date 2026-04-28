import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

_MAPPING_PATH = Path(__file__).resolve().parent.parent.parent / 'config' / 'mapping.json'


def _normalize(name: str) -> str:
    """事業者名を正規形に変換する。

    適用順:
    1. NFKC 正規化（全角記号・数字 → 半角、半角カナ → 全角。全角コンマ「，」→「,」も含む）
    2. Excel/openpyxl 由来の制御文字エスケープ (_x000B_ など) と制御文字本体の除去
    3. 全角読点「、」を半角コンマ「,」に変換（複数事業者の区切り文字を統一するため）
    4. 全角・半角スペースの除去
    5. 法人格（株式会社 / (株)）の除去
    """
    name = unicodedata.normalize('NFKC', str(name))
    name = re.sub(r'_x[0-9A-Fa-f]{4}_', '', name)
    name = re.sub(r'[\x00-\x08\x0B-\x1F\x7F]', '', name)
    name = name.replace('、', ',')
    name = re.sub(r'[\s　]', '', name)
    name = name.replace('株式会社', '').replace('(株)', '')
    return name.strip()


def clean_contractor_names(series: pd.Series, mapping_path: Path = _MAPPING_PATH) -> pd.Series:
    """pandas.Series の事業者名を正規化し、mapping.json で追加統一を行う。"""
    with open(mapping_path, encoding='utf-8') as f:
        overrides: dict = json.load(f).get('mappings', {})

    def _apply(raw: object) -> str:
        normalized = _normalize(str(raw))
        return overrides.get(normalized, normalized)

    return series.apply(_apply)


def expand_multi_contractors(df: pd.DataFrame) -> pd.DataFrame:
    """contractor_name にコンマ区切りで複数事業者が含まれる行を 1 社 1 行に展開する。

    clean_contractor_names 適用後を想定しており、区切り文字はすべて半角コンマ「,」に
    正規化済みであることを前提とする（全角コンマ・全角読点は _normalize で変換済み）。
    """
    df = df.copy()
    df['contractor_name'] = df['contractor_name'].str.split(',')
    df = df.explode('contractor_name')
    df['contractor_name'] = df['contractor_name'].str.strip()
    df = df[df['contractor_name'].notna() & (df['contractor_name'] != '')]
    return df.reset_index(drop=True)
