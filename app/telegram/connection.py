"""
Centralized Telegram connection manager and state machine.
Coordinates both the Bot client and User MTProto client.
"""

from __future__ import annotations

import asyncio
import enum
import logging
from typing import Optional, TYPE_CHECKING

from telethon.errors import FloodWaitError

if TYPE_CHECKING:
    from app.config import Config
    from app.telegram.bot import BotManager
    from app.telegram.user_client import UserClientManager

logger = logging.getLogger(__name__)


class ConnectionState(str, enum.Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    AUTH_FAILED = "AUTH_FAILED"


class TelegramConnectionManager:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.bot_state = ConnectionState.DISCONNECTED
        self.user_state = ConnectionState.DISCONNECTED
        self.bot_wait_seconds = 0

        self.bot_manager: Optional[BotManager] = None
        self.user_manager: Optional[UserClientManager] = None
        self._bot_retry_task: Optional[asyncio.Task] = None
        self.user_error: Optional[str] = None
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return (
            self.bot_state == ConnectionState.CONNECTED
            and self.user_state == ConnectionState.CONNECTED
        )

    def get_status_summary(self) -> dict[str, str]:
        bot_desc = self.bot_state.value.lower()
        if self.bot_state == ConnectionState.RECONNECTING and self.bot_wait_seconds > 0:
            bot_desc = f"reconnecting (wait {self.bot_wait_seconds}s)"
        user_desc = self.user_state.value.lower()
        if self.user_state == ConnectionState.AUTH_FAILED and self.user_error:
            short_err = (
                self.user_error[:50] + "..."
                if len(self.user_error) > 50
                else self.user_error
            )
            user_desc = f"auth_failed: {short_err}"
        return {
            "bot": bot_desc,
            "user": user_desc,
            "overall": "connected" if self.is_connected else "degraded",
        }

    async def _retry_bot_loop(self, initial_wait: int) -> None:
        """Background worker that waits for flood wait to expire, then auto-connects the bot."""
        wait = initial_wait
        while self.bot_state != ConnectionState.CONNECTED:
            try:
                logger.info(f"Bot auto-reconnect worker waiting {wait}s before retry...")
                await asyncio.sleep(wait)
                if not self.bot_manager:
                    break
                logger.info("Attempting to connect Telegram Bot client in background...")
                await self.bot_manager.connect()
                self.bot_state = ConnectionState.CONNECTED
                self.bot_wait_seconds = 0
                logger.info("🎉 Telegram Bot client connected successfully in background!")
                break
            except FloodWaitError as fe:
                wait = fe.seconds
                self.bot_wait_seconds = wait
                logger.warning(f"Bot still under flood wait: {wait}s remaining.")
            except Exception as e:
                logger.warning(f"Background bot connection retry failed: {e}. Will retry in 60s.")
                wait = 60
                self.bot_wait_seconds = 60

    async def connect_all(
        self, bot_manager: BotManager, user_manager: UserClientManager
    ) -> None:
        async with self._lock:
            self.bot_manager = bot_manager
            self.user_manager = user_manager

            logger.info("Initializing Telegram connections...")
            self.bot_state = ConnectionState.CONNECTING
            self.user_state = ConnectionState.CONNECTING

            # Connect Bot Client (Fault-tolerant & decoupled: never kills the webapp)
            try:
                logger.info("Connecting Telegram Bot client...")
                await self.bot_manager.connect()
                self.bot_state = ConnectionState.CONNECTED
                logger.info("Telegram Bot client connected successfully.")
            except FloodWaitError as e:
                self.bot_state = ConnectionState.RECONNECTING
                self.bot_wait_seconds = e.seconds
                logger.warning(
                    f"⚠️ Telegram Bot hit rate-limit flood wait of {e.seconds}s. "
                    f"WebApp & audio streaming remain 100% ONLINE! "
                    f"Scheduling background retry in {e.seconds}s..."
                )
                self._bot_retry_task = asyncio.create_task(
                    self._retry_bot_loop(e.seconds)
                )
            except Exception as e:
                err_str = str(e).lower()
                retry_wait = 5 if ("two different ip addresses" in err_str or "authkeyduplicated" in err_str) else 60
                self.bot_state = ConnectionState.RECONNECTING
                self.bot_wait_seconds = retry_wait
                logger.warning(
                    f"⚠️ Bot authentication issue: {e}. "
                    f"WebApp & audio streaming remain 100% ONLINE! "
                    f"Scheduling background retry in {retry_wait}s..."
                )
                self._bot_retry_task = asyncio.create_task(
                    self._retry_bot_loop(retry_wait)
                )

            # Connect User MTProto Client (Required for Music Channel Indexing & Streaming)
            try:
                logger.info("Connecting Telegram User MTProto client...")
                await self.user_manager.connect()
                self.user_state = ConnectionState.CONNECTED
                self.user_error = None
                logger.info("Telegram User client connected successfully.")
            except Exception as e:
                self.user_state = ConnectionState.AUTH_FAILED
                self.user_error = str(e)
                logger.error(
                    f"⚠️ User MTProto session authentication failed: {e}\n"
                    f"The WebApp & Health Server remain 100% ONLINE (HTTP 200). "
                    f"Please generate a fresh TELEGRAM_SESSION and update it in Render."
                )

    async def disconnect_all(self) -> None:
        async with self._lock:
            logger.info("Disconnecting all Telegram clients...")
            if self._bot_retry_task and not self._bot_retry_task.done():
                self._bot_retry_task.cancel()
                self._bot_retry_task = None

            if self.bot_manager:
                try:
                    await self.bot_manager.disconnect()
                except Exception as e:
                    logger.warning(f"Error disconnecting bot client: {e}")
                self.bot_state = ConnectionState.DISCONNECTED

            if self.user_manager:
                try:
                    await self.user_manager.disconnect()
                except Exception as e:
                    logger.warning(f"Error disconnecting user client: {e}")
                self.user_state = ConnectionState.DISCONNECTED

            logger.info("All Telegram clients disconnected.")
