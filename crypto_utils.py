"""
crypto_utils.py
A login password can be one-way hashed (bcrypt) because we only ever
need to CHECK it, never see it again. A database password is
different — we need to actually USE it to connect, repeatedly, so it
must be reversible. This module encrypts it instead, using a secret
key that only this application knows (stored in secrets.toml, never
in the database itself).
"""

import os
from cryptography.fernet import Fernet, InvalidToken


def _get_encryption_key() -> bytes:
    """Reads the encryption key from Streamlit secrets, falling back to
    an environment variable for testing outside a Streamlit context."""
    key = None
    try:
        import streamlit as st
        key = st.secrets.get("encryption", {}).get("key")
    except Exception:
        pass

    if not key:
        key = os.environ.get("REPORT_ENCRYPTION_KEY")

    if not key:
        raise RuntimeError(
            "No encryption key configured. Add an [encryption] section "
            "with a 'key' to secrets.toml — generate one with:\n"
            "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    return key.encode() if isinstance(key, str) else key


def encrypt_value(plain_text: str) -> str:
    """Returns an encrypted string, safe to store on disk."""
    f = Fernet(_get_encryption_key())
    return f.encrypt(plain_text.encode()).decode()


def decrypt_value(encrypted_text: str) -> str:
    """Reverses encrypt_value(). Raises a clear error if the key is
    wrong or the data was tampered with, rather than silently
    returning garbage."""
    f = Fernet(_get_encryption_key())
    try:
        return f.decrypt(encrypted_text.encode()).decode()
    except InvalidToken:
        raise ValueError(
            "Could not decrypt this value — the encryption key may have "
            "changed, or the stored data is corrupted."
        )