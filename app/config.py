"""
Configuration module for Telegram Personal Music Cloud (TPMC).
Loads, validates, and strongly-types environment variables.
Fails fast if critical secrets are missing or contain placeholder values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Recognized placeholder patterns that indicate unconfigured secrets
FORBIDDEN_PLACEHOLDERS = {
    "your_api_id_here",
    "your_api_hash_here",
    "your_bot_token_here",
    "your_channel_id_here",
    "your_session_string_here",
    "your_user_id_here",
    "1234567",
    "abcdef0123456789abcdef0123456789",
}


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str
    bot_token: str
    channel_id: int
    telegram_session: str
    authorized_user_id: int

    # Server settings
    port: int = 8080
    host: str = "0.0.0.0"
    log_level: str = "INFO"

    # Operational tuning limits
    max_concurrent_jobs: int = 1
    max_download_batch: int = 25
    max_search_results: int = 50
    flood_wait_max: int = 300

    # Access control
    approved_user_ids: tuple[int, ...] = ()

    # WebApp URL
    webapp_url: Optional[str] = None

    @classmethod
    def load_from_env(cls, env_path: Optional[str] = None) -> Config:
        """
        Load environment variables from file (if exists) and validate presence of all required items.
        Raises ValueError with clear message if any required setting is missing or invalid.
        """
        if env_path:
            load_dotenv(dotenv_path=env_path)
        else:
            load_dotenv()

        errors: list[str] = []

        # 1. API_ID
        raw_api_id = os.getenv("API_ID", "").strip()
        api_id = 0
        if not raw_api_id:
            errors.append("API_ID is required (must be an integer from https://my.telegram.org)")
        elif raw_api_id in FORBIDDEN_PLACEHOLDERS:
            errors.append(f"API_ID contains invalid placeholder: '{raw_api_id}'")
        else:
            try:
                api_id = int(raw_api_id)
            except ValueError:
                errors.append(f"API_ID must be an integer, received: '{raw_api_id}'")

        # 2. API_HASH
        api_hash = os.getenv("API_HASH", "").strip()
        if not api_hash:
            errors.append("API_HASH is required (hex string from https://my.telegram.org)")
        elif api_hash in FORBIDDEN_PLACEHOLDERS:
            errors.append(f"API_HASH contains invalid placeholder: '{api_hash}'")

        # 3. BOT_TOKEN
        bot_token = os.getenv("BOT_TOKEN", "").strip()
        if not bot_token:
            errors.append("BOT_TOKEN is required (token from @BotFather)")
        elif bot_token in FORBIDDEN_PLACEHOLDERS:
            errors.append(f"BOT_TOKEN contains invalid placeholder: '{bot_token}'")

        # 4. CHANNEL_ID
        raw_channel_id = os.getenv("CHANNEL_ID", "").strip()
        channel_id = 0
        if not raw_channel_id:
            errors.append("CHANNEL_ID is required (Telegram private channel ID, e.g., -1001234567890)")
        elif raw_channel_id in FORBIDDEN_PLACEHOLDERS:
            errors.append(f"CHANNEL_ID contains invalid placeholder: '{raw_channel_id}'")
        else:
            try:
                channel_id = int(raw_channel_id)
            except ValueError:
                errors.append(f"CHANNEL_ID must be a numeric ID (e.g. -1001234567890), received: '{raw_channel_id}'")

        # 5. TELEGRAM_SESSION
        telegram_session = os.getenv("TELEGRAM_SESSION", "").strip()
        if not telegram_session:
            errors.append("TELEGRAM_SESSION is required (Telethon StringSession from generate_session.py)")
        elif telegram_session in FORBIDDEN_PLACEHOLDERS:
            errors.append(f"TELEGRAM_SESSION contains invalid placeholder: '{telegram_session}'")

        # 6. AUTHORIZED_USER_ID
        raw_user_id = os.getenv("AUTHORIZED_USER_ID", "").strip()
        authorized_user_id = 0
        if not raw_user_id:
            errors.append("AUTHORIZED_USER_ID is required (your Telegram user ID from @userinfobot)")
        elif raw_user_id in FORBIDDEN_PLACEHOLDERS:
            errors.append(f"AUTHORIZED_USER_ID contains invalid placeholder: '{raw_user_id}'")
        else:
            try:
                authorized_user_id = int(raw_user_id)
            except ValueError:
                errors.append(f"AUTHORIZED_USER_ID must be an integer, received: '{raw_user_id}'")

        if errors:
            formatted_errors = "\n  - " + "\n  - ".join(errors)
            raise ValueError(
                f"Configuration validation failed with {len(errors)} error(s):{formatted_errors}\n"
                "Please configure these in your environment or .env file."
            )

        # Optional settings with safe defaults
        port = int(os.getenv("PORT", "8080"))
        host = os.getenv("HOST", "0.0.0.0")
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        max_concurrent_jobs = int(os.getenv("MAX_CONCURRENT_JOBS", "1"))
        max_download_batch = int(os.getenv("MAX_DOWNLOAD_BATCH", "25"))
        max_search_results = int(os.getenv("MAX_SEARCH_RESULTS", "50"))
        flood_wait_max = int(os.getenv("FLOOD_WAIT_MAX", "300"))

        raw_approved = os.getenv("APPROVED_USER_IDS", "").strip()
        approved_user_ids_list: list[int] = []
        if raw_approved:
            for item in raw_approved.split(","):
                item = item.strip()
                if item:
                    try:
                        approved_user_ids_list.append(int(item))
                    except ValueError:
                        pass
        approved_user_ids = tuple(approved_user_ids_list)

        raw_webapp_url = os.getenv("WEBAPP_URL", "").strip() or os.getenv("RENDER_EXTERNAL_URL", "").strip()
        if not raw_webapp_url:
            raw_webapp_url = f"http://localhost:{port}"
        webapp_url = raw_webapp_url.rstrip("/")

        return cls(
            api_id=api_id,
            api_hash=api_hash,
            bot_token=bot_token,
            channel_id=channel_id,
            telegram_session=telegram_session,
            authorized_user_id=authorized_user_id,
            port=port,
            host=host,
            log_level=log_level,
            max_concurrent_jobs=max_concurrent_jobs,
            max_download_batch=max_download_batch,
            max_search_results=max_search_results,
            flood_wait_max=flood_wait_max,
            approved_user_ids=approved_user_ids,
            webapp_url=webapp_url,
        )
