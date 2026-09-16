"""
Structured and sanitized logging configuration for TPMC.
Redacts secret tokens, hashes, and session strings from all log outputs.
"""

from __future__ import annotations

import logging
import sys
from typing import Iterable


class SecretRedactingFilter(logging.Filter):
    """
    Log filter that intercepts log records and scrubs any sensitive substrings
    (e.g., BOT_TOKEN, API_HASH, TELEGRAM_SESSION).
    """

    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        # Filter out empty or trivially short strings (less than 4 chars) to avoid false positives
        self.secrets = [s for s in secrets if s and len(s) >= 4]

    def filter(self, record: logging.LogRecord) -> bool:
        if not self.secrets:
            return True

        if isinstance(record.msg, str):
            msg = record.msg
            for secret in self.secrets:
                if secret in msg:
                    msg = msg.replace(secret, "***REDACTED***")
            record.msg = msg

        if record.args:
            if isinstance(record.args, dict):
                scrubbed_args = {}
                for k, v in record.args.items():
                    val_str = str(v)
                    for secret in self.secrets:
                        val_str = val_str.replace(secret, "***REDACTED***")
                    scrubbed_args[k] = val_str
                record.args = scrubbed_args
            elif isinstance(record.args, (list, tuple)):
                scrubbed_list = []
                for item in record.args:
                    val_str = str(item)
                    for secret in self.secrets:
                        val_str = val_str.replace(secret, "***REDACTED***")
                    scrubbed_list.append(val_str)
                record.args = tuple(scrubbed_list)

        return True


def setup_logging(level_name: str = "INFO", secrets: Iterable[str] | None = None) -> None:
    """
    Configure root logging with sanitized formatter and sensitive data filter.
    """
    level = getattr(logging, level_name.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Ensure stdout handles UTF-8 emojis on Windows consoles
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    if secrets:
        redacting_filter = SecretRedactingFilter(secrets)
        console_handler.addFilter(redacting_filter)

    root_logger.addHandler(console_handler)

    # Suppress verbose noisy logging from external libraries like telethon or asyncio
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
