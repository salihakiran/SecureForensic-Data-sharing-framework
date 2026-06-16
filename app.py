# import sys
# import sqlite3
# import re
# import random
# import smtplib
# import ssl
# from PyQt5 import QtWidgets, QtCore, QtGui
# import os

# try:
#     import bcrypt
# except ImportError:
#     print("ERROR: bcrypt missing. Run: pip install bcrypt")
#     bcrypt = None

# from key_exchange import generate_rsa_key_pair, private_key_exists

# from dotenv import load_dotenv
# load_dotenv()
# # =======================================================
# # OTP EMAIL CONFIG — uses same Gmail as sender
# # Change these or load from .env (see SUPERADMIN section)
# # =======================================================
# OTP_SENDER_EMAIL    = os.getenv("OTP_SENDER_EMAIL")
# OTP_SENDER_PASSWORD = os.getenv("OTP_SENDER_PASSWORD")
# # //
# SUPERADMIN_NAME     = os.getenv("SUPERADMIN_NAME")
# SUPERADMIN_EMAIL    = os.getenv("SUPERADMIN_EMAIL")
# SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD")
# SUPERADMIN_ROLE     = "SuperAdmin"
import sys
import sqlite3
import re
import random
import smtplib
import ssl
from PyQt5 import QtWidgets, QtCore, QtGui
import os
from datetime import datetime

# ─── SINGLE SOURCE OF TRUTH FOR DB PATH ───────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'users.db')
# ──────────────────────────────────────────────────────────
import os
try:
    import bcrypt
except ImportError:
    print("ERROR: bcrypt missing. Run: pip install bcrypt")
    bcrypt = None

from key_exchange import generate_rsa_key_pair, private_key_exists
from db_crypto import encrypt_field, decrypt_field, is_encrypted
from dotenv import load_dotenv
load_dotenv()
# =======================================================
# OTP EMAIL CONFIG — uses same Gmail as sender
# Change these or load from .env (see SUPERADMIN section)
# =======================================================
OTP_SENDER_EMAIL    = os.getenv("OTP_SENDER_EMAIL",    "sdtf.forensic@gmail.com")
OTP_SENDER_PASSWORD = os.getenv("OTP_SENDER_PASSWORD", "xxxx xxxx xxxx xxxx")
SUPERADMIN_NAME     = os.getenv("SUPERADMIN_NAME")
SUPERADMIN_EMAIL    = os.getenv("SUPERADMIN_EMAIL")
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD")
SUPERADMIN_ROLE     = "SuperAdmin"

# =======================================================
# PASSWORD HASHING HELPERS (bcrypt)
# =======================================================
def hash_password(plain: str) -> str:
    """Hashes a plain-text password with bcrypt. Returns a str for DB storage."""
    if not bcrypt:
        return plain   # fallback if bcrypt not installed
    return bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    """
    Verifies plain password against bcrypt hash.
    Also accepts old plain-text passwords (during migration window)
    so existing accounts still work until they re-register.
    """
    if not bcrypt:
        return plain == hashed
    # Detect if stored value is already a bcrypt hash
    if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
        try:
            return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False
    # Legacy plain-text password — still accept it (migration window)
    return plain == hashed


# =======================================================
# OTP HELPERS
# =======================================================
def generate_otp() -> str:
    """Returns a 6-digit numeric OTP string."""
    return str(random.randint(100000, 999999))

def send_otp_email(receiver_email: str, otp: str, name: str) -> bool:
    """
    Sends OTP to receiver_email via Gmail SMTP SSL.
    Returns True on success, False on failure.
    """
    try:
        socket_check = True
        import socket as _socket
        try:
            _socket.create_connection(("8.8.8.8", 53), timeout=3)
        except OSError:
            socket_check = False

        if not socket_check:
            print("[OTP] No internet — cannot send OTP email.")
            return False

        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=30) as server:
            server.login(OTP_SENDER_EMAIL, OTP_SENDER_PASSWORD)
            from email.message import EmailMessage
            msg = EmailMessage()
            msg["From"]    = OTP_SENDER_EMAIL
            msg["To"]      = receiver_email
            msg["Subject"] = "[SDTF] Your Registration OTP Code"
            msg.set_content(
                f"Hello {name},\n\n"
                f"Your One-Time Password (OTP) for SDTF registration is:\n\n"
                f"        {otp}\n\n"
                f"This code is valid for this session only.\n"
                f"Do NOT share it with anyone.\n\n"
                f"If you did not request this, ignore this email.\n\n"
                f"--- SDTF Automated Security System ---"
            )
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[OTP Email Error] {e}")
        return False



    
