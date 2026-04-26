import datetime


def convert_reiwa_date(date_val: object) -> datetime.date:
    """'YY.MM.DD' 形式（令和年.月.日）の値を datetime.date（西暦）に変換する。

    令和年の変換式: 西暦年 = 令和年 + 2018
    例: '08.03.03' → datetime.date(2026, 3, 3)
    """
    parts = str(date_val).strip().split('.')
    reiwa_year = int(parts[0])
    month = int(parts[1])
    day = int(parts[2])
    return datetime.date(reiwa_year + 2018, month, day)
