import os
import sys
from pathlib import Path

import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.data_pipeline.user_store import add_user, email_exists, generate_credentials  # noqa: E402

st.set_page_config(page_title='ユーザー登録', layout='centered')

_DASHBOARD_URL = 'https://gov-commission-dashboard.onrender.com'
_FROM_EMAIL = os.environ.get('RESEND_FROM_EMAIL', 'onboarding@resend.dev')


def _send_credentials(to_email: str, username: str, password: str) -> bool:
    api_key = os.environ.get('RESEND_API_KEY', '')
    if not api_key:
        return False
    try:
        import resend
        resend.api_key = api_key
        resend.Emails.send({
            'from': _FROM_EMAIL,
            'to': [to_email],
            'subject': '【官公庁委託調査ダッシュボード】ログイン情報',
            'html': (
                '<p>官公庁委託調査ダッシュボードへのご登録ありがとうございます。</p>'
                '<p>以下のログイン情報でアクセスできます。</p>'
                '<table border="0" cellpadding="6">'
                f'<tr><td>ユーザーID</td><td><strong>{username}</strong></td></tr>'
                f'<tr><td>パスワード</td><td><strong>{password}</strong></td></tr>'
                '</table>'
                f'<br><p>ダッシュボード: <a href="{_DASHBOARD_URL}">{_DASHBOARD_URL}</a></p>'
                '<p><small>このメールに心当たりがない場合は無視してください。</small></p>'
            ),
        })
        return True
    except Exception:
        return False


st.title('ユーザー登録')

invite_token = st.query_params.get('invite', '')
valid_token = os.environ.get('INVITE_TOKEN', '')

if not valid_token:
    st.error('招待トークンが設定されていません。管理者にお問い合わせください。')
    st.stop()

if invite_token != valid_token:
    st.warning('このページにアクセスするには招待URLが必要です。')
    st.stop()

st.info('メールアドレスを入力すると、ダッシュボードのログイン用IDとパスワードをお送りします。')

with st.form('signup_form'):
    email = st.text_input('メールアドレス')
    submitted = st.form_submit_button('登録してログイン情報を受け取る')

if submitted:
    email = email.strip()
    if not email or '@' not in email:
        st.error('有効なメールアドレスを入力してください。')
    elif email_exists(email):
        st.warning('このメールアドレスはすでに登録されています。')
    else:
        username, password = generate_credentials()
        try:
            add_user(username, password, email)
        except Exception as e:
            st.error(f'ユーザー登録に失敗しました: {e}')
            st.stop()

        if _send_credentials(email, username, password):
            st.success(f'{email} にログイン情報をお送りしました。メールをご確認ください。')
        else:
            st.warning('メール送信に失敗しました（RESEND_API_KEY を確認してください）。以下のログイン情報を直接お使いください。')
            st.code(f'ユーザーID: {username}\nパスワード: {password}')
