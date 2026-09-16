"""
Media delivery pipeline for TPMC.
Executes Mode A (server-side media forwarding) to deliver audio tracks to the owner's DM
without downloading or re-uploading media files to Render.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional
from app.index.models import Track
from app.jobs.retry import retry_telegram_operation

if TYPE_CHECKING:
    from app.telegram.user_client import UserClientManager
    from app.telegram.bot import BotManager

logger = logging.getLogger(__name__)

# Conservative delay between individual message forwards to prevent rate limits
PACING_DELAY_SECONDS = 1.2


class DeliveryEngine:
    def __init__(
        self,
        user_client: UserClientManager,
        bot_manager: Optional[BotManager] = None,
        flood_wait_max: int = 300,
    ) -> None:
        self.user_client = user_client
        self.bot_manager = bot_manager
        self.flood_wait_max = flood_wait_max

    async def deliver_track(self, owner_id: int, track: Track) -> bool:
        """
        Deliver a single track using Mode A forwarding.
        Prioritizes forwarding via BotManager so that audio is forwarded from the
        music channel directly into the user's active DM with the bot (enabling
        in-app listening/streaming and offline saving inside the chat window).
        Falls back to the user client if bot forwarding is unavailable or fails.
        Returns True if successful, False if failed.
        """
        logger.info(
            f"Delivering track: '{track.display_title}' (message_id={track.message_id}) to owner={owner_id}"
        )

        async def _forward() -> None:
            if self.bot_manager:
                try:
                    await self.bot_manager.forward_media(
                        to_peer=owner_id,
                        from_peer=track.channel_id,
                        message_ids=[track.message_id],
                    )
                    return
                except Exception as e:
                    logger.warning(
                        f"Bot forward failed for message_id={track.message_id} ({e}); falling back to user client forward"
                    )

            await self.user_client.forward_media(
                to_peer=owner_id,
                message_ids=[track.message_id],
            )

        try:
            await retry_telegram_operation(
                _forward,
                max_retries=3,
                flood_wait_max=self.flood_wait_max,
            )
            # Pacing delay between tracks
            await asyncio.sleep(PACING_DELAY_SECONDS)
            return True
        except Exception as e:
            logger.error(
                f"Failed to deliver track '{track.display_title}' (id={track.message_id}): {e}"
            )
            return False
