"""
TeleSearch-KR: Telegram Module
Telethon 클라이언트 공통 유틸리티
"""

import os
import sys

from dotenv import load_dotenv
from telethon import TelegramClient


def load_telegram_config() -> dict:
    """
    Load Telegram API configuration from environment.

    Returns:
        dict with api_id, api_hash, phone, default_chat_id

    Raises:
        SystemExit if required variables are missing
    """
    load_dotenv()

    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    phone = os.getenv("PHONE")
    default_chat_id = os.getenv("DEFAULT_CHAT_ID")

    if not api_id or not api_hash:
        print("Error: API_ID and API_HASH are required in .env file")
        print("Get them from https://my.telegram.org")
        sys.exit(1)

    return {
        "api_id": int(api_id),
        "api_hash": api_hash,
        "phone": phone,
        "default_chat_id": int(default_chat_id) if default_chat_id else None,
    }


async def get_client(config: dict = None, session_name: str = "telesearch_session") -> TelegramClient:
    """
    Create and authenticate Telegram client.

    Args:
        config: Telegram config dict. If None, loads from environment
        session_name: Session file name (without .session extension)

    Returns:
        Authenticated TelegramClient
    """
    if config is None:
        config = load_telegram_config()

    client = TelegramClient(session_name, config["api_id"], config["api_hash"])
    client.flood_sleep_threshold = 60  # Auto-wait up to 60 seconds

    await client.start(phone=config["phone"])
    return client


def get_chat_type(entity) -> str:
    """
    Determine chat type from Telethon entity.

    Args:
        entity: Telethon Dialog entity

    Returns:
        "user", "group", "supergroup", or "channel"
    """
    from telethon.tl.types import Channel, Chat, User

    if isinstance(entity, User):
        return "user"
    elif isinstance(entity, Chat):
        return "group"
    elif isinstance(entity, Channel):
        if entity.megagroup:
            return "supergroup"
        return "channel"
    return "unknown"
