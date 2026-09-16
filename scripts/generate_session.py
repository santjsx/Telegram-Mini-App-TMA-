#!/usr/bin/env python3
"""
Telegram Personal Music Cloud (TPMC) - StringSession Generator
Use this script locally to generate the TELEGRAM_SESSION string for your user account,
and optionally the BOT_SESSION string for the bot.

The resulting session string should be stored in your Render environment variables.
NEVER share or commit session strings to Git!
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, cast
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

# Load existing .env if present
env_path = Path(".env")
if env_path.exists():
    load_dotenv(dotenv_path=env_path)


async def generate_user_session(api_id: int, api_hash: str) -> None:
    print("\n" + "-" * 60)
    print("STEP 1: Generating User MTProto Session (TELEGRAM_SESSION)")
    print("-" * 60)
    print("Telegram will send a confirmation code to your Telegram app (or SMS).")
    
    session = StringSession()
    client = TelegramClient(session, api_id, api_hash)
    
    try:
        await cast(Any, client.start())
        me = await client.get_me()
        session_str = client.session.save()

        print("\n" + "=" * 60)
        print(f"🎉 [SUCCESS] Authorized User Account: {me.first_name} (@{me.username}) [ID: {me.id}]")
        print("=" * 60)
        print("Copy the following TELEGRAM_SESSION value to your Render Environment Variables:")
        print("-" * 60)
        print(session_str)
        print("-" * 60)
    except Exception as e:
        print(f"\n[ERROR] User authorization failed: {e}")
    finally:
        await client.disconnect()


async def generate_bot_session(api_id: int, api_hash: str, bot_token: str) -> None:
    print("\n" + "-" * 60)
    print("STEP 2: Generating Bot Session (BOT_SESSION)")
    print("-" * 60)
    print(f"Signing in bot token ({bot_token[:10]}...)...")

    session = StringSession()
    client = TelegramClient(session, api_id, api_hash)

    try:
        await cast(Any, client.start(bot_token=bot_token))
        me = await client.get_me()
        session_str = client.session.save()

        print("\n" + "=" * 60)
        print(f"🎉 [SUCCESS] Authorized Bot: @{me.username} [ID: {me.id}]")
        print("=" * 60)
        print("Copy the following BOT_SESSION value to your Render Environment Variables:")
        print("(This bypasses Telegram bot flood waits permanently!)")
        print("-" * 60)
        print(session_str)
        print("-" * 60)
    except Exception as e:
        print(f"\n[NOTE] Bot authorization info: {e}")
        print("If the bot is currently in a Telegram flood wait, wait for the timer to expire,")
        print("or let the deployed server auto-reconnect once the timer finishes.")
    finally:
        await client.disconnect()


async def main() -> None:
    print("=" * 60)
    print("TPMC — Telethon StringSession Generator (Render Deployment)")
    print("=" * 60)

    env_api_id = os.getenv("API_ID", "").strip()
    env_api_hash = os.getenv("API_HASH", "").strip()
    env_bot_token = os.getenv("BOT_TOKEN", "").strip()

    prompt_api_id = f"API_ID [{env_api_id}]: " if env_api_id else "API_ID: "
    api_id_input = input(prompt_api_id).strip() or env_api_id

    prompt_api_hash = f"API_HASH [{env_api_hash[:6]}...]: " if env_api_hash else "API_HASH: "
    api_hash_input = input(prompt_api_hash).strip() or env_api_hash

    if not api_id_input or not api_hash_input:
        print("\n[ERROR] Both API_ID and API_HASH are required.")
        return

    try:
        api_id = int(api_id_input)
    except ValueError:
        print("\n[ERROR] API_ID must be a numeric integer.")
        return

    print("\nWhich session do you want to generate?")
    print("1) User Session only (TELEGRAM_SESSION) [Default]")
    print("2) Both User Session & Bot Session (TELEGRAM_SESSION + BOT_SESSION)")
    print("3) Bot Session only (BOT_SESSION)")
    choice = input("\nSelect [1/2/3] (default 1): ").strip() or "1"

    if choice in ("1", "2"):
        await generate_user_session(api_id, api_hash_input)

    if choice in ("2", "3"):
        prompt_bot_token = f"BOT_TOKEN [{env_bot_token[:10]}...]: " if env_bot_token else "BOT_TOKEN: "
        bot_token_input = input(prompt_bot_token).strip() or env_bot_token
        if bot_token_input:
            await generate_bot_session(api_id, api_hash_input, bot_token_input)
        else:
            print("\n[SKIPPED] No BOT_TOKEN provided.")

    print("\n" + "=" * 60)
    print("Done! Copy the session string(s) and paste into Render -> Environment.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