# =======================================================
# CREATE DATABASE TABLES
# =======================================================
def create_users_db():
    conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # ── USERS TABLE ─────────────────────────────────────────────
    #is_approved : 0 = pending, 1 = approved
    #is_revoked  : 0 = active,  1 = revoked
    # SuperAdmin is seeded with is_approved=1, is_revoked=0 automatically
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT    NOT NULL,
        password    TEXT    NOT NULL,
        email       TEXT    UNIQUE,
        role        TEXT,
        public_key  TEXT,
        is_approved INTEGER DEFAULT 0,
        is_revoked  INTEGER DEFAULT 0,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS forensic_files (
        file_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id       TEXT NOT NULL,
        file_name     TEXT NOT NULL,
        original_hash TEXT NOT NULL,
        file_size     TEXT,
        sender_name   TEXT,
        timestamp     DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS manifest_details (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id           TEXT,
        aes_key           TEXT,
        investigator_name TEXT,
        creation_date     DATETIME
    )''')

    # ── VAULT TRANSFERS TABLE ────────────────────────────────────
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vault_transfers (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_name       TEXT    NOT NULL,
        receiver_email    TEXT    NOT NULL,
        vault_path        TEXT    NOT NULL,
        encrypted_aes_key BLOB    NOT NULL,
        original_hash     TEXT    NOT NULL,
        file_name         TEXT    NOT NULL,
        method            TEXT    DEFAULT "Email",
        status            TEXT    DEFAULT "PENDING",
        case_id           TEXT,
        investigator      TEXT,
        created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
        fetched_at        DATETIME
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS integrity_audit (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_hash      TEXT,
        receiver_hash    TEXT,
        integrity_status TEXT,
        audit_time       DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chain_of_custody (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id         TEXT,
        action          TEXT,
        performed_by    TEXT,
        timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
        location_device TEXT
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS anomaly_alerts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type  TEXT,
        description TEXT,
        severity    TEXT,
        timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS system_monitor_logs (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        event_source TEXT,
        event_type   TEXT,
        details      TEXT,
        timestamp    DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS forensic_receipts (
        receipt_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        generated_by   TEXT,
        hash_confirmed TEXT,
        receipt_path   TEXT
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS login_history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT,
        login_time  DATETIME,
        logout_time DATETIME,
        status      TEXT
    )''')

    # ── SHARED NOTIFICATIONS TABLE ───────────────────────────────
    # Single table read by ALL dashboards for real-time bell updates.
    # target_role: "Sender" | "Receiver" | "Admin" | "SuperAdmin" | "All"
    # is_read    : 0 = unread (triggers bell), 1 = read (already shown)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS shared_notifications (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        target_role TEXT    NOT NULL,
        target_user TEXT,
        message     TEXT    NOT NULL,
        category    TEXT    DEFAULT "Info",
        is_read     INTEGER DEFAULT 0,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # ── AUDIT LOGS TABLE ─────────────────────────────────────────
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS audit_logs (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        username  TEXT,
        role      TEXT,
        action    TEXT,
        method    TEXT,
        file_name TEXT,
        details   TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()
    print("Database and all tables created successfully.")


# =======================================================
# MIGRATION — adds new columns safely to existing DBs
# =======================================================
def migrate_existing_db():
    """
    Safe migration — adds new columns/tables without losing data.
    Called at every startup after create_users_db().
    """
    conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(users)")
    existing_cols = [row[1] for row in cursor.fetchall()]

    # Add new columns if missing.
    # NOTE: SQLite does not allow ALTER TABLE ADD COLUMN with a
    # non-constant default (e.g. CURRENT_TIMESTAMP), so created_at
    # is added as plain TEXT and then backfilled for existing rows.
    simple_columns = {
        "public_key":  "TEXT",
        "is_approved": "INTEGER DEFAULT 0",
        "is_revoked":  "INTEGER DEFAULT 0",
    }
    for col, col_type in simple_columns.items():
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
            print(f"[Migration] Added '{col}' column to users table.")

    if "created_at" not in existing_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
        cursor.execute(
            "UPDATE users SET created_at = datetime('now') WHERE created_at IS NULL"
        )
        print("[Migration] Added 'created_at' column and backfilled existing rows.")

    # ── BCRYPT MIGRATION ─────────────────────────────────────────
    # Hash any existing plain-text passwords that were stored before
    # bcrypt was introduced. Safe to run multiple times — already-hashed
    # passwords start with "$2b$" and are skipped automatically.
    if bcrypt:
        cursor.execute("SELECT id, password FROM users")
        rows = cursor.fetchall()
        migrated = 0
        for uid, pw in rows:
            if pw and not (pw.startswith("$2b$") or pw.startswith("$2a$")):
                hashed = bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute("UPDATE users SET password=? WHERE id=?", (hashed, uid))
                migrated += 1
        if migrated:
            print(f"[Migration] Hashed {migrated} plain-text password(s) with bcrypt.")

        conn.commit()

    # vault_transfers
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vault_transfers (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_name       TEXT    NOT NULL,
        receiver_email    TEXT    NOT NULL,
        vault_path        TEXT    NOT NULL,
        encrypted_aes_key BLOB    NOT NULL,
        original_hash     TEXT    NOT NULL,
        file_name         TEXT    NOT NULL,
        method            TEXT    DEFAULT "Email",
        status            TEXT    DEFAULT "PENDING",
        case_id           TEXT,
        investigator      TEXT,
        created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
        fetched_at        DATETIME
    )''')

    # audit_logs
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS audit_logs (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        username  TEXT,
        role      TEXT,
        action    TEXT,
        method    TEXT,
        file_name TEXT,
        details   TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # session_keys
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS session_keys (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        transfer_id    INTEGER UNIQUE,
        receiver_email TEXT NOT NULL,
        file_name      TEXT NOT NULL,
        aes_key        TEXT NOT NULL,
        original_hash  TEXT NOT NULL,
        created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (transfer_id) REFERENCES vault_transfers(id)
    )''')

    # shared_notifications — cross-dashboard real-time bell
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS shared_notifications (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        target_role TEXT    NOT NULL,
        target_user TEXT,
        message     TEXT    NOT NULL,
        category    TEXT    DEFAULT "Info",
        is_read     INTEGER DEFAULT 0,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # ── DROP UNUSED TABLES from old schema ───────────────────────
    # receiver_logs and transfers were created in original schema
    # but are never written to by the app — remove them cleanly.
    for old_table in ["receiver_logs", "transfers"]:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {old_table}")
            print(f"[Migration] Dropped unused table: {old_table}")
        except Exception as e:
            print(f"[Migration] Could not drop {old_table}: {e}")
    # ── DROP unused columns ───────────────────────────────────
    # ── DROP unused columns (works on ALL SQLite versions) ────
    cursor.execute("PRAGMA foreign_keys = OFF")

    _rebuild_table_without_columns(cursor, "users", 
    ["status", "verfication_token", "is_verified"])

    _rebuild_table_without_columns(cursor, "manifest_details", 
    ["file_id"])

    _rebuild_table_without_columns(cursor, "integrity_audit",  
    ["file_id"])

    _rebuild_table_without_columns(cursor, "forensic_receipts", 
    ["file_id"])
    
    cursor.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    # ── ENCRYPT EXISTING PLAIN-TEXT KEYS / HASHES ─────────────────
    # Any aes_key / public_key / hash value saved before encryption
    # was added is still plain text — encrypt it now. Safe to run on
    # every startup: already-encrypted values are detected and skipped.
    _encrypt_existing_plaintext_columns(cursor)
    conn.commit()
    conn.close()
    print("[Migration] Database migration complete.")


def _encrypt_existing_plaintext_columns(cursor):
    """
    One-time-safe migration: walks every table/column that stores a
    key or a hash and encrypts any value that is still plain text.
    Already-encrypted values are left untouched (checked via is_encrypted()).
    """
    targets = [
        ("users",             "id", "public_key"),
        ("forensic_files",    "file_id", "original_hash"),
        ("manifest_details",  "id", "aes_key"),
        ("vault_transfers",   "id", "original_hash"),
        ("session_keys",      "id", "aes_key"),
        ("session_keys",      "id", "original_hash"),
        ("integrity_audit",   "id", "sender_hash"),
        ("integrity_audit",   "id", "receiver_hash"),
        ("forensic_receipts", "receipt_id", "hash_confirmed"),
    ]
    for table, id_col, col in targets:
        try:
            cursor.execute(f"SELECT {id_col}, {col} FROM {table}")
            rows = cursor.fetchall()
        except Exception:
            continue  # table/column doesn't exist yet — nothing to migrate
        migrated = 0
        for rid, val in rows:
            if val and not is_encrypted(val):
                try:
                    cursor.execute(
                        f"UPDATE {table} SET {col}=? WHERE {id_col}=?",
                        (encrypt_field(val), rid)
                    )
                    migrated += 1
                except Exception as e:
                    print(f"[Migration] Could not encrypt {table}.{col} (id={rid}): {e}")
        if migrated:
            print(f"[Migration] Encrypted {migrated} existing plain-text value(s) in {table}.{col}.")


# =======================================================
# SEED SUPERADMIN — runs at every startup, safe to re-run
# =======================================================
def seed_superadmin():
    """
    Creates the SuperAdmin account if it does not already exist.
    SuperAdmin is auto-approved and never revoked by this function.
    Credentials are defined at the top of this file (or load from .env).

    How to use .env instead:
        pip install python-dotenv
        from dotenv import load_dotenv; load_dotenv()
        SUPERADMIN_EMAIL    = os.getenv("SUPERADMIN_EMAIL")
        SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD")
    """
    conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE email = ?", (SUPERADMIN_EMAIL,))
    if cursor.fetchone():
        conn.close()
        print("[SuperAdmin] Already exists — skipping seed.")
        return

    # Generate RSA key pair for SuperAdmin.
    # Key is saved as keys/<SUPERADMIN_NAME>_private.pem
    # We use the plain name (spaces allowed) — key_exchange handles it fine.
    try:
        public_key, _ = generate_rsa_key_pair(SUPERADMIN_NAME)
    except Exception as e:
        print(f"[SuperAdmin] RSA keygen warning: {e}")
        public_key = ""

    cursor.execute(
        "INSERT INTO users (name, email, password, role, public_key, is_approved, is_revoked) "
        "VALUES (?, ?, ?, ?, ?, 1, 0)",
        (SUPERADMIN_NAME, SUPERADMIN_EMAIL, hash_password(SUPERADMIN_PASSWORD), SUPERADMIN_ROLE, encrypt_field(public_key))
    )
    conn.commit()
    conn.close()

    write_audit_log(
        username=SUPERADMIN_NAME, role=SUPERADMIN_ROLE,
        action="SUPERADMIN_SEEDED", method="System",
        details=f"Email: {SUPERADMIN_EMAIL}"
    )
    print(f"[SuperAdmin] Created: {SUPERADMIN_EMAIL}")


# =======================================================
# AUDIT LOG WRITER — used by all modules
# =======================================================
def write_audit_log(username, role, action, method="", file_name="", details=""):
    """
    Writes one entry to audit_logs in users.db.
    Called by sender, receiver, admin, and this module.
    Admin dashboard reads from this table for chain of custody.
    """
    try:
        conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO audit_logs (username, role, action, method, file_name, details) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (username, role, action, method, file_name, details)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Audit Log Error] {e}")


