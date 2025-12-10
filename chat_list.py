#!/usr/bin/env python3
"""
TeleSearch-KR: Chat List
사용자의 전체 대화 목록을 조회하는 도구
"""

import argparse
import asyncio
import json
import sys

from lib.telegram import get_chat_type, get_client, load_telegram_config

MAX_RETRIES = 3


async def get_chat_list(client) -> list:
    """
    Fetch all dialogs (chats) from Telegram.

    Args:
        client: Authenticated TelegramClient

    Returns:
        List of chat dicts with id, name, type
    """
    chats = []

    async for dialog in client.iter_dialogs():
        chat_type = get_chat_type(dialog.entity)

        # Get chat ID (handle different entity types)
        chat_id = dialog.id

        chats.append({
            "id": chat_id,
            "name": dialog.name or "(Unknown)",
            "type": chat_type,
        })

    return chats


async def main_async():
    """Async main entry point."""
    config = load_telegram_config()

    # Retry logic for network errors
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            client = await get_client(config)
            try:
                chats = await get_chat_list(client)
                return {"chats": chats}
            finally:
                await client.disconnect()
        except ConnectionError as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                print(f"Connection error, retrying... ({attempt + 1}/{MAX_RETRIES})", file=sys.stderr)
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            continue
        except Exception as e:
            # Handle session not found
            if "session" in str(e).lower():
                return {"error": "Telegram 인증이 필요합니다", "code": "SESSION_NOT_FOUND"}
            raise

    return {"error": f"네트워크 오류: {last_error}", "code": "NETWORK_ERROR"}


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="List all Telegram chats")
    parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="json",
        help="Output format (default: json)",
    )
    args = parser.parse_args()

    result = asyncio.run(main_async())

    if "error" in result:
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # Table format for CLI
        print(f"{'ID':<20} {'Type':<12} Name")
        print("-" * 60)
        for chat in result["chats"]:
            print(f"{chat['id']:<20} {chat['type']:<12} {chat['name']}")
        print(f"\nTotal: {len(result['chats'])} chats")


if __name__ == "__main__":
    main()
