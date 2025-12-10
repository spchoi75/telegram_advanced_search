"""
Tests for searcher.py JSON output
"""

import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

# Import functions from searcher
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from searcher import build_link, build_query, format_json_results


class TestBuildLink:
    """Test build_link function."""

    def test_supergroup_link(self):
        """Test link generation for supergroup (negative ID with -100 prefix)."""
        link = build_link(-1001234567890, 42)
        assert link == "https://t.me/c/1234567890/42"

    def test_channel_link(self):
        """Test link generation for channel."""
        link = build_link(-1009876543210, 100)
        assert link == "https://t.me/c/9876543210/100"

    def test_positive_chat_id(self):
        """Test link generation for positive chat ID."""
        link = build_link(123456789, 1)
        assert link == "https://t.me/c/123456789/1"


class TestBuildQuery:
    """Test build_query function."""

    def test_basic_query(self):
        """Test basic query without chat_id filter."""
        query, params = build_query("테스트", limit=10)
        assert "fts_messages MATCH" in query
        assert params[0] == '"테스트"'
        assert params[-1] == 10

    def test_query_with_chat_id(self):
        """Test query with chat_id filter."""
        query, params = build_query("검색어", chat_id=-1001234567890, limit=20)
        assert "m.chat_id = ?" in query
        assert -1001234567890 in params

    def test_query_escapes_quotes(self):
        """Test that double quotes are escaped."""
        query, params = build_query('test"query', limit=10)
        assert params[0] == '"test""query"'


class TestFormatJsonResults:
    """Test format_json_results function."""

    def test_empty_results(self):
        """Test empty results."""
        output = format_json_results([], 5.5)
        assert output["count"] == 0
        assert output["elapsed_ms"] == 5.5
        assert output["results"] == []

    def test_single_result(self):
        """Test single result formatting."""
        # Create mock row
        mock_row = {
            "id": 42,
            "chat_id": -1001234567890,
            "date": int(datetime(2024, 3, 15, 14, 32).timestamp()),
            "text": "테스트 메시지입니다",
        }

        # SQLite Row-like dict
        class MockRow(dict):
            def __getitem__(self, key):
                return dict.__getitem__(self, key)

        row = MockRow(mock_row)

        output = format_json_results([row], 23.5)

        assert output["count"] == 1
        assert output["elapsed_ms"] == 23.5
        assert len(output["results"]) == 1

        result = output["results"][0]
        assert result["id"] == 42
        assert result["chat_id"] == -1001234567890
        assert result["text"] == "테스트 메시지입니다"
        assert result["link"] == "https://t.me/c/1234567890/42"
        assert "2024-03-15" in result["date"]


class TestSearcherIntegration:
    """Integration tests with actual SQLite database."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create tables
        cursor.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                sender_id INTEGER,
                date INTEGER NOT NULL,
                text TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE VIRTUAL TABLE fts_messages USING fts5(
                text,
                content='messages',
                content_rowid='id',
                tokenize='trigram'
            )
        """)

        cursor.execute("""
            CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO fts_messages(rowid, text) VALUES (new.id, new.text);
            END
        """)

        # Insert test data
        test_messages = [
            (1, -1001234567890, 123, int(datetime(2024, 3, 15, 14, 32).timestamp()), "텔레그램에서 재밌는 영상을 봤어요"),
            (2, -1001234567890, 456, int(datetime(2024, 3, 10, 9, 15).timestamp()), "텔레그램 봇 만들기 튜토리얼"),
            (3, -1009876543210, 789, int(datetime(2024, 3, 5, 12, 0).timestamp()), "카카오톡보다 텔레그램이 좋아요"),
        ]

        cursor.executemany(
            "INSERT INTO messages (id, chat_id, sender_id, date, text) VALUES (?, ?, ?, ?, ?)",
            test_messages,
        )

        conn.commit()
        conn.close()

        yield db_path

        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    def test_search_finds_matches(self, temp_db):
        """Test that search finds matching messages."""
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.chat_id, m.sender_id, m.date, m.text
            FROM messages m
            INNER JOIN fts_messages fts ON m.id = fts.rowid
            WHERE fts_messages MATCH '"텔레그램"'
            ORDER BY m.date DESC
        """)

        results = cursor.fetchall()
        conn.close()

        assert len(results) == 3  # All 3 messages contain "텔레그램"

    def test_search_korean_partial_match(self, temp_db):
        """Test Korean partial matching with trigram."""
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.id, m.text
            FROM messages m
            INNER JOIN fts_messages fts ON m.id = fts.rowid
            WHERE fts_messages MATCH '"재밌는"'
        """)

        results = cursor.fetchall()
        conn.close()

        assert len(results) == 1
        assert "재밌는" in results[0]["text"]
