#!/usr/bin/env python3
"""
Telegram Personal Music Cloud (TPMC) - StringSession Generator
Use this script locally to generate the TELEGRAM_SESSION string for the user account.
The resulting session string should be stored in your Render environment variables.
NEVER share or commit the session string!
"""

import asyncio
from typing import Any, cast
from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    print("=" * 60)
    print("TPMC — Telethon StringSession Generator")
    print("=" * 60)
    print("Please enter your Telegram API credentials (from https://my.telegram.org):")
    
    api_id_str = input("API_ID: ").strip()
    api_hash = input("API_HASH: ").strip()

    if not api_id_str or not api_hash:
        print("\n[ERROR] Both API_ID and API_HASH are required.")
        return

    try:
        api_id = int(api_id_str)
    except ValueError:
        print("\n[ERROR] API_ID must be an integer.")
        return

    print("\nConnecting to Telegram to authorize your account...")
    session = StringSession()
    client = TelegramClient(session, api_id, api_hash)

    try:
        await cast(Any, client.start())
        me = await client.get_me()
        session_str = client.session.save()

        print("\n" + "=" * 60)
        print(f"[SUCCESS] Authorized as: {me.first_name} (@{me.username}) [ID: {me.id}]")
        print("=" * 60)
        print("\nCopy the following TELEGRAM_SESSION value and set it as an environment variable in Render:")
        print("-" * 60)
        print(session_str)
        print("-" * 60)
        print("\nWARNING: Keep this session string secure. Anyone with this string can access your Telegram account!")
    except Exception as e:
        print(f"\n[ERROR] Authentication failed: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
