from secureforensics_fyp.database_helper import get_db_connection
def fetch_pending_users():

    conn = get_db_connection()
    cursor = conn.cursor()

    users = cursor.execute(
            "SELECT name, email, role, status, created_at FROM users"
            ).fetchall()

    return users
