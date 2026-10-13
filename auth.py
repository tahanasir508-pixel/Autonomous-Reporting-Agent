"""
auth.py
Manual (email/password) account system, backed by a local SQLite
database. Passwords are never stored in plain text — only a bcrypt
hash, which is a one-way function (you can check "does this password
match the stored hash" but can never recover the original password
from what's stored, even if the database file leaks).

This is separate from Google sign-in (handled by Streamlit's own
st.login()); this module only covers the manual email/password path.
"""

import re
import sqlite3
from pathlib import Path

import bcrypt

DB_PATH = Path("users.db")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash BLOB NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return conn


def create_user(email: str, password: str) -> tuple[bool, str]:
    """Returns (success, message). Rejects duplicate emails, weak
    passwords, and malformed email addresses before ever touching the
    database, so bad input never gets a confusing SQL-level error."""
    email = email.strip().lower()

    if not EMAIL_RE.match(email):
        return False, "That doesn't look like a valid email address."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."

    conn = _get_connection()
    try:
        existing = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return False, "An account with this email already exists. Try logging in instead."

        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash),
        )
        conn.commit()
        return True, "Account created successfully."
    finally:
        conn.close()


def verify_user(email: str, password: str) -> tuple[bool, str]:
    """Returns (success, message). Deliberately gives the same generic
    error for 'no such user' and 'wrong password' — telling an attacker
    WHICH one was wrong is a real, well-known security leak (it lets
    them enumerate which emails have accounts)."""
    email = email.strip().lower()

    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()

        if row is None:
            return False, "Incorrect email or password."

        stored_hash = row[0]
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
            return True, "Logged in successfully."
        else:
            return False, "Incorrect email or password."
    finally:
        conn.close()