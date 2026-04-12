"""
database/db.py
SQLite database setup and operations for Meeting Intelligence App
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "meetings.db")


def get_connection():
    """Get a SQLite database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dict-like objects
    return conn


def init_db():
    """Initialize database and create all required tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Users table for authentication
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Meetings table as specified in requirements
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            transcript TEXT,
            summary TEXT,
            tasks TEXT,
            deadlines TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialized successfully.")


# ──────────────────────────────────────────────
# User Operations
# ──────────────────────────────────────────────

def create_user(username: str, hashed_password: str) -> dict | None:
    """Insert a new user. Returns user dict or None if username taken."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, hashed_password) VALUES (?, ?)",
            (username, hashed_password)
        )
        conn.commit()
        user_id = cursor.lastrowid
        return {"id": user_id, "username": username}
    except sqlite3.IntegrityError:
        return None  # Username already exists
    finally:
        conn.close()


def get_user_by_username(username: str) -> dict | None:
    """Fetch user by username."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ──────────────────────────────────────────────
# Meeting Operations
# ──────────────────────────────────────────────

def save_meeting(user_id: int, filename: str, transcript: str,
                 summary: str, tasks: str, deadlines: str) -> int:
    """Save a processed meeting to the database. Returns the new meeting ID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO meetings (user_id, filename, transcript, summary, tasks, deadlines)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, filename, transcript, summary, tasks, deadlines))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_meetings(user_id: int, search: str = "", date_filter: str = "") -> list[dict]:
    """Fetch all meetings for a user with optional search and date filter."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM meetings WHERE user_id = ?"
        params = [user_id]

        if search:
            query += " AND (filename LIKE ? OR summary LIKE ? OR tasks LIKE ?)"
            like = f"%{search}%"
            params.extend([like, like, like])

        if date_filter:
            query += " AND DATE(created_at) = ?"
            params.append(date_filter)

        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_meeting_by_id(meeting_id: int, user_id: int) -> dict | None:
    """Fetch a single meeting by ID (scoped to user)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM meetings WHERE id = ? AND user_id = ?",
            (meeting_id, user_id)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_latest_meeting(user_id: int) -> dict | None:
    """Fetch the most recently processed meeting for a user."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM meetings WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_meeting(meeting_id: int, user_id: int) -> bool:
    """Delete a meeting (scoped to user). Returns True if deleted."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM meetings WHERE id = ? AND user_id = ?",
            (meeting_id, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
