"""
db_crypto.py — Field-level encryption for sensitive SDTF database columns
============================================================================
Encrypts AES keys, RSA public keys, and SHA-256 hashes before they are
written to users.db, and decrypts them right after they are read back.
This means that if users.db is ever leaked/stolen on its own, every
key/hash column inside it is unreadable ciphertext — not plain text.

The actual encryption key lives in a SEPARATE local file (db_secret.key,
created automatically next to users.db on first run) and is never stored
inside the database itself. So leaking the .db file alone reveals nothing.

⚠️ IMPORTANT
    - Keep db_secret.key safe and backed up. If it is lost, every
      encrypted value already in the database becomes permanently
      unreadable (there is no way to recover it without the key).
    - Never send/commit db_secret.key together with users.db — keep
      them on separate storage/backups.

Usage:
    from db_crypto import encrypt_field, decrypt_field

    cursor.execute("INSERT INTO manifest_details (aes_key) VALUES (?)",
                   (encrypt_field(aes_key),))
    ...
    row = cursor.fetchone()
    real_aes_key = decrypt_field(row[0])
"""

import os
from cryptography.fernet import Fernet, InvalidToken

# ─── SINGLE SOURCE OF TRUTH FOR THE ENCRYPTION KEY FILE ────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_PATH = os.path.join(BASE_DIR, "db_secret.key")
# ─────────────────────────────────────────────────────────────────


def _load_or_create_key() -> bytes:
    """
    Loads the existing encryption key, or creates a new one on first run.
    Safe to call from multiple modules — the key file is only written once.
    """
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, "rb") as f:
            key = f.read().strip()
        if key:
            return key

    key = Fernet.generate_key()
    with open(KEY_PATH, "wb") as f:
        f.write(key)
    try:
        os.chmod(KEY_PATH, 0o600)  # owner-only read/write (no effect on Windows)
    except Exception:
        pass
    print(f"[db_crypto] New DB encryption key created at: {KEY_PATH}")
    print("[db_crypto] KEEP THIS FILE SAFE — losing it makes all encrypted DB data unrecoverable.")
    return key


_fernet = Fernet(_load_or_create_key())


def is_encrypted(value) -> bool:
    """Returns True if `value` is already a valid token produced by this module."""
    if not value:
        return False
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except Exception:
            return False
    try:
        _fernet.decrypt(value.encode("utf-8"))
        return True
    except Exception:
        return False


def encrypt_field(value):
    """
    Encrypts a string before it is stored in the database.
    - None / "" pass through unchanged.
    - Already-encrypted values pass through unchanged (safe to call twice).
    """
    if value is None or value == "":
        return value
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    if is_encrypted(value):
        return value
    return _fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_field(value):
    """
    Decrypts a value read from the database.
    Backward-compatible: if the value is NOT a valid encrypted token
    (e.g. an old plain-text row saved before encryption was added),
    it is returned unchanged instead of raising an error.
    """
    if value is None or value == "":
        return value
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    try:
        return _fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return value
    except Exception:
        return value
