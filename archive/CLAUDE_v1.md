# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TeleSearch-KR: A personal Telegram message search tool that overcomes Korean language search limitations using SQLite FTS5 with trigram tokenizer for partial matching.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Index messages from a chat
python indexer.py --chat-id -100123456789    # specific chat
python indexer.py                             # uses DEFAULT_CHAT_ID from .env
python indexer.py --years 5                   # customize time range (default: 3 years)

# Search indexed messages
python searcher.py "검색어"                    # basic search (max 20 results)
python searcher.py "검색어" --limit 50        # adjust result count
python searcher.py "검색어" --chat-id -100123456789  # filter by chat
```

## Architecture

Two standalone CLI scripts with shared SQLite storage:

```
indexer.py ──(Telethon TakeoutClient)──► Telegram API
    │
    │ (batch INSERT, 1000/batch)
    ▼
SQLite DB (search.db)
    │
    │ (FTS5 MATCH query)
    ▼
searcher.py ──► CLI output with highlights + t.me links
```

### Database Schema

- `messages` - Main table (id, chat_id, sender_id, date, text)
- `fts_messages` - FTS5 virtual table with trigram tokenizer (auto-synced via trigger)
- `idx_messages_chat_date` - Index for incremental backup queries

### Key Design Decisions

1. **2-file separation**: indexer.py and searcher.py run independently (no shared modules)
2. **Hybrid async**: Telethon async for API, sync for SQLite (batch writes make async unnecessary)
3. **Trigger-based FTS sync**: External content table with auto-sync trigger on INSERT
4. **TakeoutClient**: Used for rate limit avoidance on bulk downloads

## Configuration

Requires `.env` file (copy from `.env.example`):
- `API_ID`, `API_HASH`: From https://my.telegram.org
- `PHONE`: Phone number for Telegram auth
- `DEFAULT_CHAT_ID`: Optional default chat
- `DB_PATH`: Database location (default: ./search.db)

## Constraints

- Search queries must be at least 3 characters (trigram tokenizer limitation)
- Text messages only (media/stickers excluded)
- First indexer run requires Telegram auth code input
