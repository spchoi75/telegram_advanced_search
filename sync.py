#!/usr/bin/env python3
"""
TeleSearch-KR: Supabase Sync
SQLite 데이터를 Supabase PostgreSQL로 동기화하는 도구
"""

import argparse
import json
import signal
import sys
import time
from datetime import datetime

from lib.db import get_connection, get_db_path
from lib.supabase import batch_upsert, get_client, get_last_synced_id

BATCH_SIZE = 1000

# ============================================================
# Global State for Cancellation
# ============================================================

_cancelled = False
_synced_ids = []  # 현재 세션에서 동기화된 메시지 ID들
_start_time = None


def handle_signal(signum, frame):
    """Handle SIGINT/SIGTERM for graceful cancellation."""
    global _cancelled
    _cancelled = True


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def print_progress(data: dict, json_mode: bool = False):
    """Print progress in JSON or text format."""
    if json_mode:
        print(json.dumps(data, ensure_ascii=False), flush=True)
    else:
        msg = data.get("message", "")
        if data.get("type") == "progress":
            print(f"  {msg}", end="\r")
        else:
            print(msg)


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


def rollback_sync(supabase, synced_ids: list) -> int:
    """
    Rollback synced messages from Supabase.

    Args:
        supabase: Supabase client
        synced_ids: List of message IDs to delete

    Returns:
        Number of deleted messages
    """
    if not synced_ids:
        return 0

    try:
        # Delete in batches to avoid query limits
        deleted = 0
        for i in range(0, len(synced_ids), BATCH_SIZE):
            batch_ids = synced_ids[i : i + BATCH_SIZE]
            supabase.table("messages").delete().in_("id", batch_ids).execute()
            deleted += len(batch_ids)
        return deleted
    except Exception:
        return 0


def sync_to_supabase(db_path: str = None, verbose: bool = True, json_mode: bool = False) -> dict:
    """
    Sync local SQLite messages to Supabase.

    Args:
        db_path: SQLite database path (uses DB_PATH from .env if None)
        verbose: Print progress messages
        json_mode: Output progress in JSON format

    Returns:
        dict with synced count and status
    """
    global _cancelled, _synced_ids, _start_time
    _synced_ids = []
    _start_time = time.time()

    # Connect to local SQLite
    if db_path is None:
        db_path = get_db_path()

    try:
        conn = get_connection(db_path)
    except Exception as e:
        print_progress({
            "type": "error",
            "code": "SQLITE_ERROR",
            "message": f"SQLite 연결 실패: {e}"
        }, json_mode)
        return {"error": f"SQLite 연결 실패: {e}", "code": "SQLITE_ERROR"}

    # Connect to Supabase
    try:
        supabase = get_client(use_service_key=True)
    except ValueError as e:
        conn.close()
        print_progress({
            "type": "error",
            "code": "SUPABASE_CONFIG_ERROR",
            "message": str(e)
        }, json_mode)
        return {"error": str(e), "code": "SUPABASE_CONFIG_ERROR"}
    except Exception as e:
        conn.close()
        print_progress({
            "type": "error",
            "code": "SUPABASE_ERROR",
            "message": f"Supabase 연결 실패: {e}"
        }, json_mode)
        return {"error": f"Supabase 연결 실패: {e}", "code": "SUPABASE_ERROR"}

    try:
        # Get last synced ID
        last_synced_id = get_last_synced_id(supabase)
        print_progress({
            "type": "info",
            "message": f"Last synced ID: {last_synced_id}"
        }, json_mode)

        # Get unsynced messages
        messages = get_unsynced_messages(conn, last_synced_id)
        total_messages = len(messages)

        if total_messages == 0:
            print_progress({
                "type": "complete",
                "message": "No new messages to sync.",
                "synced": 0
            }, json_mode)
            return {"synced": 0, "status": "up_to_date"}

        print_progress({
            "type": "start",
            "message": f"Found {total_messages} new messages to sync...",
            "total": total_messages
        }, json_mode)

        # Sync in batches
        synced = 0
        for i in range(0, total_messages, BATCH_SIZE):
            # Check for cancellation
            if _cancelled:
                print_progress({
                    "type": "rolling_back",
                    "message": "롤백 중...",
                    "synced_so_far": synced
                }, json_mode)
                deleted = rollback_sync(supabase, _synced_ids)
                print_progress({
                    "type": "cancelled",
                    "message": f"동기화가 취소되었습니다. {deleted}개 메시지 롤백됨.",
                    "rolled_back": deleted
                }, json_mode)
                return {"synced": 0, "status": "cancelled", "rolled_back": deleted}

            batch = messages[i : i + BATCH_SIZE]
            batch_upsert(supabase, batch, BATCH_SIZE)
            synced += len(batch)
            _synced_ids.extend([m["id"] for m in batch])

            elapsed = time.time() - _start_time
            percentage = int((synced / total_messages) * 100)
            rate = synced / elapsed if elapsed > 0 else 0
            eta_sec = int((total_messages - synced) / rate) if rate > 0 else None

            print_progress({
                "type": "progress",
                "current": synced,
                "total": total_messages,
                "percentage": percentage,
                "message": f"Synced {synced}/{total_messages} messages ({percentage}%)",
                "elapsed_sec": int(elapsed),
                "eta_sec": eta_sec,
                "rate": round(rate, 1)
            }, json_mode)

        print_progress({
            "type": "complete",
            "message": f"Sync complete! {synced} messages synced.",
            "synced": synced,
            "elapsed_sec": int(time.time() - _start_time)
        }, json_mode)

        return {"synced": synced, "status": "success"}

    except Exception as e:
        # Rollback on error
        if _synced_ids:
            deleted = rollback_sync(supabase, _synced_ids)
            print_progress({
                "type": "error",
                "code": "SYNC_ERROR",
                "message": f"동기화 실패: {e}. {deleted}개 메시지 롤백됨.",
                "rolled_back": deleted
            }, json_mode)
            return {"error": f"동기화 실패: {e}", "code": "SYNC_ERROR", "rolled_back": deleted}
        print_progress({
            "type": "error",
            "code": "SYNC_ERROR",
            "message": f"동기화 실패: {e}"
        }, json_mode)
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
    parser.add_argument(
        "--json-progress",
        action="store_true",
        help="Output progress in JSON format for GUI integration",
    )
    args = parser.parse_args()

    json_mode = args.json_progress

    if not json_mode:
        print("TeleSearch-KR Sync")
        print("=" * 40)

    result = sync_to_supabase(
        db_path=args.db,
        verbose=not args.quiet,
        json_mode=json_mode
    )

    if "error" in result:
        if not json_mode:
            print(f"\nError: {result['error']}", file=sys.stderr)
        sys.exit(1)

    if result.get("status") == "cancelled":
        sys.exit(130)

    if not json_mode:
        print(f"\nResult: {result['synced']} messages synced")


if __name__ == "__main__":
    main()
