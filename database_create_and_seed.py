# database_create_and_seed.py
from database_config import connect
from datetime import datetime
import base64

def create_tables():
    conn = connect()
    c = conn.cursor()

    # Users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Files table
    c.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER,
        receiver_id INTEGER,
        file_name TEXT,
        file_path TEXT,
        hash_value TEXT,
        encryption_key TEXT,
        status TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(sender_id) REFERENCES users(id),
        FOREIGN KEY(receiver_id) REFERENCES users(id)
    );
    """)

    # Forensic logs
    c.execute("""
    CREATE TABLE IF NOT EXISTS forensic_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        file_id INTEGER,
        device_info TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(file_id) REFERENCES files(id)
    );
    """)

    # Anomaly logs
    c.execute("""
    CREATE TABLE IF NOT EXISTS anomaly_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        description TEXT,
        severity TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)

    conn.commit()
    conn.close()
    print("Tables created (if they did not exist).")

def seed_sample_data():
    """
    Insert sample users, a sample encrypted file record, and sample logs.
    This helps for demoing to your supervisor.
    """
    conn = connect()
    c = conn.cursor()

    # Sample users (use INSERT OR IGNORE so repeated runs are safe)
    users = [
        ("Saliha Kiran", "saliha@example.com", "hash_pass_1", "sender"),
        ("Memoona Kiran", "memoona@example.com", "hash_pass_2", "sender"),
        ("Jaweria Maryam", "jaweria@example.com", "hash_pass_3", "receiver"),
        ("Admin Faiza", "admin@example.com", "hash_admin", "admin")
    ]
    for name, email, pwdhash, role in users:
        c.execute("""
            INSERT OR IGNORE INTO users (name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        """, (name, email, pwdhash, role))

    conn.commit()

    # Fetch user ids to use for file record
    c.execute("SELECT id, email FROM users")
    rows = c.fetchall()
    email_to_id = {r[1]: r[0] for r in rows}

    sender_id = email_to_id.get("saliha@example.com")
    receiver_id = email_to_id.get("jaweria@example.com")

    # Create a sample "encrypted file" record
    # For demo purposes we will not encrypt; we just store dummy info.
    sample_file_name = "demo_document.pdf.enc"
    sample_file_path = str((conn.execute("PRAGMA database_list").fetchone()))  # placeholder
    sample_hash = "dummysha256hashvalue"
    # Generate a demo key (base64 text) to mimic Fernet key
    sample_key = base64.urlsafe_b64encode(b"this_is_a_demo_key_32byteslong!!")[:44].decode('utf-8')

    # Insert file record only if not already present
    c.execute("""
        SELECT id FROM files WHERE file_name = ?
    """, (sample_file_name,))
    if c.fetchone() is None:
        c.execute("""
            INSERT INTO files (sender_id, receiver_id, file_name, file_path, hash_value, encryption_key, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sender_id, receiver_id, sample_file_name, sample_file_path, sample_hash, sample_key, "sent"))
        file_id = c.lastrowid
    else:
        c.execute("SELECT id FROM files WHERE file_name = ?", (sample_file_name,))
        file_id = c.fetchone()[0]

    conn.commit()

    # Add a couple of forensic logs
    now = datetime.utcnow().isoformat(sep=' ', timespec='seconds')
    sample_logs = [
        (sender_id, "user_registered", None, "device:PC_demo"),
        (sender_id, "file_encrypted_and_saved", file_id, "device:PC_demo"),
        (receiver_id, "file_received", file_id, "device:PC_demo")
    ]
    for user_id, action, fid, device in sample_logs:
        c.execute("""
            INSERT INTO forensic_logs (user_id, action, file_id, device_info)
            VALUES (?, ?, ?, ?)
        """, (user_id, action, fid, device))

    # Add a sample anomaly log
    c.execute("""
        INSERT INTO anomaly_logs (user_id, description, severity)
        VALUES (?, ?, ?)
    """, (sender_id, "Multiple large uploads in short time", "medium"))

    conn.commit()
    conn.close()
    print("Sample data inserted (users, a file record, logs).")

def main():
    create_tables()
    seed_sample_data()
    print("Database ready: forensic.db")

if __name__ == "__main__":
    main()
