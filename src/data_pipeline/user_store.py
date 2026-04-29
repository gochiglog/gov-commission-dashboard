import hashlib
import secrets
import sqlite3
import string
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_USERS_DB_PATH = _PROJECT_ROOT / 'data' / 'processed' / 'users.sqlite'


def _get_conn() -> sqlite3.Connection:
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


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def generate_credentials() -> tuple[str, str]:
    username = 'user_' + secrets.token_hex(4)
    password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
    return username, password


def add_user(username: str, password: str, email: str) -> None:
    conn = _get_conn()
    conn.execute(
        'INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)',
        (username, _hash(password), email),
    )
    conn.commit()
    conn.close()


def authenticate_user(username: str, password: str) -> bool:
    conn = _get_conn()
    row = conn.execute(
        'SELECT password_hash FROM users WHERE username = ?', (username,)
    ).fetchone()
    conn.close()
    return row is not None and row[0] == _hash(password)


def email_exists(email: str) -> bool:
    conn = _get_conn()
    row = conn.execute('SELECT 1 FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    return row is not None
