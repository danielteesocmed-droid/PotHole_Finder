import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "./pothole.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_name TEXT,
            contact TEXT,
            address TEXT NOT NULL,
            landmark TEXT,
            latitude REAL,
            longitude REAL,
            severity TEXT NOT NULL DEFAULT 'moderate',
            description TEXT,
            photo_path TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            admin_notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Create default admin
    from auth import hash_password
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin1234")

    existing = c.execute("SELECT id FROM admins WHERE username = ?", (admin_username,)).fetchone()
    if not existing:
        c.execute(
            "INSERT INTO admins (username, password_hash, created_at) VALUES (?, ?, ?)",
            (admin_username, hash_password(admin_password), datetime.utcnow().isoformat())
        )

    conn.commit()
    conn.close()
