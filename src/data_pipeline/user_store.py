import hashlib
import os
import secrets
import sqlite3
import string
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_USERS_DB_PATH = _PROJECT_ROOT / 'data' / 'processed' / 'users.sqlite'


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def generate_credentials() -> tuple[str, str]:
    username = 'user_' + secrets.token_hex(4)
    password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
    return username, password


# --- Supabase（本番: Render） ---

def _supabase():
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_KEY')
    if not url or not key:
        return None
    from supabase import create_client
    return create_client(url, key)


# --- SQLite（ローカル開発用フォールバック） ---

def _sqlite_conn() -> sqlite3.Connection:
    _USERS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_USERS_DB_PATH))
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    conn.commit()
    return conn


# --- 公開 API ---

def add_user(username: str, password: str, email: str) -> None:
    client = _supabase()
    if client:
        client.table('users').insert({
            'username': username,
            'password_hash': _hash(password),
            'email': email,
        }).execute()
    else:
        conn = _sqlite_conn()
        conn.execute(
            'INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)',
            (username, _hash(password), email),
        )
        conn.commit()
        conn.close()


def authenticate_user(login: str, password: str) -> bool:
    """username または email でログイン可能"""
    client = _supabase()
    if client:
        result = (
            client.table('users')
            .select('password_hash')
            .or_(f'username.eq.{login},email.eq.{login}')
            .execute()
        )
        if not result.data:
            return False
        return result.data[0]['password_hash'] == _hash(password)
    else:
        conn = _sqlite_conn()
        row = conn.execute(
            'SELECT password_hash FROM users WHERE username = ? OR email = ?', (login, login)
        ).fetchone()
        conn.close()
        return row is not None and row[0] == _hash(password)


def email_exists(email: str) -> bool:
    client = _supabase()
    if client:
        result = client.table('users').select('id').eq('email', email).execute()
        return len(result.data) > 0
    else:
        conn = _sqlite_conn()
        row = conn.execute('SELECT 1 FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        return row is not None


def delete_user(email: str) -> None:
    client = _supabase()
    if client:
        client.table('users').delete().eq('email', email).execute()
    else:
        conn = _sqlite_conn()
        conn.execute('DELETE FROM users WHERE email = ?', (email,))
        conn.commit()
        conn.close()
