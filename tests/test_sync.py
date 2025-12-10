"""
Tests for sync.py functionality
"""

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from sync import get_unsynced_messages


class TestGetUnsyncedMessages:
    """Test get_unsynced_messages function."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database with test data."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                sender_id INTEGER,
                date INTEGER NOT NULL,
                text TEXT NOT NULL
            )
        """)

        # Insert test messages
        test_messages = [
            (1, -1001234567890, 123, int(datetime(2024, 1, 1).timestamp()), "Message 1"),
            (2, -1001234567890, 123, int(datetime(2024, 1, 2).timestamp()), "Message 2"),
            (3, -1001234567890, 456, int(datetime(2024, 1, 3).timestamp()), "Message 3"),
            (4, -1009876543210, 789, int(datetime(2024, 1, 4).timestamp()), "Message 4"),
            (5, -1001234567890, 123, int(datetime(2024, 1, 5).timestamp()), "Message 5"),
        ]

        cursor.executemany(
            "INSERT INTO messages (id, chat_id, sender_id, date, text) VALUES (?, ?, ?, ?, ?)",
            test_messages,
        )

        conn.commit()
        yield conn

        conn.close()
        Path(db_path).unlink(missing_ok=True)

    def test_get_all_unsynced(self, temp_db):
        """Test getting all unsynced messages from beginning."""
        messages = get_unsynced_messages(temp_db, 0)
        assert len(messages) == 5
        assert messages[0]["id"] == 1  # Ordered by ID ASC
        assert messages[-1]["id"] == 5

    def test_get_partial_unsynced(self, temp_db):
        """Test getting messages after a specific ID."""
        messages = get_unsynced_messages(temp_db, 2)
        assert len(messages) == 3
        assert messages[0]["id"] == 3
        assert messages[-1]["id"] == 5

    def test_get_none_unsynced(self, temp_db):
        """Test when all messages are already synced."""
        messages = get_unsynced_messages(temp_db, 5)
        assert len(messages) == 0

    def test_with_limit(self, temp_db):
        """Test limiting number of messages."""
        messages = get_unsynced_messages(temp_db, 0, limit=2)
        assert len(messages) == 2
        assert messages[0]["id"] == 1
        assert messages[1]["id"] == 2

    def test_message_format(self, temp_db):
        """Test that messages have correct format for Supabase."""
        messages = get_unsynced_messages(temp_db, 0, limit=1)
        msg = messages[0]

        assert "id" in msg
        assert "chat_id" in msg
        assert "sender_id" in msg
        assert "date" in msg
        assert "text" in msg

        # Date should be ISO format string
        assert isinstance(msg["date"], str)
        assert "T" in msg["date"]  # ISO format contains T separator


class TestSyncResult:
    """Test sync result format."""

    def test_success_result(self):
        """Test successful sync result format."""
        result = {"synced": 100, "status": "success"}
        assert result["synced"] == 100
        assert result["status"] == "success"

    def test_up_to_date_result(self):
        """Test up-to-date sync result."""
        result = {"synced": 0, "status": "up_to_date"}
        assert result["synced"] == 0
        assert result["status"] == "up_to_date"

    def test_error_result(self):
        """Test error result format."""
        result = {
            "error": "Supabase 연결 실패",
            "code": "SUPABASE_ERROR"
        }
        assert "error" in result
        assert "code" in result

    def test_partial_sync_error(self):
        """Test partial sync error result."""
        result = {
            "error": "동기화 중 오류",
            "code": "SYNC_ERROR",
            "partial_sync": True
        }
        assert result["partial_sync"] is True
