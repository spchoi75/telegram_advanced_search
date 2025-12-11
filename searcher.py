#!/usr/bin/env python3
"""
TeleSearch-KR: Telegram Message Searcher
SQLite FTS5 trigram을 사용한 한국어 메시지 검색 도구
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

# ANSI color codes for terminal
COLOR_RESET = "\033[0m"
COLOR_HIGHLIGHT = "\033[1;33m"  # Bold Yellow
COLOR_DIM = "\033[2m"  # Dim
COLOR_LINK = "\033[4;36m"  # Underline Cyan


# ============================================================
# Configuration Layer
# ============================================================

def load_env():
    """Load environment variables from .env file."""
    load_dotenv()
    return {
        "db_path": os.getenv("DB_PATH", "./search.db"),
    }


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Search Telegram messages with Korean full-text search"
    )
    parser.add_argument(
        "query",
        type=str,
        help="Search keyword",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of results (default: 20)",
    )
    parser.add_argument(
        "--chat-id",
        type=int,
        help="Filter by specific chat ID (optional)",
    )
    parser.add_argument(
        "--db",
        type=str,
        help="Database path (overrides DB_PATH in .env)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )
    return parser.parse_args()


# ============================================================
# Storage Layer
# ============================================================

def connect_db(db_path: str) -> sqlite3.Connection:
    """Connect to SQLite database."""
    if not os.path.exists(db_path):
        print(f"Error: Database not found: {db_path}")
        print("Run indexer.py first to create the database.")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# Search Layer
# ============================================================

def build_query(keyword: str, chat_id: int = None, limit: int = 20) -> tuple:
    """
    Build FTS5 MATCH query.
    Returns (query_string, parameters).
    """
    # Escape special FTS5 characters
    escaped_keyword = keyword.replace('"', '""')

    if chat_id:
        query = """
            SELECT m.id, m.chat_id, m.sender_id, m.date, m.text
            FROM messages m
            INNER JOIN fts_messages fts ON m.id = fts.rowid
            WHERE fts_messages MATCH ?
            AND m.chat_id = ?
            ORDER BY m.date DESC
            LIMIT ?
        """
        params = (f'"{escaped_keyword}"', chat_id, limit)
    else:
        query = """
            SELECT m.id, m.chat_id, m.sender_id, m.date, m.text
            FROM messages m
            INNER JOIN fts_messages fts ON m.id = fts.rowid
            WHERE fts_messages MATCH ?
            ORDER BY m.date DESC
            LIMIT ?
        """
        params = (f'"{escaped_keyword}"', limit)

    return query, params


def execute_search(conn: sqlite3.Connection, query: str, params: tuple) -> list:
    """Execute search query and return results."""
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor.fetchall()


# ============================================================
# Presentation Layer
# ============================================================

def highlight_text(text: str, keyword: str, max_length: int = 200) -> str:
    """Highlight keyword in text with ANSI colors."""
    # Find keyword position (case-insensitive)
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    match = pattern.search(text)

    if not match:
        # If no exact match (shouldn't happen with FTS5), just truncate
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text

    # Calculate context window around the match
    match_start = match.start()
    match_end = match.end()

    # Try to show context around the match
    context_before = 50
    context_after = max_length - context_before - len(keyword)

    start = max(0, match_start - context_before)
    end = min(len(text), match_end + context_after)

    snippet = text[start:end]

    # Add ellipsis if truncated
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""

    # Highlight the keyword in the snippet
    highlighted = pattern.sub(
        f"{COLOR_HIGHLIGHT}\\g<0>{COLOR_RESET}",
        snippet
    )

    return f"{prefix}{highlighted}{suffix}"


def build_link(chat_id: int, message_id: int) -> str:
    """
    Build Telegram message link using tg:// protocol to open in app.
    Format: tg://privatepost?channel={channel_id}&post={message_id}

    Note: For private chats/groups, chat_id needs conversion:
    - Channels/Supergroups have IDs like -100XXXXXXXXXX
    - The link format uses the ID without -100 prefix
    """
    # Convert chat_id for link
    # Telegram uses -100 prefix for channels/supergroups
    if chat_id < 0:
        # Remove -100 prefix for link
        link_chat_id = str(chat_id).replace("-100", "")
    else:
        link_chat_id = str(chat_id)

    # Use tg:// protocol to open in Telegram app instead of web
    return f"tg://privatepost?channel={link_chat_id}&post={message_id}"


def format_result(row: sqlite3.Row, keyword: str, index: int) -> str:
    """Format a single search result for display."""
    # Parse date
    date = datetime.fromtimestamp(row["date"])
    date_str = date.strftime("%Y-%m-%d %H:%M")

    # Build components
    link = build_link(row["chat_id"], row["id"])
    highlighted_text = highlight_text(row["text"], keyword)

    # Replace newlines with spaces for cleaner output
    highlighted_text = highlighted_text.replace("\n", " ")

    return f"""
{COLOR_DIM}[{index}] {date_str}{COLOR_RESET}
{highlighted_text}
{COLOR_LINK}{link}{COLOR_RESET}
"""


def print_results(results: list, keyword: str, elapsed_time: float):
    """Print all search results in CLI format."""
    if not results:
        print(f"\nNo results found for '{keyword}'")
        return

    print(f"\nFound {len(results)} result(s) in {elapsed_time:.3f}s")
    print("=" * 60)

    for i, row in enumerate(results, 1):
        print(format_result(row, keyword, i))

    print("=" * 60)


def format_json_results(results: list, elapsed_ms: float) -> dict:
    """Format search results as JSON-serializable dict."""
    formatted_results = []

    for row in results:
        date = datetime.fromtimestamp(row["date"])
        link = build_link(row["chat_id"], row["id"])

        formatted_results.append({
            "id": row["id"],
            "chat_id": row["chat_id"],
            "date": date.isoformat(),
            "text": row["text"],
            "link": link,
        })

    return {
        "count": len(results),
        "elapsed_ms": round(elapsed_ms, 2),
        "results": formatted_results,
    }


def print_json_results(results: list, elapsed_ms: float):
    """Print search results in JSON format."""
    output = format_json_results(results, elapsed_ms)
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ============================================================
# Main
# ============================================================

def main():
    """Main entry point."""
    # Load configuration
    config = load_env()
    args = parse_args()

    # Validate query length (minimum 3 characters for trigram)
    if len(args.query) < 3:
        if args.json:
            print(json.dumps({
                "error": "검색어는 최소 3글자 이상이어야 합니다",
                "code": "QUERY_TOO_SHORT"
            }, ensure_ascii=False))
        else:
            print("Error: 검색어는 최소 3글자 이상이어야 합니다", file=sys.stderr)
        sys.exit(1)

    # Determine DB path
    db_path = args.db or config["db_path"]

    # Check database exists (for JSON mode, return error instead of exit)
    if not os.path.exists(db_path):
        if args.json:
            print(json.dumps({
                "error": "인덱싱을 먼저 실행하세요",
                "code": "DB_NOT_FOUND"
            }, ensure_ascii=False))
        else:
            print(f"Error: Database not found: {db_path}", file=sys.stderr)
            print("Run indexer.py first to create the database.", file=sys.stderr)
        sys.exit(1)

    # Connect to database
    conn = connect_db(db_path)

    try:
        # Build and execute query
        query, params = build_query(args.query, args.chat_id, args.limit)

        start_time = time.time()
        results = execute_search(conn, query, params)
        elapsed_time = time.time() - start_time
        elapsed_ms = elapsed_time * 1000

        # Print results based on format
        if args.json:
            print_json_results(results, elapsed_ms)
        else:
            print_results(results, args.query, elapsed_time)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
