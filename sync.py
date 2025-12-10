#!/usr/bin/env python3
"""
TeleSearch-KR: Supabase Sync
SQLite 데이터를 Supabase PostgreSQL로 동기화하는 도구
"""

import argparse
import sys
from datetime import datetime

from lib.db import get_connection, get_db_path
from lib.supabase import batch_upsert, get_client, get_last_synced_id

BATCH_SIZE = 1000


def get_unsynced_messages(conn, last_synced_id: int, limit: int = None) -> list:
    """
    Get messages that haven't been synced yet.

    Args:
        conn: SQLite connection
        last_synced_id: Last synced message ID
        limit: Maximum number of messages to fetch (None for all)

    Returns:
        List of message dicts
    """
    cursor = conn.cursor()

    query = """
        SELECT id, chat_id, sender_id, date, text
        FROM messages
        WHERE id > ?
        ORDER BY id ASC
    """
    params = [last_synced_id]

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    messages = []
    for row in rows:
        messages.append({
            "id": row["id"],
            "chat_id": row["chat_id"],
            "sender_id": row["sender_id"],
            "date": datetime.fromtimestamp(row["date"]).isoformat(),
            "text": row["text"],
        })

    return messages


def sync_to_supabase(db_path: str = None, verbose: bool = True) -> dict:
    """
    Sync local SQLite messages to Supabase.

    Args:
        db_path: SQLite database path (uses DB_PATH from .env if None)
        verbose: Print progress messages

    Returns:
        dict with synced count and status
    """
    # Connect to local SQLite
    if db_path is None:
        db_path = get_db_path()

    try:
        conn = get_connection(db_path)
    except Exception as e:
        return {"error": f"SQLite 연결 실패: {e}", "code": "SQLITE_ERROR"}

    # Connect to Supabase
    try:
        supabase = get_client(use_service_key=True)
    except ValueError as e:
        conn.close()
        return {"error": str(e), "code": "SUPABASE_CONFIG_ERROR"}
    except Exception as e:
        conn.close()
        return {"error": f"Supabase 연결 실패: {e}", "code": "SUPABASE_ERROR"}

    try:
        # Get last synced ID
        last_synced_id = get_last_synced_id(supabase)
        if verbose:
            print(f"Last synced ID: {last_synced_id}")

        # Get unsynced messages
        messages = get_unsynced_messages(conn, last_synced_id)
        total_messages = len(messages)

        if total_messages == 0:
            if verbose:
                print("No new messages to sync.")
            return {"synced": 0, "status": "up_to_date"}

        if verbose:
            print(f"Found {total_messages} new messages to sync...")

        # Sync in batches
        synced = 0
        for i in range(0, total_messages, BATCH_SIZE):
            batch = messages[i : i + BATCH_SIZE]
            batch_upsert(supabase, batch, BATCH_SIZE)
            synced += len(batch)

            if verbose:
                print(f"  Synced {synced}/{total_messages} messages...", end="\r")

        if verbose:
            print(f"\nSync complete! {synced} messages synced.")

        return {"synced": synced, "status": "success"}

    except Exception as e:
        return {"error": f"동기화 실패: {e}", "code": "SYNC_ERROR", "partial_sync": True}
    finally:
        conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync local messages to Supabase"
    )
    parser.add_argument(
        "--db",
        type=str,
        help="Database path (overrides DB_PATH in .env)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress output",
    )
    args = parser.parse_args()

    print("TeleSearch-KR Sync")
    print("=" * 40)

    result = sync_to_supabase(db_path=args.db, verbose=not args.quiet)

    if "error" in result:
        print(f"\nError: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"\nResult: {result['synced']} messages synced")


if __name__ == "__main__":
    main()
