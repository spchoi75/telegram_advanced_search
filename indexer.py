#!/usr/bin/env python3
"""
TeleSearch-KR: Telegram Message Indexer
텔레그램 메시지를 수집하여 SQLite DB에 저장하는 도구
"""

import argparse
import asyncio
import json
import os
import signal
import sqlite3
import sys
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv

# ============================================================
# Global State for Cancellation
# ============================================================

_cancelled = False
_takeout_client = None
_current_session_messages = []  # 현재 세션에서 추가된 메시지 ID들
_start_time = None


def handle_signal(signum, frame):
    """Handle SIGINT/SIGTERM for graceful cancellation."""
    global _cancelled
    _cancelled = True
    print_progress({"type": "cancelling", "message": "취소 요청 수신..."}, json_mode=True)


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def print_progress(data: dict, json_mode: bool = False):
    """Print progress in JSON or text format."""
    if json_mode:
        print(json.dumps(data, ensure_ascii=False), flush=True)
    else:
        if data.get("type") == "progress":
            msg = data.get("message", "")
            print(f"  {msg}", end="\r")
        else:
            print(data.get("message", ""))


from telethon import TelegramClient
from telethon.errors import (
    ChatAdminRequiredError,
    FloodWaitError,
    TakeoutInitDelayError,
)
from telethon.tl.types import Message

# ============================================================
# Configuration Layer
# ============================================================

def load_env():
    """Load environment variables from .env file."""
    load_dotenv()

    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    phone = os.getenv("PHONE")
    default_chat_id = os.getenv("DEFAULT_CHAT_ID")
    db_path = os.getenv("DB_PATH", "./search.db")

    if not api_id or not api_hash:
        print("Error: API_ID and API_HASH are required in .env file")
        print("Get them from https://my.telegram.org")
        sys.exit(1)

    return {
        "api_id": int(api_id),
        "api_hash": api_hash,
        "phone": phone,
        "default_chat_id": int(default_chat_id) if default_chat_id else None,
        "db_path": db_path,
    }


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Index Telegram messages for Korean full-text search"
    )
    parser.add_argument(
        "--chat-id",
        type=int,
        help="Target chat ID (overrides DEFAULT_CHAT_ID in .env)",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=3,
        help="Number of years to fetch (default: 3)",
    )
    parser.add_argument(
        "--db",
        type=str,
        help="Database path (overrides DB_PATH in .env)",
    )
    parser.add_argument(
        "--json-progress",
        action="store_true",
        help="Output progress in JSON format for GUI integration",
    )
    return parser.parse_args()


# ============================================================
# Storage Layer
# ============================================================

def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize SQLite database with FTS5 trigram support."""
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
    """Get the last saved message ID for incremental backup."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT MAX(id) FROM messages WHERE chat_id = ?",
        (chat_id,)
    )
    result = cursor.fetchone()[0]
    return result if result else 0