def push_notification(message, target_role, category="Info", target_user=None):
    """
    Writes a cross-dashboard notification to shared_notifications in users.db.

    target_role : "Sender" | "Receiver" | "Admin" | "SuperAdmin" | "All"
    target_user : specific username (None = all users of that role)
    category    : "Info" | "Success" | "Alert" | "Warning"
    """
    try:
        conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO shared_notifications "
            "(target_role, target_user, message, category, is_read) "
            "VALUES (?, ?, ?, ?, 0)",
            (target_role, target_user, message, category)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Push Notification Error] {e}")


def poll_notifications(role, username, last_id):
    """
    Returns new unread notifications for this role/user since last_id.
    Called every 5 seconds by each dashboard's QTimer.
    Marks fetched rows as read automatically.

    Returns list of (id, message, category) tuples.
    """
    try:
        conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, message, category
            FROM shared_notifications
            WHERE id > ?
              AND is_read = 0
              AND (
                  target_role = ?
               OR target_role = "All"
               OR (target_role = "Admin" AND ? IN ("Admin","SuperAdmin"))
              )
              AND (target_user IS NULL OR target_user = ?)
            ORDER BY id ASC
        ''', (last_id, role, role, username))
        rows = cursor.fetchall()
        if rows:
            ids = [r[0] for r in rows]
            cursor.execute(
                f"UPDATE shared_notifications SET is_read=1 "
                f"WHERE id IN ({','.join('?'*len(ids))})", ids
            )
            conn.commit()
        conn.close()
        return rows
    except Exception as e:
        print(f"[Poll Notification Error] {e}")
        return []

def _rebuild_table_without_columns(cursor, table, drop_cols):
    """
    Recreates a table without specified columns.
    Works on ALL SQLite versions including older ones.
    """
    # Get current columns
    cursor.execute(f"PRAGMA table_info({table})")
    all_cols = cursor.fetchall()
    
    # Filter out columns to drop
    keep_cols = [
        col for col in all_cols 
        if col[1] not in drop_cols
    ]
    
    if len(keep_cols) == len(all_cols):
        return  # nothing to drop
    
    col_names  = [col[1] for col in keep_cols]
    col_defs   = []
    for col in keep_cols:
        # col = (cid, name, type, notnull, dflt_value, pk)
        defn = f"{col[1]} {col[2]}"
        if col[5]:  defn += " PRIMARY KEY AUTOINCREMENT"
        if col[3]:  defn += " NOT NULL"
        if col[4] is not None: defn += f" DEFAULT {col[4]}"
        col_defs.append(defn)
    
    cols_str = ", ".join(col_defs)
    names_str = ", ".join(col_names)
    
    cursor.execute(f"ALTER TABLE {table} RENAME TO _{table}_old")
    cursor.execute(f"CREATE TABLE {table} ({cols_str})")
    cursor.execute(
        f"INSERT INTO {table} ({names_str}) "
        f"SELECT {names_str} FROM _{table}_old"
    )
    cursor.execute(f"DROP TABLE _{table}_old")
    print(f"[Migration] Rebuilt {table} — removed: {drop_cols}")

def write_anomaly_alert(event_type, description, severity="MEDIUM"):
    """
    Writes one entry to anomaly_alerts in users.db.

    Called automatically when suspicious events occur:
      - Failed login attempts
      - Unauthorized access (wrong receiver trying to decrypt)
      - Integrity check mismatch (file tampered)
      - Transfer blocked (revoked/unapproved receiver)

    event_type  : SHORT_CODE  e.g. "UNAUTHORIZED_ACCESS", "INTEGRITY_FAIL"
    description : human readable detail
    severity    : "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    """
    try:
        conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO anomaly_alerts (event_type, description, severity) "
            "VALUES (?, ?, ?)",
            (event_type, description, severity)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Anomaly Alert Error] {e}")


def write_system_log(event_source, event_type, details=""):
    """
    Writes one entry to system_monitor_logs in users.db.

    Called from every transfer method to record system-level events:
      USB inserted, HDD connected, LAN transfer started,
      Email vault accessed, Google Drive upload started etc.

    event_source : "USB" | "HDD" | "LAN" | "Email" | "GoogleDrive"
    event_type   : "CONNECTED" | "TRANSFER_START" | "TRANSFER_COMPLETE" | "DISCONNECTED"
    details      : any extra info (file name, IP address, size etc.)
    """
    try:
        conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO system_monitor_logs (event_source, event_type, details) "
            "VALUES (?, ?, ?)",
            (event_source, event_type, details)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[System Log Error] {e}")


if __name__ == "__main__":
    create_users_db()


# =======================================================
# VALIDATION HELPERS
# =======================================================
def is_valid_name(name):
    return bool(re.fullmatch(r"^[a-zA-Z\s]{3,}$", name.strip()))

def is_valid_email(email):
    return bool(re.fullmatch(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email))

def check_password_strength(password):
    score = 0
    is_long_enough = len(password) >= 8
    if is_long_enough:                                   score += 1
    if re.search(r"[a-zA-Z]",           password):       score += 1
    if re.search(r"\d",                  password):       score += 1
    if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password): score += 1
    if score == 4 and is_long_enough:
        return "Strong Password", "green", True
    return "Weak password (letters, digits, symbols)", "red", False


# =======================================================
# STYLING
# =======================================================
BLUE_PRIMARY   = "#0284c7"
BLUE_DARK      = "#0369a1"
BLUE_LIGHT_BG  = "#eff6ff"
NAV_BAR_COLOR  = "#0284c7"

INPUT_STYLE = """
    QLineEdit, QComboBox {
        background-color: #f3f4f6;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        font-size: 16px;
        padding: 10px;
        min-height: 45px;
        max-height: 45px;
        color: #1f2937;
    }
    QLineEdit:focus, QComboBox:focus {
        border: 2px solid #60a5fa;
        background-color: white;
    }
    QComboBox::drop-down { subcontrol-origin:padding; subcontrol-position:top right;
                           width:35px; border:none; }
    QComboBox::down-arrow { image:none; border-left:6px solid transparent;
                            border-right:6px solid transparent;
                            border-top:8px solid #000000;
                            position:relative; right:10px; top:0px; }
    QComboBox::down-arrow:hover { border-top:8px solid #3b82f6; }
    QComboBox QAbstractItemView { border:1px solid #d1d5db;
        selection-background-color:#3b82f6; selection-color:white;
        background-color:white; outline:none; padding:5px; }
"""

BUTTON_PRIMARY_STYLE = f"""
    QPushButton {{
        background-color: {BLUE_PRIMARY};
        color: white;
        font-size: 20px;
        padding: 15px;
        border-radius: 12px;
        margin-top: 20px;
        min-height: 50px;
    }}
    QPushButton:hover {{ background-color: {BLUE_DARK}; }}
"""

LINK_STYLE        = "font-size: 16px; color: black; text-decoration: none;"
ERROR_LABEL_STYLE = "color: #ef4444; font-size: 16px; font-weight: bold; min-height: 25px;"


class CustomPopup(QtWidgets.QDialog):
    def __init__(self, message, title="Notification"):
        super().__init__(None, QtCore.Qt.Window)
        self.setWindowTitle(title)
        self.setFixedSize(340, 160)
        self.setStyleSheet(f"background-color:{BLUE_LIGHT_BG}; border:2px solid {BLUE_PRIMARY}; border-radius:10px;")
        layout = QtWidgets.QVBoxLayout(self)
        label  = QtWidgets.QLabel(message)
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{BLUE_PRIMARY}; font-size:14px; font-weight:bold;")
        layout.addWidget(label)
        btn = QtWidgets.QPushButton("OK")
        btn.setFixedSize(100, 30)
        btn.setStyleSheet(BUTTON_PRIMARY_STYLE
            .replace("font-size: 20px", "font-size: 14px")
            .replace("min-height: 50px", "min-height: 30px")
            .replace("margin-top: 20px", "margin-top: 5px"))
        layout.addWidget(btn, alignment=QtCore.Qt.AlignCenter)
        btn.clicked.connect(self.accept)
        qr = self.frameGeometry()
        cp = QtWidgets.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

def show_popup(msg):
    CustomPopup(msg).exec_()

def create_field_layout(label_text, widget):
    h = QtWidgets.QHBoxLayout()
    lbl = QtWidgets.QLabel(label_text)
    lbl.setStyleSheet("color:black; font-size:16px; min-width:100px;")
    h.addWidget(lbl); h.addWidget(widget)
    return h


# =======================================================
# PENDING APPROVAL DIALOG
# =======================================================
class PendingApprovalDialog(QtWidgets.QDialog):
    """
    Shown when a user logs in but is_approved=0 or is_revoked=1.
    Gives them a clear, friendly explanation.
    """
    def __init__(self, message, parent=None):
        super().__init__(parent, QtCore.Qt.Window)
        self.setWindowTitle("Account Status")
        self.setFixedSize(460, 280)
        self.setStyleSheet(f"""
            background: white;
            border: 2px solid {BLUE_PRIMARY};
            border-radius: 14px;
        """)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(30, 30, 30, 20)
        lay.setSpacing(15)

        icon_lbl = QtWidgets.QLabel("🔒")
        icon_lbl.setAlignment(QtCore.Qt.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 36px; border: none; background: transparent;")

        msg_lbl = QtWidgets.QLabel(message)
        msg_lbl.setAlignment(QtCore.Qt.AlignCenter)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(f"color: #1e293b; font-size: 14px; border: none;")

        ok_btn = QtWidgets.QPushButton("OK")
        ok_btn.setFixedSize(120, 40)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background: {BLUE_PRIMARY}; color: white;
                border-radius: 8px; font-size: 15px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {BLUE_DARK}; }}
        """)
        ok_btn.clicked.connect(self.accept)

        lay.addWidget(icon_lbl)
        lay.addWidget(msg_lbl)
        lay.addWidget(ok_btn, alignment=QtCore.Qt.AlignCenter)

        qr = self.frameGeometry()
        cp = QtWidgets.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp); self.move(qr.topLeft())


# =======================================================
# WELCOME PAGE
# =======================================================
class WelcomePage(QtWidgets.QWidget):
    switch_page   = QtCore.pyqtSignal(int)
    theme_changed = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_dark_mode = False

        self.main_container = QtWidgets.QVBoxLayout(self)
        self.main_container.setSpacing(0)
        self.main_container.setContentsMargins(0, 0, 0, 0)

        self.navBar = QtWidgets.QFrame()
        self.navBar.setMinimumHeight(70)
        self.navBar.setStyleSheet(f"background-color:{NAV_BAR_COLOR};")
        self.navLayout = QtWidgets.QHBoxLayout(self.navBar)
        self.navLayout.setContentsMargins(25, 0, 25, 0)

        self.titleLabel = QtWidgets.QLabel("SDTF")
        self.titleLabel.setStyleSheet("color:white; font-weight:bold; font-size:28px; margin-right:20px;")
        self.navLayout.addWidget(self.titleLabel)

        self.btn_home = self.create_nav_btn("Home")
        self.btn_sec  = self.create_nav_btn("Security Architecture")
        self.btn_for  = self.create_nav_btn("Forensic Audit")
        self.btn_how  = self.create_nav_btn("How It Works")
        self.btn_sup  = self.create_nav_btn("Support & Report")

        for btn in [self.btn_home, self.btn_sec, self.btn_for, self.btn_how, self.btn_sup]:
            self.navLayout.addWidget(btn)
        self.navLayout.addStretch()

        self.themeToggle = QtWidgets.QPushButton("🌙")
        self.themeToggle.setFixedSize(45, 42)
        self.themeToggle.setCursor(QtCore.Qt.PointingHandCursor)
        self.themeToggle.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,0.1);border-radius:6px;font-size:18px;color:white;}")
        self.themeToggle.clicked.connect(self.toggle_theme)
        self.navLayout.addWidget(self.themeToggle)

        self.signinButton = QtWidgets.QPushButton("Sign in")
        self.signupButton = QtWidgets.QPushButton("Sign up")
        self.signinButton.setFixedSize(110, 42)
        self.signupButton.setFixedSize(110, 42)
        self.signinButton.setStyleSheet(
            "background:white; color:#0284c7; border:2px solid white; border-radius:6px; font-weight:bold; font-size:18px;")
        self.signupButton.setStyleSheet(
            "background:white; color:#0284c7; border-radius:6px; font-weight:bold; font-size:18px;")
        self.navLayout.addWidget(self.signinButton)
        self.navLayout.addWidget(self.signupButton)
        self.main_container.addWidget(self.navBar)

        self.content_stack = QtWidgets.QStackedWidget()
        self.home_page = self.create_home_page()
        self.content_stack.addWidget(self.home_page)

        self.details_page = QtWidgets.QWidget()
        self.details_layout = QtWidgets.QHBoxLayout(self.details_page)
        self.details_layout.setContentsMargins(80, 40, 80, 40)
        self.details_layout.setSpacing(50)
        self.content_stack.addWidget(self.details_page)

        self.main_container.addWidget(self.content_stack)
        self.apply_theme_styles()

        self.btn_home.clicked.connect(lambda: self.content_stack.setCurrentIndex(0))
        self.btn_sec.clicked.connect(lambda: self.update_details_page("Security Architecture",
            "<h3>Core Framework Security</h3>"
            "<b>• End-to-End Encryption:</b> AES-256 encryption at source.<br><br>"
            "<b>• Cryptographic Algorithms:</b> Military-grade AES-256 and RSA-2048.<br><br>"
            "<b>• Data Integrity:</b> SHA-256 hash validation per packet.<br><br>"
            "<b>• Secure Key Exchange:</b> RSA-encrypted key transport.<br><br>"
            "<b>• Zero Knowledge:</b> Even the service provider cannot access raw data.",
            "images/security.jpg"))
        self.btn_for.clicked.connect(lambda: self.update_details_page("Forensic Audit",
            "<h3>Digital Forensic & Accountability</h3>"
            "<b>• Immutable Logs:</b> Every action recorded in tamper-proof audit trail.<br><br>"
            "<b>• Granular Tracking:</b> User IDs, MAC addresses, timestamps captured.<br><br>"
            "<b>• Forensic Reports:</b> Auto-generated comprehensive reports.<br><br>"
            "<b>• Non-Repudiation:</b> Users cannot deny logged actions.<br><br>"
            "<b>• Integrity Monitoring:</b> Constant background file surveillance.",
            "images/forensic.jpg"))
        self.btn_how.clicked.connect(lambda: self.update_details_page("How It Works",
            "<h3>Operational Workflow</h3>"
            "<b>Step 1:</b> Authenticate through multi-factor portal.<br><br>"
            "<b>Step 2:</b> Local AES-256 encryption and SHA-256 hashing.<br><br>"
            "<b>Step 3:</b> Choose Online P2P or Offline Mode.<br><br>"
            "<b>Step 4:</b> Key delivered only to authorized receiver via RSA.<br><br>"
            "<b>Step 5:</b> Receiver validates hash before decryption.",
            "images/process.jpg"))
        self.btn_sup.clicked.connect(lambda: self.update_details_page("Support & Report",
            "<h3>AI Threat Detection & Support</h3>"
            "<b>• AI Anomaly Detection:</b> Monitors for suspicious activities.<br><br>"
            "<b>• Real-time Alerts:</b> Instant notifications on breach detection.<br><br>"
            "<b>• Admin Control Panel:</b> Dedicated suite for administrators.<br><br>"
            "<b>• Incident Reporting:</b> Module to report bugs securely.<br><br>"
            "<b>• 24/7 Support:</b> Integrated support ticketing system.",
            "images/support.jpg"))
        self.signupButton.clicked.connect(lambda: self.switch_page.emit(2))
        self.signinButton.clicked.connect(lambda: self.switch_page.emit(1))

    def update_details_page(self, title, info, image_path):
        while self.details_layout.count():
            item = self.details_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.details_layout.setContentsMargins(50, 30, 50, 30)
        self.details_layout.setSpacing(40)
        text_color  = "white" if self.is_dark_mode else BLUE_PRIMARY
        card_bg     = "#1e293b" if self.is_dark_mode else "white"
        sub_text    = "#94a3b8" if self.is_dark_mode else "#334155"
        left_container = QtWidgets.QWidget()
        left_v = QtWidgets.QVBoxLayout(left_container); left_v.setContentsMargins(0,0,0,0)
        h_label = QtWidgets.QLabel(title)
        h_label.setStyleSheet(f"font-size:36px; font-weight:bold; color:{text_color}; margin-bottom:5px;")
        info_card = QtWidgets.QLabel(info)
        info_card.setTextFormat(QtCore.Qt.RichText); info_card.setWordWrap(True)
        info_card.setStyleSheet(f"font-size:17px; color:{sub_text}; background:{card_bg}; padding:25px; border-radius:20px; border:2px solid #cbd5e1; line-height:140%;")
        left_v.addWidget(h_label); left_v.addWidget(info_card); left_v.addStretch()
        right_img = QtWidgets.QLabel()
        pix = QtGui.QPixmap(image_path)
        if not pix.isNull():
            right_img.setPixmap(pix.scaled(500, 550, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        else:
            right_img.setText("📷 Picture Space")
            right_img.setStyleSheet(f"background:{card_bg}; border-radius:20px; border:2px dashed #cbd5e1;")
            right_img.setFixedSize(400, 500)
        right_img.setAlignment(QtCore.Qt.AlignCenter)
        self.details_layout.addWidget(left_container, 55)
        self.details_layout.addWidget(right_img, 45)
        self.content_stack.setCurrentIndex(1)

    def create_nav_btn(self, text):
        btn = QtWidgets.QPushButton(text); btn.setFixedHeight(45)
        btn.setStyleSheet("QPushButton{background:transparent;color:white;border:none;font-size:15px;font-weight:bold;padding:0 10px;} QPushButton:hover{color:#bae6fd;}")
        return btn

    def apply_theme_styles(self):
        bg     = "#121212" if self.is_dark_mode else BLUE_LIGHT_BG
        nav_bg = "#0f172a" if self.is_dark_mode else NAV_BAR_COLOR
        self.setStyleSheet(f"background-color:{bg};")
        self.navBar.setStyleSheet(f"background-color:{nav_bg};")

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.theme_changed.emit(self.is_dark_mode)
        self.themeToggle.setText("☀️" if self.is_dark_mode else "🌙")
        self.apply_theme_styles()
        idx = self.content_stack.currentIndex()
        self.content_stack.removeWidget(self.home_page)
        self.home_page = self.create_home_page()
        self.content_stack.insertWidget(0, self.home_page)
        self.content_stack.setCurrentIndex(idx)

    def create_home_page(self):
        page   = QtWidgets.QWidget(); main_v = QtWidgets.QVBoxLayout(page)
        main_v.setContentsMargins(0, 0, 0, 0)
        scroll = QtWidgets.QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none; background:transparent;")
        content_widget = QtWidgets.QWidget(); content_widget.setStyleSheet("background:transparent;")
        scroll.setWidget(content_widget)
        scroll_layout = QtWidgets.QVBoxLayout(content_widget)
        text_color = "white" if self.is_dark_mode else "#1e293b"
        sub_text   = "#94a3b8" if self.is_dark_mode else "#4b5563"
        card_bg    = "#1e293b" if self.is_dark_mode else "white"
        card_text  = "white"  if self.is_dark_mode else "#1e293b"
        hero   = QtWidgets.QFrame(); h_lay = QtWidgets.QHBoxLayout(hero)
        h_lay.setContentsMargins(80, 60, 80, 60)
        t_box  = QtWidgets.QVBoxLayout()
        title  = QtWidgets.QLabel("Secure Data Sharing\nFramework")
        title.setStyleSheet("font-size:50px; font-weight:bold; color:#0284c7; line-height:110%;")
        fyp_text = ("A reliable and robust offline and online platform<br>"
                    "designed specifically to facilitate secure data exchange<br>"
                    "using high level military grade AES-256 encryption standards<br>"
                    "ensuring sensitive information remains fully protected<br>"
                    "integrated with automated forensic logs and AI-checks.")
        desc = QtWidgets.QLabel(fyp_text); desc.setTextFormat(QtCore.Qt.RichText)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size:18px; color:{sub_text}; line-height:170%; margin-top:15px;")
        t_box.addWidget(title); t_box.addWidget(desc); t_box.addStretch()
        img = QtWidgets.QLabel()
        pix = QtGui.QPixmap(os.path.join(BASE_DIR, "images", "landing.jpg"))
        if not pix.isNull():
            img.setPixmap(pix.scaled(500, 400, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        else:
            img.setText("📷"); img.setStyleSheet("font-size:100px;")
        h_lay.addLayout(t_box, 60); h_lay.addWidget(img, 40)
        scroll_layout.addWidget(hero)
        grid_widget = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(grid_widget)
        grid.setContentsMargins(80, 20, 80, 40); grid.setSpacing(30)
        features = [
            ("End-to-End Encryption","🔒","Military-grade AES-256 encryption at the source."),
            ("Tamper-Proof Logs","📝","Immutable forensic audit trails of every interaction."),
            ("Uninterrupted Transfer","🚀","High-performance multi-threaded data exchange."),
            ("No Central Server","🌐","Decentralized Peer-to-Peer architecture."),
            ("AI Threat Alerts","🤖","AI algorithms monitoring system behavior in real-time."),
            ("File Integrity Check","✔️","SHA-256 hashing to verify file consistency."),
        ]
        for i, (f_t, icon, f_d) in enumerate(features):
            card = QtWidgets.QFrame(); card.setFixedSize(350, 150)
            card.setStyleSheet(f"background:{card_bg}; border-radius:15px; border:1px solid #cbd5e1;")
            v = QtWidgets.QVBoxLayout(card); v.setContentsMargins(20,20,20,20)
            h_t = QtWidgets.QHBoxLayout()
            il = QtWidgets.QLabel(icon); il.setStyleSheet("font-size:40px; border:none;")
            tl = QtWidgets.QLabel(f"<b>{f_t}</b>")
            tl.setStyleSheet(f"font-size:16px; color:{card_text}; border:none;")
            h_t.addWidget(il); h_t.addWidget(tl); h_t.addStretch()
            dl = QtWidgets.QLabel(f_d); dl.setWordWrap(True)
            dl.setStyleSheet(f"font-size:16px; color:{sub_text}; border:none; line-height:140%;")
            v.addLayout(h_t); v.addSpacing(10); v.addWidget(dl); v.addStretch()
            grid.addWidget(card, i // 3, i % 3)
        scroll_layout.addWidget(grid_widget)
        main_v.addWidget(scroll)
        return page


# =======================================================
# OTP VERIFICATION DIALOG
# =======================================================
class OTPVerificationDialog(QtWidgets.QDialog):
    """
    Shown after OTP email is sent during signup.
    User has 3 attempts to enter the correct OTP.
    """
    def __init__(self, email, otp, parent=None):
        super().__init__(parent, QtCore.Qt.Window)
        self.otp        = otp
        self.email      = email
        self.attempts   = 0
        self.max_attempts = 3

        self.setWindowTitle("Email Verification")
        self.setFixedSize(460, 340)
        self.setStyleSheet("background:white; border-radius:12px;")

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(40, 28, 40, 28)
        lay.setSpacing(12)

        icon_lbl = QtWidgets.QLabel("📧")
        icon_lbl.setAlignment(QtCore.Qt.AlignCenter)
        icon_lbl.setStyleSheet("font-size:36px; border:none;")

        title_lbl = QtWidgets.QLabel("Verify Your Email")
        title_lbl.setAlignment(QtCore.Qt.AlignCenter)
        title_lbl.setStyleSheet(
            f"font-size:20px; font-weight:bold; color:{BLUE_PRIMARY}; border:none;"
        )

        info_lbl = QtWidgets.QLabel(
            f"A 6-digit OTP has been sent to:\n{email}"
        )
        info_lbl.setAlignment(QtCore.Qt.AlignCenter)
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("font-size:13px; color:#475569; border:none;")

        self.otp_input = QtWidgets.QLineEdit()
        self.otp_input.setPlaceholderText("Enter 6-digit OTP")
        self.otp_input.setMaxLength(6)
        self.otp_input.setAlignment(QtCore.Qt.AlignCenter)
        self.otp_input.setFixedHeight(52)
        self.otp_input.setStyleSheet(
            "font-size:26px; font-weight:bold; letter-spacing:12px; "
            "padding:8px 16px; border:2px solid #cbd5e1; border-radius:8px; "
            "background:#f8fafc; color:#0f172a;"
        )

        self.error_lbl = QtWidgets.QLabel("")
        self.error_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.error_lbl.setStyleSheet("color:#ef4444; font-size:13px; font-weight:bold; border:none;")

        verify_btn = QtWidgets.QPushButton("Verify OTP")
        verify_btn.setFixedHeight(46)
        verify_btn.setStyleSheet(f"""
            QPushButton {{
                background:{BLUE_PRIMARY}; color:white; font-size:15px;
                font-weight:bold; border-radius:8px;
            }}
            QPushButton:hover {{ background:{BLUE_DARK}; }}
        """)
        verify_btn.clicked.connect(self.verify_otp)
        self.otp_input.returnPressed.connect(self.verify_otp)

        lay.addWidget(icon_lbl)
        lay.addWidget(title_lbl)
        lay.addWidget(info_lbl)
        lay.addWidget(self.otp_input)
        lay.addWidget(self.error_lbl)
        lay.addWidget(verify_btn)

        # Center on screen
        qr = self.frameGeometry()
        cp = QtWidgets.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp); self.move(qr.topLeft())

    def verify_otp(self):
        entered = self.otp_input.text().strip()
        self.attempts += 1

        if entered == self.otp:
            self.accept()
        else:
            remaining = self.max_attempts - self.attempts
            if remaining > 0:
                self.error_lbl.setText(
                    f"Incorrect OTP. {remaining} attempt(s) remaining."
                )
                self.otp_input.clear()
                self.otp_input.setStyleSheet(
                    "font-size:26px; font-weight:bold; letter-spacing:12px; "
                    "padding:8px 16px; border:2px solid #ef4444; border-radius:8px; "
                    "background:#fef2f2; color:#0f172a;"
                )
            else:
                self.error_lbl.setText("Too many failed attempts.")
                QtWidgets.QMessageBox.critical(
                    self, "Verification Failed",
                    "You have exceeded the maximum number of OTP attempts.\n\n"
                    "Please restart the registration process."
                )
                self.reject()


# =======================================================
# SIGNUP PAGE
# =======================================================
class SignupPage(QtWidgets.QWidget):
    switch_page = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        main = QtWidgets.QHBoxLayout(self); main.addStretch()
        whiteCard = QtWidgets.QFrame()
        whiteCard.setFixedSize(950, 670)
        whiteCard.setStyleSheet("background-color:white; border-radius:20px;")
        shadow = QtWidgets.QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40); shadow.setXOffset(0); shadow.setYOffset(0)
        shadow.setColor(QtGui.QColor(0,0,0,80)); whiteCard.setGraphicsEffect(shadow)
        cardHLayout = QtWidgets.QHBoxLayout(whiteCard)
        cardHLayout.setContentsMargins(20,20,20,20); cardHLayout.setSpacing(0)

        blueSide = QtWidgets.QFrame(); blueSide.setFixedWidth(350)
        blueSide.setStyleSheet(f"background-color:{BLUE_PRIMARY}; border-radius:15px;")
        blueVLayout = QtWidgets.QVBoxLayout(blueSide)
        blueVLayout.setContentsMargins(25, 50, 25, 50)

        welcomeLabel = QtWidgets.QLabel("WELCOME")
        welcomeLabel.setStyleSheet("color:white; font-size:40px; font-weight:bold;")
        welcomeLabel.setAlignment(QtCore.Qt.AlignCenter)
        headlineLabel = QtWidgets.QLabel("CREATE YOUR ACCOUNT")
        headlineLabel.setStyleSheet("color:white; font-size:24px;")
        headlineLabel.setAlignment(QtCore.Qt.AlignCenter)

        # ── NOTE displayed on blue panel ───────────────────────
        noteLabel = QtWidgets.QLabel(
            "ℹ️ All new accounts require SuperAdmin approval before login.\n\n"
            "Admins are also subject to approval."
        )
        noteLabel.setStyleSheet("color:#bfdbfe; font-size:13px; line-height:150%;")
        noteLabel.setWordWrap(True); noteLabel.setAlignment(QtCore.Qt.AlignCenter)

        blueVLayout.addWidget(welcomeLabel); blueVLayout.addSpacing(15)
        blueVLayout.addWidget(headlineLabel); blueVLayout.addSpacing(20)
        blueVLayout.addWidget(noteLabel); blueVLayout.addStretch()
        cardHLayout.addWidget(blueSide)

        formSide = QtWidgets.QFrame()
        formVLayout = QtWidgets.QVBoxLayout(formSide)
        formVLayout.setSpacing(15); formVLayout.setAlignment(QtCore.Qt.AlignCenter)

        formTitle = QtWidgets.QLabel("Sign up")
        formTitle.setStyleSheet("color:black; font-size:45px; font-weight:bold; margin-bottom:10px;")
        formTitle.setAlignment(QtCore.Qt.AlignCenter)
        formVLayout.addWidget(formTitle)

        self.name = QtWidgets.QLineEdit()
        self.name.setPlaceholderText("Name")
        self.name.setStyleSheet(INPUT_STYLE)
        self.name.textChanged.connect(self.validate_live)

        self.email = QtWidgets.QLineEdit()
        self.email.setPlaceholderText("Email (e.g., example123@domain.com)")
        self.email.setStyleSheet(INPUT_STYLE)
        self.email.textChanged.connect(self.validate_live)

        self.password = QtWidgets.QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.password.setStyleSheet(INPUT_STYLE)
        self.password.textChanged.connect(self.validate_live)

        self.password_strength_label = QtWidgets.QLabel("")
        self.password_strength_label.setAlignment(QtCore.Qt.AlignLeft)
        self.password_strength_label.setFixedHeight(20)

        # ── Role dropdown — ALL roles allowed at signup ──────────
        # Admin is included; SuperAdmin approves all before login.
        self.role = QtWidgets.QComboBox()
        self.role.setStyleSheet(INPUT_STYLE)
        self.role.addItem("Select Your Role")
        self.role.addItems(["Sender", "Receiver"])
        self.role.setItemData(0, 0, QtCore.Qt.UserRole - 1)
        self.role.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.role.currentIndexChanged.connect(self.validate_live)

        formVLayout.addLayout(create_field_layout("Name:",     self.name))
        formVLayout.addLayout(create_field_layout("Email:",    self.email))
        formVLayout.addLayout(create_field_layout("Password:", self.password))

        self.password_strength_label.setStyleSheet(
            "font-size:15px; font-weight:bold; padding-left:110px; margin-top:-5px;")
        formVLayout.addWidget(self.password_strength_label, alignment=QtCore.Qt.AlignLeft)
        formVLayout.addSpacing(-5)
        formVLayout.addLayout(create_field_layout("Role:", self.role))
        formVLayout.addSpacing(10)

        self.errorLabel = QtWidgets.QLabel("")
        self.errorLabel.setStyleSheet(ERROR_LABEL_STYLE)
        self.errorLabel.setAlignment(QtCore.Qt.AlignCenter)
        formVLayout.addWidget(self.errorLabel)
        formVLayout.addSpacing(-10)

        self.create_btn = QtWidgets.QPushButton("Create Account")
        self.create_btn.setStyleSheet(BUTTON_PRIMARY_STYLE)
        formVLayout.addWidget(self.create_btn)
        formVLayout.addSpacing(25)

        loginLink = QtWidgets.QLabel("Already have an account? <a href=\"#\">Sign in</a>")
        loginLink.linkActivated.connect(lambda: self.switch_page.emit(1))
        loginLink.setAlignment(QtCore.Qt.AlignCenter)
        loginLink.setStyleSheet(LINK_STYLE)
        formVLayout.addWidget(loginLink)
        formVLayout.addStretch()
        cardHLayout.addWidget(formSide)
        main.addWidget(whiteCard); main.addStretch()

        self.create_btn.clicked.connect(self.create_account)

    def validate_live(self):
        self.errorLabel.setText("")
        self.create_btn.setEnabled(True)
        name     = self.name.text().strip()
        email    = self.email.text().strip()
        password = self.password.text()
        role     = self.role.currentText()

        is_name_valid  = is_valid_name(name)
        is_email_valid = is_valid_email(email)
        is_password_strong = False

        if name and not is_name_valid:
            self.errorLabel.setText("Invalid Name: letters and spaces only (min 3 chars).")
            self.create_btn.setEnabled(False); return
        if email and not is_valid_email(email):
            self.errorLabel.setText("Invalid Email Format.")
            self.create_btn.setEnabled(False); return
        if password:
            strength_text, color, is_password_strong = check_password_strength(password)
            self.password_strength_label.setText(strength_text)
            self.password_strength_label.setStyleSheet(
                f"color:{color}; font-size:15px; font-weight:bold; padding-left:110px; margin-top:-5px;")
            if not is_password_strong:
                self.create_btn.setEnabled(False); return
        else:
            self.password_strength_label.setText("")

        all_key_valid = is_name_valid and is_email_valid and is_password_strong
        if all_key_valid and role == "Select Your Role":
            self.errorLabel.setText("Please select a Role.")
            self.create_btn.setEnabled(False); return

        if is_name_valid and is_valid_email(email) and is_password_strong and role != "Select Your Role":
            self.create_btn.setEnabled(True)
        elif name or email or password or role != "Select Your Role":
            self.create_btn.setEnabled(False)

    def create_account(self):
        name     = self.name.text().strip()
        email    = self.email.text().strip()
        password = self.password.text()
        role     = self.role.currentText()

        self.validate_live()
        if not name or not email or not password or role == "Select Your Role":
            self.errorLabel.setText("Please fill all required fields correctly."); return
        if not self.create_btn.isEnabled():
            return

        # ── STEP 1: Check email not already registered ────────────
        conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
        c    = conn.cursor()
        c.execute("SELECT id FROM users WHERE email=?", (email,))
        if c.fetchone():
            conn.close()
            self.errorLabel.setText("Error: Email already registered!"); return
        conn.close()

        # ── STEP 2: Generate and send OTP ─────────────────────────
        otp = generate_otp()
        self.errorLabel.setText("Sending OTP to your email...")
        QtWidgets.QApplication.processEvents()

        sent = send_otp_email(email, otp, name)
        if not sent:
            reply = QtWidgets.QMessageBox.question(
                self, "OTP Email Failed",
                "Could not send OTP email.\n\n"
                "Possible reasons:\n"
                "  • No internet connection\n"
                "  • OTP_SENDER_PASSWORD not configured in .env\n\n"
                "Do you want to continue registration WITHOUT email verification?\n"
                "(Account will still require SuperAdmin approval before login.)",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                self.errorLabel.setText("Registration cancelled."); return
            otp = None   # skip OTP check below

        # ── STEP 3: OTP verification dialog ───────────────────────
        if otp:
            otp_dialog = OTPVerificationDialog(email, otp, self)
            if otp_dialog.exec_() != QtWidgets.QDialog.Accepted:
                self.errorLabel.setText("OTP verification failed or cancelled."); return

        # ── STEP 4: Generate RSA key pair ─────────────────────────
        try:
            public_key, _ = generate_rsa_key_pair(name)
        except Exception as e:
            self.errorLabel.setText(f"Key generation failed: {e}"); return

        # ── STEP 5: Hash password with bcrypt ─────────────────────
        hashed_password = hash_password(password)

        # ── STEP 6: Save to DB ────────────────────────────────────
        conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
        c    = conn.cursor()
        try:
            c.execute(
                  "INSERT INTO users (name, email, password, role, public_key, is_approved, is_revoked, created_at) "
                  "VALUES (?, ?, ?, ?, ?, 0, 0, ?)",
                   (name, email, hashed_password, role, encrypt_field(public_key),
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit(); conn.close()

            write_audit_log(
                username=name, role=role,
                action="ACCOUNT_CREATED", method="Registration",
                details=f"Email: {email} | OTP verified: {otp is not None} | Awaiting SuperAdmin approval"
            )

            show_popup(
                "Account Created Successfully!\n\n"
                "Email verified via OTP.\n\n"
                "Your account is pending SuperAdmin approval.\n"
                "You can log in once approved."
            )
            self.switch_page.emit(1)

        except sqlite3.IntegrityError:
            conn.close()
            self.errorLabel.setText("Error: Email already registered!")

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        pixmap  = QtGui.QPixmap(os.path.join(BASE_DIR, "signup.jpg"))
        if not pixmap.isNull():
            painter.drawPixmap(self.rect(), pixmap)


# =======================================================
# SIGNIN PAGE
# =======================================================
class SigninPage(QtWidgets.QWidget):
    switch_page = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        main = QtWidgets.QHBoxLayout(self); main.addStretch()
        whiteCard = QtWidgets.QFrame()
        whiteCard.setFixedSize(950, 650)
        whiteCard.setStyleSheet("background-color:white; border-radius:20px;")
        shadow = QtWidgets.QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40); shadow.setXOffset(0); shadow.setYOffset(0)
        shadow.setColor(QtGui.QColor(0,0,0,80)); whiteCard.setGraphicsEffect(shadow)
        cardHLayout = QtWidgets.QHBoxLayout(whiteCard)
        cardHLayout.setContentsMargins(20,20,20,20); cardHLayout.setSpacing(0)

        blueSide = QtWidgets.QFrame(); blueSide.setFixedWidth(350)
        blueSide.setStyleSheet(f"background-color:{BLUE_PRIMARY}; border-radius:15px;")
        blueVLayout = QtWidgets.QVBoxLayout(blueSide)
        blueVLayout.setContentsMargins(25, 50, 25, 50)
        welcomeLabel = QtWidgets.QLabel("DATA SECURITY")
        welcomeLabel.setStyleSheet("color:white; font-size:36px; font-weight:bold; background:transparent;")
        welcomeLabel.setAlignment(QtCore.Qt.AlignCenter)
        headlineLabel = QtWidgets.QLabel("ACCESS YOUR ACCOUNT")
        headlineLabel.setStyleSheet("color:white; font-size:24px; background:transparent;")
        headlineLabel.setAlignment(QtCore.Qt.AlignCenter)
        blueVLayout.addWidget(welcomeLabel); blueVLayout.addSpacing(15)
        blueVLayout.addWidget(headlineLabel); blueVLayout.addStretch()
        cardHLayout.addWidget(blueSide)

        formSide    = QtWidgets.QFrame()
        formVLayout = QtWidgets.QVBoxLayout(formSide)
        formVLayout.setSpacing(15); formVLayout.setAlignment(QtCore.Qt.AlignCenter)

        formTitle = QtWidgets.QLabel("Sign in")
        formTitle.setStyleSheet("color:black; font-size:45px; font-weight:bold; margin-bottom:20px; background:transparent;")
        formTitle.setAlignment(QtCore.Qt.AlignCenter)
        formVLayout.addWidget(formTitle)

        self.email = QtWidgets.QLineEdit()
        self.email.setPlaceholderText("Email"); self.email.setStyleSheet(INPUT_STYLE)
        self.email.textChanged.connect(self.validate_live)

        self.password = QtWidgets.QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.password.setStyleSheet(INPUT_STYLE + "padding-right:40px;")
        self.toggle_action = self.password.addAction(
        QtGui.QIcon(os.path.join(BASE_DIR, "eye_icon.png")), QtWidgets.QLineEdit.TrailingPosition)
        self.toggle_action.setCheckable(True)
        self.toggle_action.triggered.connect(self.toggle_password_visibility)

        formVLayout.addSpacing(30)
        formVLayout.addLayout(create_field_layout("Email:",    self.email))
        formVLayout.addSpacing(10)
        formVLayout.addLayout(create_field_layout("Password:", self.password))
        formVLayout.addSpacing(10)

        self.errorLabel = QtWidgets.QLabel("")
        self.errorLabel.setStyleSheet(ERROR_LABEL_STYLE)
        self.errorLabel.setAlignment(QtCore.Qt.AlignCenter)
        formVLayout.addWidget(self.errorLabel)

        self.login_btn = QtWidgets.QPushButton("Sign In")
        self.login_btn.setStyleSheet(BUTTON_PRIMARY_STYLE)
        formVLayout.addWidget(self.login_btn)
        formVLayout.addSpacing(20)

        signupLink = QtWidgets.QLabel("Don't have an account? <a href=\"#\">Sign up</a>")
        signupLink.linkActivated.connect(lambda: self.switch_page.emit(2))
        signupLink.setAlignment(QtCore.Qt.AlignCenter)
        signupLink.setStyleSheet(LINK_STYLE)
        formVLayout.addWidget(signupLink)
        formVLayout.addStretch()
        cardHLayout.addWidget(formSide)
        main.addWidget(whiteCard); main.addStretch()

        self.login_btn.clicked.connect(self.verify_login)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        pixmap  = QtGui.QPixmap(os.path.join(BASE_DIR, "signin.jpg"))
        if not pixmap.isNull():
            painter.drawPixmap(self.rect(), pixmap)

    def validate_live(self):
        self.errorLabel.setText("")
        self.login_btn.setEnabled(True)
        email = self.email.text().strip()
        if email and not is_valid_email(email):
            self.errorLabel.setText("Invalid Email Format.")
            self.login_btn.setEnabled(False)

    def verify_login(self):
        email    = self.email.text().strip()
        password = self.password.text()

        if not email or not password:
            self.errorLabel.setText("Please enter both Email and Password."); return

        conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
        c    = conn.cursor()
        # Fetch by email only — bcrypt comparison done in Python, not SQL
        c.execute(
            "SELECT role, name, password, is_approved, is_revoked FROM users WHERE email=?",
            (email,)
        )
        user = c.fetchone(); conn.close()

        if not user or not verify_password(password, user[2]):
            self.errorLabel.setText("Invalid email or password!")
            # anomaly_alerts — failed login attempt
            write_anomaly_alert(
                "FAILED_LOGIN",
                f"Failed login attempt for email: {email}",
                "MEDIUM"
            )
            return

        role, name, _, is_approved, is_revoked = user

        # ── REVOKED CHECK ─────────────────────────────────────────
        if is_revoked:
            PendingApprovalDialog(
                "Your account has been revoked by the SuperAdmin.\n\n"
                "Please contact the system administrator for assistance."
            ).exec_()
            write_audit_log(username=name, role=role,
                            action="LOGIN_DENIED_REVOKED", method="Password",
                            details=f"Email: {email}")
            # anomaly_alerts — revoked account tried to login
            write_anomaly_alert(
                "REVOKED_LOGIN_ATTEMPT",
                f"Revoked account '{name}' ({email}) attempted login",
                "HIGH"
            )
            return

        # ── APPROVAL CHECK ────────────────────────────────────────
        if not is_approved:
            PendingApprovalDialog(
                "Your account is pending approval.\n\n"
                "The SuperAdmin must approve your account before you can log in.\n\n"
                "Please check back later or contact the administrator."
            ).exec_()
            write_audit_log(username=name, role=role,
                            action="LOGIN_DENIED_PENDING", method="Password",
                            details=f"Email: {email}")
            return

        # ── PRIVATE KEY WARNING ───────────────────────────────────
        # Only relevant for Receiver — they need the key to decrypt files.
        # SuperAdmin and Admin never decrypt evidence, so skip for them.
        if role == "Receiver" and not private_key_exists(name):
            QtWidgets.QMessageBox.warning(
                self, "Private Key Missing",
                f"Warning: No private key found for '{name}' on this machine.\n\n"
                "If you registered on a different computer, you will not be able "
                "to decrypt received files here.\n\n"
                "If this is a fresh install, please re-register your account."
            )

        # ── WRITE LOGIN AUDIT ─────────────────────────────────────
        write_audit_log(username=name, role=role,
                        action="USER_LOGIN", method="Password",
                        details=f"Email: {email}")

        # ── CHANGE 1: login_history table ────────────────────────
        try:
            from datetime import datetime as _dt
            conn = sqlite3.connect(DB_PATH)   # ✅ SAHI
            cur  = conn.cursor()
            cur.execute(
                "INSERT INTO login_history (username, login_time, status) "
                "VALUES (?, ?, ?)",
                (name, _dt.now().strftime("%Y-%m-%d %H:%M:%S"), "Success")
            )
            conn.commit(); conn.close()
        except Exception as e:
            print(f"[login_history] {e}")

        self.open_dashboard_by_role(role, name)

    def open_dashboard_by_role(self, role, name):
        global dashboard_window
        if role == "SuperAdmin":
            # SuperAdmin uses Admin dashboard with elevated privileges
            # Pass role="SuperAdmin" so admin_dashboard can show extra controls
            from admin_dashboard import AdminDashboard
            dashboard_window = AdminDashboard(name, role="SuperAdmin")
        elif role == "Admin":
            from admin_dashboard import AdminDashboard
            dashboard_window = AdminDashboard(name, role="Admin")
        elif role == "Sender":
            from sender_dashboard import SenderDashboard
            dashboard_window = SenderDashboard(name)
        elif role == "Receiver":
            from receiver_dashboard import ReceiverDashboard
            dashboard_window = ReceiverDashboard(name)
        else:
            self.errorLabel.setText(f"Unknown role: {role}"); return

        dashboard_window.showMaximized()
        if self.window():
            self.window().hide()

    def toggle_password_visibility(self):
        if self.password.echoMode() == QtWidgets.QLineEdit.Password:
            self.password.setEchoMode(QtWidgets.QLineEdit.Normal)
        else:
            self.password.setEchoMode(QtWidgets.QLineEdit.Password)


# =======================================================
# MAIN APP WINDOW
# =======================================================
class MainAppWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Secure Data Sharing Framework")
        self.setStyleSheet(f"background-color:{BLUE_LIGHT_BG};")
        self.showMaximized()
        self.setMinimumSize(QtWidgets.QDesktopWidget().availableGeometry().size())

        # Initialise DB, migrate schema, then seed SuperAdmin
        create_users_db()
        migrate_existing_db()
        seed_superadmin()          # ← NEW: creates SuperAdmin if not present

        self.stack = QtWidgets.QStackedWidget()
        self.welcome_page = WelcomePage(self)
        self.signin_page  = SigninPage(self)
        self.signup_page  = SignupPage(self)

        self.stack.addWidget(self.welcome_page)   # Index 0
        self.stack.addWidget(self.signin_page)    # Index 1
        self.stack.addWidget(self.signup_page)    # Index 2

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.stack)

        self.welcome_page.switch_page.connect(self.navigate)
        self.signin_page.switch_page.connect(self.navigate)
        self.signup_page.switch_page.connect(self.navigate)

    def navigate(self, target_index):
        self.stack.setCurrentIndex(target_index)


# =======================================================
# ENTRY POINT
# =======================================================
if __name__ == "__main__":
    create_users_db()
    migrate_existing_db()
    seed_superadmin()
    app = QtWidgets.QApplication(sys.argv)
    win = MainAppWindow()
    win.show()
    sys.exit(app.exec_())