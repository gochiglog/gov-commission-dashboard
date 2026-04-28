import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DB_PATH = _PROJECT_ROOT / 'data' / 'processed' / 'gov_commission.sqlite'
_AUTH_PATH = _PROJECT_ROOT / 'config' / 'auth.json'

sys.path.insert(0, str(_PROJECT_ROOT))
from src.data_pipeline.cleaner import clean_contractor_names, expand_multi_contractors  # noqa: E402

# データ不足のためデフォルトで非表示にする年度
_DEFAULT_HIDDEN_YEARS = {2021}

st.set_page_config(page_title='官公庁委託調査ダッシュボード', layout='wide')


# --- 認証 ---

def _authenticate(username: str, password: str) -> bool:
    try:
        with open(_AUTH_PATH, encoding='utf-8') as f:
            users = json.load(f).get('users', {})
        return users.get(username) == password
    except FileNotFoundError:
        st.error('認証設定ファイル (config/auth.json) が見つかりません。auth.json.example をコピーして作成してください。')
        return False


def _show_login() -> None:
    st.title('官公庁委託調査ダッシュボード')
    with st.form('login_form'):
        st.subheader('ログイン')
        username = st.text_input('ユーザーID')
        password = st.text_input('パスワード', type='password')
        if st.form_submit_button('ログイン'):
            if _authenticate(username, password):
                st.session_state['authenticated'] = True
                st.rerun()
            else:
                st.error('IDまたはパスワードが正しくありません')


if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    _show_login()
    st.stop()


# --- データ読み込み ---

@st.cache_data
def _load_data() -> pd.DataFrame:
    if not _DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(_DB_PATH))
    df = pd.read_sql('SELECT * FROM contracts', conn)
    conn.close()
    df['publish_date'] = pd.to_datetime(df['publish_date'])
    # ETL 後に追加された mapping.json の正規化ルールを反映
    df['contractor_name'] = clean_contractor_names(df['contractor_name'])
    # 連名行（コンマ区切り）を 1 社 1 行に展開（ETL 実行前の旧データへの対応も兼ねる）
    df = expand_multi_contractors(df)
    # 展開後の各ピースに再マッピング + ゴミフラグメント除去
    df['contractor_name'] = clean_contractor_names(df['contractor_name'])
    _JUNK_FRAGMENTS = {'Ltd.', 'Ltd', 'Pvt.', 'Pvt', 'Pte.', 'Pte', 'Co.', 'Inc.', 'Inc', 'Corp.', 'Corp', 'nan', ''}
    df = df[~df['contractor_name'].isin(_JUNK_FRAGMENTS)]
    # 年度を導出（4月始まり: 4月〜翌3月を同一年度とする）
    df['fiscal_year'] = df['publish_date'].apply(
        lambda d: d.year if d.month >= 4 else d.year - 1
    )
    return df


df = _load_data()

if df.empty:
    st.error('データが見つかりません。先に ETL スクリプト (meti_parser.py) を実行してください。')
    st.stop()


# --- サイドバー: フィルター ---

with st.sidebar:
    st.title('フィルター')

    ministries = sorted(df['ministry'].unique().tolist())
    selected_ministry = st.selectbox('省庁', ministries)

    base = df[df['ministry'] == selected_ministry].copy()

    all_years = sorted(base['fiscal_year'].unique().tolist())
    default_years = [y for y in all_years if y not in _DEFAULT_HIDDEN_YEARS]
    selected_years = st.multiselect(
        '対象年度',
        options=all_years,
        default=default_years,
        format_func=lambda y: f'{y}年度',
    )

    filtered = base[base['fiscal_year'].isin(selected_years)]

    top_contractors = (
        filtered.groupby('contractor_name')
        .size()
        .sort_values(ascending=False)
        .head(10)
        .index.tolist()
    )
    all_contractors = sorted(filtered['contractor_name'].unique().tolist())
    selected_contractors = st.multiselect(
        '委託事業者（複数選択可）',
        options=all_contractors,
        default=top_contractors,
    )

    st.divider()
    if st.button('ログアウト'):
        st.session_state['authenticated'] = False
        st.rerun()


# --- メインコンテンツ ---

st.title('官公庁委託調査ダッシュボード')
st.caption(
    f'省庁: {selected_ministry}　／　'
    f'対象年度: {len(selected_years)} 年度　／　'
    f'対象事業者: {len(selected_contractors)} 社'
)

if not selected_years:
    st.warning('対象年度を1年度以上選択してください')
    st.stop()

if not selected_contractors:
    st.warning('事業者を1社以上選択してください')
    st.stop()

agg = (
    filtered[filtered['contractor_name'].isin(selected_contractors)]
    .groupby(['fiscal_year', 'contractor_name'])
    .size()
    .reset_index(name='件数')
)

# 0件の年度もプロットして線で結ぶため、年度×事業者の直積で 0 埋めする
idx = pd.MultiIndex.from_product(
    [selected_years, selected_contractors],
    names=['fiscal_year', 'contractor_name'],
)
chart_df = (
    agg.set_index(['fiscal_year', 'contractor_name'])
    .reindex(idx, fill_value=0)
    .reset_index()
    .sort_values(['contractor_name', 'fiscal_year'])
)

fig = px.line(
    chart_df,
    x='fiscal_year',
    y='件数',
    color='contractor_name',
    markers=True,
    title='委託事業者別 年度別受託件数の推移',
    labels={'fiscal_year': '年度', 'contractor_name': '委託事業者'},
)
fig.update_xaxes(dtick=1, tickformat='d')
fig.update_layout(legend_title_text='委託事業者')
st.plotly_chart(fig, use_container_width=True)

with st.expander('集計データを表示'):
    pivot = (
        chart_df.pivot(index='contractor_name', columns='fiscal_year', values='件数')
        .fillna(0)
        .astype(int)
    )
    pivot.index.name = '委託事業者'
    pivot.columns.name = '年度'
    st.dataframe(pivot, use_container_width=True)