def batch_insert(conn: sqlite3.Connection, messages: list):
    """Insert messages in batch using executemany."""
    global _current_session_messages
    if not messages:
        return

    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT OR IGNORE INTO messages (id, chat_id, sender_id, date, text)
        VALUES (?, ?, ?, ?, ?)
        """,
        messages
    )
    conn.commit()

    # Track inserted message IDs for potential rollback
    _current_session_messages.extend([m[0] for m in messages])


def rollback_session(conn: sqlite3.Connection, chat_id: int):
    """Rollback messages inserted during this session."""
    global _current_session_messages
    if not _current_session_messages:
        return 0

    cursor = conn.cursor()
    placeholders = ",".join("?" * len(_current_session_messages))
    cursor.execute(
        f"DELETE FROM messages WHERE id IN ({placeholders}) AND chat_id = ?",
        _current_session_messages + [chat_id]
    )
    deleted = cursor.rowcount
    conn.commit()
    _current_session_messages = []
    return deleted


# ============================================================
# Telegram Layer
# ============================================================

async def create_client(config: dict) -> TelegramClient:
    """Create and authenticate Telegram client."""
    client = TelegramClient(
        "telesearch_session",
        config["api_id"],
        config["api_hash"]
    )
    client.flood_sleep_threshold = 60  # Auto-wait up to 60 seconds

    await client.start(phone=config["phone"])
    return client


async def fetch_messages(
    client: TelegramClient,
    chat_id: int,
    min_id: int,
    offset_date: datetime,
    batch_size: int = 1000,
    json_mode: bool = False
):
    """
    Fetch messages from Telegram using TakeoutClient.
    Yields batches of messages for efficient processing.
    """
    global _cancelled, _takeout_client, _start_time
    _start_time = time.time()

    try:
        async with client.takeout(
            contacts=False,
            users=False,
            chats=True,
            megagroups=True,
            channels=True,
            files=False,
        ) as takeout:
            _takeout_client = takeout
            batch = []
            count = 0

            async for message in takeout.iter_messages(
                chat_id,
                min_id=min_id,
                offset_date=offset_date,
                reverse=False,
            ):
                # Check for cancellation
                if _cancelled:
                    print_progress({
                        "type": "cancelled",
                        "message": "인덱싱이 취소되었습니다.",
                        "collected": count
                    }, json_mode)
                    return

                # Skip non-text messages
                if not isinstance(message, Message) or not message.text:
                    continue

                batch.append((
                    message.id,
                    chat_id,
                    message.sender_id,
                    int(message.date.timestamp()),
                    message.text,
                ))
                count += 1

                if len(batch) >= batch_size:
                    yield batch
                    elapsed = time.time() - _start_time
                    # ETA 계산 (총 개수를 모르므로 수집 속도 기반)
                    rate = count / elapsed if elapsed > 0 else 0
                    print_progress({
                        "type": "progress",
                        "phase": "fetching",
                        "current": count,
                        "total": None,  # 총 개수는 알 수 없음
                        "message": f"Collected {count} messages...",
                        "elapsed_sec": int(elapsed),
                        "rate": round(rate, 1)  # 초당 메시지 수
                    }, json_mode)
                    batch = []

            # Yield remaining messages
            if batch:
                yield batch
                elapsed = time.time() - _start_time
                print_progress({
                    "type": "progress",
                    "phase": "fetching",
                    "current": count,
                    "total": None,
                    "message": f"Collected {count} messages...",
                    "elapsed_sec": int(elapsed)
                }, json_mode)

            print_progress({
                "type": "complete",
                "message": f"Total: {count} messages",
                "total": count,
                "elapsed_sec": int(time.time() - _start_time)
            }, json_mode)

    except TakeoutInitDelayError as e:
        wait_time = e.seconds
        print_progress({
            "type": "error",
            "code": "TAKEOUT_DELAY",
            "message": f"Telegram requires waiting {wait_time} seconds before takeout.",
            "wait_seconds": wait_time
        }, json_mode)
        raise
    except ChatAdminRequiredError:
        print_progress({
            "type": "error",
            "code": "ADMIN_REQUIRED",
            "message": f"Admin permission required for chat {chat_id}"
        }, json_mode)
        raise
    finally:
        _takeout_client = None


# ============================================================
# Main
# ============================================================

async def main():
    """Main entry point."""
    global _cancelled, _current_session_messages

    # Load configuration
    config = load_env()
    args = parse_args()
    json_mode = args.json_progress

    # Determine chat ID
    chat_id = args.chat_id or config["default_chat_id"]
    if not chat_id:
        print_progress({
            "type": "error",
            "code": "NO_CHAT_ID",
            "message": "No chat ID specified. Use --chat-id argument or set DEFAULT_CHAT_ID in .env"
        }, json_mode)
        sys.exit(1)

    # Determine DB path
    db_path = args.db or config["db_path"]

    # Calculate offset date
    offset_date = datetime.now() - timedelta(days=365 * args.years)

    # Print start info
    print_progress({
        "type": "start",
        "chat_id": chat_id,
        "db_path": db_path,
        "years": args.years,
        "message": f"TeleSearch-KR Indexer - Chat {chat_id}"
    }, json_mode)

    if not json_mode:
        print(f"TeleSearch-KR Indexer")
        print(f"=" * 40)
        print(f"Chat ID: {chat_id}")
        print(f"Database: {db_path}")
        print(f"Period: Last {args.years} year(s)")
        print(f"=" * 40)

    # Initialize database
    conn = init_db(db_path)
    _current_session_messages = []  # Reset session tracking

    # Get last message ID for incremental backup
    min_id = get_last_message_id(conn, chat_id)
    if min_id > 0:
        print_progress({
            "type": "info",
            "message": f"Incremental mode: Starting from message ID {min_id}"
        }, json_mode)
    else:
        print_progress({
            "type": "info",
            "message": "Full sync mode: Fetching all messages"
        }, json_mode)

    # Create Telegram client
    print_progress({"type": "info", "message": "Connecting to Telegram..."}, json_mode)
    client = await create_client(config)

    try:
        # Fetch and store messages
        print_progress({
            "type": "info",
            "message": f"Fetching messages from chat {chat_id}..."
        }, json_mode)
        total = 0

        async for batch in fetch_messages(client, chat_id, min_id, offset_date, json_mode=json_mode):
            if _cancelled:
                break
            batch_insert(conn, batch)
            total += len(batch)

        # Handle cancellation with rollback
        if _cancelled:
            print_progress({
                "type": "rolling_back",
                "message": "롤백 중...",
                "messages_to_delete": len(_current_session_messages)
            }, json_mode)
            deleted = rollback_session(conn, chat_id)
            print_progress({
                "type": "cancelled",
                "message": f"인덱싱이 취소되었습니다. {deleted}개 메시지 롤백됨.",
                "rolled_back": deleted
            }, json_mode)
            sys.exit(130)  # Standard exit code for SIGINT

        print_progress({
            "type": "complete",
            "message": f"Indexing complete! Total: {total} messages",
            "total": total
        }, json_mode)

    except (TakeoutInitDelayError, ChatAdminRequiredError):
        # Rollback on error
        if _current_session_messages:
            rollback_session(conn, chat_id)
        sys.exit(1)
    except FloodWaitError as e:
        print_progress({
            "type": "error",
            "code": "FLOOD_WAIT",
            "message": f"Rate limited. Waiting {e.seconds} seconds...",
            "wait_seconds": e.seconds
        }, json_mode)
        # Rollback on error
        if _current_session_messages:
            rollback_session(conn, chat_id)
        sys.exit(1)
    finally:
        conn.close()
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
