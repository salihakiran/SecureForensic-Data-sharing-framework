import sqlite3
import random
import string
import hashlib
def random_token(length=20):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def seed_users():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    users = [
        ("Alice", "pass123", "alice@example.com", "admin", 1, 0),
        ("Bob", "pass123", "bob@example.com", "investigator", 1, 0),
        ("Charlie", "pass123", "charlie@example.com", "analyst", 0, 1),
        ("David", "pass123", "david@example.com", "investigator", 1, 0),
        ("Eve", "pass123", "eve@example.com", "analyst", 0, 0),
    ]

    for name, password, email, role, is_verified, status in users:
        hash_password = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute("""
            INSERT OR IGNORE INTO users 
            (name, password, email, role, verification_token, is_verified, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            hash_password,
            email,
            role,
            random_token(),
            is_verified,
            status
        ))

    conn.commit()
    conn.close()
    print("✅ Users seeded successfully")

if __name__ == "__main__":
    seed_users()
