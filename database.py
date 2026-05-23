import sqlite3
from datetime import datetime

def get_connection():
    return sqlite3.connect("investments.db", check_same_thread=False)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        age INTEGER,
        income INTEGER,
        goal TEXT,
        risk TEXT,
        strategy_title TEXT,
        strategy_details TEXT,
        timestamp DATETIME
    )
    """)
    conn.commit()
    conn.close()

# Initialize on import
init_db()

def save_user(age, income, goal, risk, title, strategy):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (age, income, goal, risk, strategy_title, strategy_details, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (age, income, goal, risk, title, strategy, datetime.now())
    )
    conn.commit()
    conn.close()

def get_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows