"""
Centralized Telegram connection manager and state machine.
Coordinates both the Bot client and User MTProto client.
"""

from __future__ import annotations

import asyncio
import enum
import logging
from typing import Optional, TYPE_CHECKING

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

        self.bot_manager: Optional[BotManager] = None
        self.user_manager: Optional[UserClientManager] = None
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return (
            self.bot_state == ConnectionState.CONNECTED
            and self.user_state == ConnectionState.CONNECTED
        )

    def get_status_summary(self) -> dict[str, str]:
        return {
            "bot": self.bot_state.value.lower(),
            "user": self.user_state.value.lower(),
            "overall": "connected" if self.is_connected else "degraded",
        }

    async def connect_all(
        self, bot_manager: BotManager, user_manager: UserClientManager
    ) -> None:
        async with self._lock:
            self.bot_manager = bot_manager
            self.user_manager = user_manager

            logger.info("Initializing Telegram connections...")
            self.bot_state = ConnectionState.CONNECTING
            self.user_state = ConnectionState.CONNECTING

            # Connect Bot Client
            try:
                logger.info("Connecting Telegram Bot client...")
                await self.bot_manager.connect()
                self.bot_state = ConnectionState.CONNECTED
                logger.info("Telegram Bot client connected successfully.")
            except Exception as e:
                logger.error(f"FATAL: Bot authentication failed: {e}")
                self.bot_state = ConnectionState.AUTH_FAILED
                raise

            # Connect User MTProto Client
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
