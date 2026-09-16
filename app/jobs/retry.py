"""
Telegram rate limiting, FloodWait handling, and retry policy for TPMC.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Coroutine, TypeVar, Any
from telethon.errors import FloodWaitError, RPCError

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_telegram_operation(
    coro_factory: Callable[[], Coroutine[Any, Any, T]],
    max_retries: int = 3,
    flood_wait_max: int = 300,
    base_backoff: float = 1.0,
    on_flood_wait: Callable[[int], Coroutine[Any, Any, None]] | None = None,
) -> T:
    """
    Execute a Telegram coroutine with automatic FloodWait recovery and exponential backoff.
    """
    attempt = 0
    while True:
        try:
            return await coro_factory()
        except FloodWaitError as e:
            seconds = int(e.seconds)
            logger.warning(
                f"Telegram FloodWait encountered: waiting {seconds} seconds (limit={flood_wait_max}s)..."
            )
            if seconds > flood_wait_max:
                logger.error(
                    f"FloodWait duration ({seconds}s) exceeds maximum allowed ({flood_wait_max}s). Aborting operation."
                )
                raise

            if on_flood_wait:
                try:
                    await on_flood_wait(seconds)
                except Exception as notify_err:
                    logger.debug(f"FloodWait notification failed: {notify_err}")

            # Sleep requested duration plus small jitter
            await asyncio.sleep(seconds + 1)
            # FloodWait wait does not count against standard retry budget
            continue

        except (ConnectionError, asyncio.TimeoutError, OSError) as e:
            attempt += 1
            if attempt > max_retries:
                logger.error(f"Permanent connection failure after {max_retries} attempts: {e}")
                raise

            delay = base_backoff * (2 ** (attempt - 1))
            logger.warning(
                f"Transient network error on attempt {attempt}/{max_retries}: {e}. Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)

        except RPCError as e:
            # Check for non-recoverable Telegram errors (e.g. MESSAGE_ID_INVALID)
            logger.error(f"Telegram RPC error: {e}")
            raise
