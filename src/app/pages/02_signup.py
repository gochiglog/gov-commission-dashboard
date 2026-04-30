import os
import sys
from pathlib import Path

import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.data_pipeline.user_store import add_user, email_exists  # noqa: E402

st.set_page_config(page_title='ユーザー登録', layout='centered')

_DASHBOARD_URL = 'https://gov-commission-dashboard.onrender.com'

st.title('ユーザー登録')

invite_token = st.query_params.get('invite', '')
valid_token = os.environ.get('INVITE_TOKEN', '')

if not valid_token:
    st.error('招待トークンが設定されていません。管理者にお問い合わせください。')
    st.stop()

if invite_token != valid_token:
    st.warning('このページにアクセスするには招待URLが必要です。')
    st.stop()

st.info('メールアドレスとパスワードを設定してアカウントを作成してください。')

with st.form('signup_form'):
    email = st.text_input('メールアドレス')
    password = st.text_input('パスワード（8文字以上）', type='password')
    password_confirm = st.text_input('パスワード（確認）', type='password')
    submitted = st.form_submit_button('アカウントを作成する')

if submitted:
    email = email.strip()
    if not email or '@' not in email:
        st.error('有効なメールアドレスを入力してください。')
    elif len(password) < 8:
        st.error('パスワードは8文字以上で設定してください。')
    elif password != password_confirm:
        st.error('パスワードが一致しません。')
    elif email_exists(email):
        st.warning('このメールアドレスはすでに登録されています。')
    else:
        try:
            # username にメールアドレスを使用することでログイン時にメアドで入力可能にする
            add_user(email, password, email)
        except Exception as e:
            st.error(f'登録に失敗しました: {e}')
            st.stop()
        st.success('アカウントを作成しました！')
        st.info(f'以下のURLにアクセスし、メールアドレスとパスワードでログインしてください。\n\n{_DASHBOARD_URL}')
