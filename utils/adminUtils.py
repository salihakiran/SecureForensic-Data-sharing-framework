import sqlite3
from database_helper import get_db_connection
def fetch_pending_users():

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    users = cursor.execute(
            "SELECT name, email, role, status, created_at FROM users"
            ).fetchall()

    return users


def update_user_status(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    status = cursor.execute("SELECT status FROM users WHERE email = ?", (email,)).fetchone()


    status_up = 0 if status[0] else 1
    cursor.execute(
            "UPDATE users SET status = ? WHERE email = ? ", (status_up,email))
    conn.commit()
    conn.close()
