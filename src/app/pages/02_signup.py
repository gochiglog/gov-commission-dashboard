import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import streamlit as st

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.data_pipeline.user_store import add_user, delete_user, email_exists, generate_credentials  # noqa: E402

st.set_page_config(page_title='ユーザー登録', layout='centered')

_DASHBOARD_URL = 'https://gov-commission-dashboard.onrender.com'


def _send_credentials(to_email: str, username: str, password: str) -> bool:
    gmail_user = os.environ.get('GMAIL_USER', '')
    gmail_app_password = os.environ.get('GMAIL_APP_PASSWORD', '')
    if not gmail_user or not gmail_app_password:
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = '【官公庁委託調査ダッシュボード】ログイン情報'
        msg['From'] = gmail_user
        msg['To'] = to_email
        html = (
            '<p>官公庁委託調査ダッシュボードへのご登録ありがとうございます。</p>'
            '<p>以下のログイン情報でアクセスできます。</p>'
            '<table border="0" cellpadding="6">'
            f'<tr><td>ユーザーID</td><td><strong>{username}</strong></td></tr>'
            f'<tr><td>パスワード</td><td><strong>{password}</strong></td></tr>'
            '</table>'
            '<br><p>上記のユーザーIDとパスワードを使って、以下のURLからログインしてください。</p>'
            f'<p><a href="{_DASHBOARD_URL}">{_DASHBOARD_URL}</a></p>'
            '<p><small>このメールに心当たりがない場合は無視してください。</small></p>'
        )
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_user, gmail_app_password)
            server.sendmail(gmail_user, to_email, msg.as_string())
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
            # メール送信失敗時はユーザーを削除してロールバック
            delete_user(email)
            st.error(
                'メール送信に失敗しました。しばらく待ってから再度お試しください。'
                '問題が続く場合は管理者にお問い合わせください。'
            )
