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
        return {
            "bot": bot_desc,
            "user": self.user_state.value.lower(),
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
                self.bot_state = ConnectionState.RECONNECTING
                self.bot_wait_seconds = 60
                logger.warning(
                    f"⚠️ Bot authentication issue: {e}. "
                    f"WebApp & audio streaming remain 100% ONLINE! "
                    f"Scheduling background retry in 60s..."
                )
                self._bot_retry_task = asyncio.create_task(
                    self._retry_bot_loop(60)
                )

            # Connect User MTProto Client (Required for Music Channel Indexing & Streaming)
            try:
                logger.info("Connecting Telegram User MTProto client...")
                await self.user_manager.connect()
                self.user_state = ConnectionState.CONNECTED
                logger.info("Telegram User client connected successfully.")
            except Exception as e:
                logger.error(f"FATAL: User session authentication failed: {e}")
                self.user_state = ConnectionState.AUTH_FAILED
                raise

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
