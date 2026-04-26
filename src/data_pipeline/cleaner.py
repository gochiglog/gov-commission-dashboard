import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

_MAPPING_PATH = Path(__file__).resolve().parent.parent.parent / 'config' / 'mapping.json'


def _normalize(name: str) -> str:
    """事業者名を正規形に変換する。

    適用順:
    1. NFKC 正規化（全角記号・数字 → 半角、半角カナ → 全角）
    2. 全角・半角スペースの除去
    3. 法人格（株式会社 / (株)）の除去
    """
    name = unicodedata.normalize('NFKC', str(name))
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
