"""
Telegram User MTProto client manager.
Provides direct channel access, message scanning, metadata extraction,
and Mode A media forwarding via Telethon StringSession.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator, Optional
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.custom.message import Message

from app.config import Config

logger = logging.getLogger(__name__)


class UserClientManager:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.session = StringSession(config.telegram_session)
        self.client = TelegramClient(
            self.session,
            config.api_id,
            config.api_hash,
            auto_reconnect=True,
            connection_retries=5,
            retry_delay=2,
        )
        self._channel_entity = None

    async def connect(self) -> None:
        """Connect and verify that the user session is authenticated."""
        await self.client.connect()
        if not await self.client.is_user_authorized():
            raise RuntimeError(
                "User session authentication failed. TELEGRAM_SESSION is invalid or expired."
            )
        me = await self.client.get_me()
        logger.info(f"User client authorized as: {me.first_name} (ID: {me.id})")

    async def disconnect(self) -> None:
        """Disconnect the user client."""
        if self.client.is_connected():
            await self.client.disconnect()

    async def validate_channel(self) -> None:
        """
        Validate that the authenticated account has access to the configured storage channel.
        Fails fast if channel is not found or inaccessible.
        """
        channel_id = self.config.channel_id
        logger.info(f"Validating access to storage channel: {channel_id}...")
        try:
            self._channel_entity = await self.client.get_entity(channel_id)
            title = getattr(self._channel_entity, "title", str(channel_id))
            logger.info(f"Storage channel validated successfully: '{title}' ({channel_id})")
        except Exception as e:
            logger.error(
                f"FATAL: Storage channel {channel_id} unavailable or unauthorized: {e}"
            )
            raise RuntimeError(
                f"Cannot access storage channel {channel_id}. "
                f"Verify that CHANNEL_ID is correct and your Telegram account has joined it. Error: {e}"
            ) from e

    async def iter_channel_messages(
        self, min_id: int = 0, limit: Optional[int] = None
    ) -> AsyncIterator[Message]:
        """
        Stream messages from the storage channel in forward order without loading them all into memory.
        """
        if not self._channel_entity:
            await self.validate_channel()

        # iter_messages with reverse=True traverses from oldest (or min_id) forward
        async for message in self.client.iter_messages(
            self._channel_entity,
            min_id=min_id,
            reverse=True,
            limit=limit,
        ):
            yield message

    async def get_message(self, message_id: int) -> Optional[Message]:
        """Fetch a specific message by its ID."""
        if not self._channel_entity:
            await self.validate_channel()

        return await self.client.get_messages(self._channel_entity, ids=message_id)

    async def forward_media(self, to_peer: int, message_ids: list[int]) -> list[Message]:
        """
        Forward messages directly from the storage channel to the target peer (Mode A).
        """
        if not self._channel_entity:
            await self.validate_channel()

        return await self.client.forward_messages(
            entity=to_peer,
            messages=message_ids,
            from_peer=self._channel_entity,
        )
