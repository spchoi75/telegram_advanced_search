"""
TeleSearch-KR: Supabase Module
Supabase 연결 및 동기화 유틸리티
"""

import os

from dotenv import load_dotenv
from supabase import Client, create_client


def get_supabase_config() -> dict:
    """
    Load Supabase configuration from environment.

    Returns:
        dict with url, anon_key, service_key
    """
    load_dotenv()

    return {
        "url": os.getenv("SUPABASE_URL"),
        "anon_key": os.getenv("SUPABASE_ANON_KEY"),
        "service_key": os.getenv("SUPABASE_SERVICE_KEY"),
    }


def get_client(use_service_key: bool = False) -> Client:
    """
    Create Supabase client.

    Args:
        use_service_key: If True, use service key (for INSERT/UPDATE).
                        If False, use anon key (for SELECT only).

    Returns:
        Supabase Client

    Raises:
        ValueError if required environment variables are missing
    """
    config = get_supabase_config()

    if not config["url"]:
        raise ValueError("SUPABASE_URL is required in .env file")

    key = config["service_key"] if use_service_key else config["anon_key"]
    if not key:
        key_name = "SUPABASE_SERVICE_KEY" if use_service_key else "SUPABASE_ANON_KEY"
        raise ValueError(f"{key_name} is required in .env file")

    return create_client(config["url"], key)


def get_last_synced_id(client: Client) -> int:
    """
    Get the last synced message ID from Supabase.

    Args:
        client: Supabase client

    Returns:
        Last message ID or 0 if no messages exist
    """
    result = client.table("messages").select("id").order("id", desc=True).limit(1).execute()

    if result.data:
        return result.data[0]["id"]
    return 0


def batch_upsert(client: Client, messages: list, batch_size: int = 1000) -> int:
    """
    Upsert messages in batches to Supabase.

    Args:
        client: Supabase client (with service key)
        messages: List of message dicts
        batch_size: Number of messages per batch

    Returns:
        Total number of upserted messages
    """
    total = 0

    for i in range(0, len(messages), batch_size):
        batch = messages[i : i + batch_size]
        client.table("messages").upsert(batch).execute()
        total += len(batch)

    return total
