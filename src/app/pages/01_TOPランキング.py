import json
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DB_PATH = _PROJECT_ROOT / 'data' / 'processed' / 'gov_commission.sqlite'
_AUTH_PATH = _PROJECT_ROOT / 'config' / 'auth.json'

sys.path.insert(0, str(_PROJECT_ROOT))
from src.data_pipeline.cleaner import clean_contractor_names, expand_multi_contractors  # noqa: E402

st.set_page_config(page_title='TOP ランキング', layout='wide')


# --- 認証 ---

def _authenticate(username: str, password: str) -> bool:
    env_user = os.environ.get('ADMIN_USERNAME')
    env_pass = os.environ.get('ADMIN_PASSWORD')
    if env_user and env_pass:
        return username == env_user and password == env_pass
    try:
        with open(_AUTH_PATH, encoding='utf-8') as f:
            users = json.load(f).get('users', {})
        return users.get(username) == password
    except FileNotFoundError:
        st.error('認証設定ファイル (config/auth.json) が見つかりません。')
        return False


if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
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
    df['contractor_name'] = clean_contractor_names(df['contractor_name'])
    df = expand_multi_contractors(df)
    df['contractor_name'] = clean_contractor_names(df['contractor_name'])
    _JUNK_FRAGMENTS = {'Ltd.', 'Ltd', 'Pvt.', 'Pvt', 'Pte.', 'Pte', 'Co.', 'Inc.', 'Inc', 'Corp.', 'Corp', 'nan', ''}
    df = df[~df['contractor_name'].isin(_JUNK_FRAGMENTS)]
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

    base = df[df['ministry'] == selected_ministry]
    all_years = sorted(base['fiscal_year'].unique().tolist())

    period_options = ['総合（全年度）'] + [f'{y}年度' for y in all_years]
    selected_period = st.selectbox('期間', period_options, index=0)

    top_n = st.number_input('表示件数', min_value=1, value=10, step=1)

    st.divider()
    if st.button('ログアウト'):
        st.session_state['authenticated'] = False
        st.rerun()


# --- メインコンテンツ ---

st.title('TOP 受託事業者ランキング')
st.caption(
    f'省庁: {selected_ministry}　／　'
    f'期間: {selected_period}　／　'
    f'表示: TOP {int(top_n)}'
)

if selected_period == '総合（全年度）':
    target = base
else:
    year = int(selected_period.replace('年度', ''))
    target = base[base['fiscal_year'] == year]

col1, col2 = st.columns(2)
col1.metric('期間内の総受託件数', f'{len(target):,} 件')
col2.metric('ユニーク事業者数', f'{target["contractor_name"].nunique():,} 社')

ranking = (
    target.groupby('contractor_name')
    .size()
    .reset_index(name='受託件数')
    .sort_values('受託件数', ascending=False)
    .head(int(top_n))
    .reset_index(drop=True)
)
ranking.insert(0, '順位', ranking.index + 1)
ranking = ranking.rename(columns={'contractor_name': '事業者名'})

st.dataframe(
    ranking,
    use_container_width=True,
    hide_index=True,
    column_config={
        '順位': st.column_config.NumberColumn(width='small'),
        '事業者名': st.column_config.TextColumn(width='large'),
        '受託件数': st.column_config.NumberColumn(width='medium'),
    },
)
