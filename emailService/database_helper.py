import sqlite3
def get_db_connection():
    return sqlite3.connect('../users.db') # Jo file app.py mein ban rahi hai

