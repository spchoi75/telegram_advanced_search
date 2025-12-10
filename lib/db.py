"""
TeleSearch-KR: Database Module
SQLite 연결 및 공통 DB 유틸리티
"""

import os
import sqlite3

from dotenv import load_dotenv


def get_db_path() -> str:
    """Get database path from environment."""
    load_dotenv()
    return os.getenv("DB_PATH", "./search.db")


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """
    Get SQLite connection with row factory.

    Args:
        db_path: Database path. If None, uses DB_PATH from .env

    Returns:
        sqlite3.Connection with Row factory enabled
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = None) -> sqlite3.Connection:
    """
    Initialize database with FTS5 trigram support.

    Args:
        db_path: Database path. If None, uses DB_PATH from .env

    Returns:
        sqlite3.Connection with tables created
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            sender_id INTEGER,
            date INTEGER NOT NULL,
            text TEXT NOT NULL
        )
    """)

    # Create index for incremental backup
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_chat_date
        ON messages(chat_id, date DESC)
    """)

    # Create FTS5 virtual table with trigram tokenizer
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS fts_messages USING fts5(
            text,
            content='messages',
            content_rowid='id',
            tokenize='trigram'
        )
    """)

    # Create trigger for automatic FTS sync on INSERT
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
            INSERT INTO fts_messages(rowid, text) VALUES (new.id, new.text);
        END
    """)

    conn.commit()
    return conn


def get_last_message_id(conn: sqlite3.Connection, chat_id: int) -> int:
    """
    Get the last saved message ID for incremental backup.

    Args:
        conn: Database connection
        chat_id: Target chat ID

    Returns:
        Last message ID or 0 if no messages exist
    """
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(id) FROM messages WHERE chat_id = ?", (chat_id,))
    result = cursor.fetchone()[0]
    return result if result else 0


def batch_insert(conn: sqlite3.Connection, messages: list):
    """
    Insert messages in batch using executemany.

    Args:
        conn: Database connection
        messages: List of tuples (id, chat_id, sender_id, date, text)
    """
    if not messages:
        return

    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT OR IGNORE INTO messages (id, chat_id, sender_id, date, text)
        VALUES (?, ?, ?, ?, ?)
        """,
        messages,
    )
    conn.commit()
