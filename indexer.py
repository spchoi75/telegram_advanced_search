#!/usr/bin/env python3
"""
TeleSearch-KR: Telegram Message Indexer
텔레그램 메시지를 수집하여 SQLite DB에 저장하는 도구
"""

import argparse
import asyncio
import os
import sqlite3
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv
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
    batch_size: int = 1000
):
    """
    Fetch messages from Telegram using TakeoutClient.
    Yields batches of messages for efficient processing.
    """
    try:
        async with client.takeout(
            contacts=False,
            users=False,
            chats=True,
            megagroups=True,
            channels=True,
            files=False,
        ) as takeout:
            batch = []
            count = 0

            async for message in takeout.iter_messages(
                chat_id,
                min_id=min_id,
                offset_date=offset_date,
                reverse=False,
            ):
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
                    print(f"  Collected {count} messages...", end="\r")
                    batch = []

            # Yield remaining messages
            if batch:
                yield batch
                print(f"  Collected {count} messages...", end="\r")

            print(f"\n  Total: {count} messages")

    except TakeoutInitDelayError as e:
        wait_time = e.seconds
        print(f"\nTelegram requires waiting {wait_time} seconds before takeout.")
        print("This is a security measure. Please try again later.")
        print(f"Estimated wait time: {timedelta(seconds=wait_time)}")
        raise
    except ChatAdminRequiredError:
        print(f"\nError: Admin permission required for chat {chat_id}")
        raise


# ============================================================
# Main
# ============================================================

async def main():
    """Main entry point."""
    # Load configuration
    config = load_env()
    args = parse_args()

    # Determine chat ID
    chat_id = args.chat_id or config["default_chat_id"]
    if not chat_id:
        print("Error: No chat ID specified.")
        print("Use --chat-id argument or set DEFAULT_CHAT_ID in .env")
        sys.exit(1)

    # Determine DB path
    db_path = args.db or config["db_path"]

    # Calculate offset date
    offset_date = datetime.now() - timedelta(days=365 * args.years)

    print(f"TeleSearch-KR Indexer")
    print(f"=" * 40)
    print(f"Chat ID: {chat_id}")
    print(f"Database: {db_path}")
    print(f"Period: Last {args.years} year(s)")
    print(f"=" * 40)

    # Initialize database
    conn = init_db(db_path)

    # Get last message ID for incremental backup
    min_id = get_last_message_id(conn, chat_id)
    if min_id > 0:
        print(f"Incremental mode: Starting from message ID {min_id}")
    else:
        print("Full sync mode: Fetching all messages")

    # Create Telegram client
    print("\nConnecting to Telegram...")
    client = await create_client(config)

    try:
        # Fetch and store messages
        print(f"\nFetching messages from chat {chat_id}...")
        total = 0

        async for batch in fetch_messages(client, chat_id, min_id, offset_date):
            batch_insert(conn, batch)
            total += len(batch)

        print(f"\nIndexing complete!")
        print(f"Total messages indexed: {total}")

    except (TakeoutInitDelayError, ChatAdminRequiredError):
        sys.exit(1)
    except FloodWaitError as e:
        print(f"\nRate limited. Waiting {e.seconds} seconds...")
        await asyncio.sleep(e.seconds)
        print("Please run the script again.")
        sys.exit(1)
    finally:
        conn.close()
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
