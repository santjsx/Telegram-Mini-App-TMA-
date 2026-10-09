"""
Download and bulk delivery command handlers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from telethon.tl.custom.message import Message

from app.index.search import SearchEngine

if TYPE_CHECKING:
    from app.index.indexer import MusicIndexer
    from app.jobs.manager import JobManager
    from app.telegram.bot import BotManager

logger = logging.getLogger(__name__)


class DownloadCommandHandler:
    def __init__(
        self,
        indexer: MusicIndexer,
        job_manager: JobManager,
        bot_manager: BotManager,
    ) -> None:
        self.indexer = indexer
        self.job_manager = job_manager
        self.bot_manager = bot_manager

    async def handle_download(self, message: Message) -> None:
        text = message.text.strip()
        parts = text.split(maxsplit=1)
        query = parts[1].strip() if len(parts) > 1 else ""

        if not query:
            await message.reply(
                "📥 **Batch Audio Delivery** ⚡\n\n"
                "Deliver multiple tracks or entire playlists directly to this chat!\n\n"
                "**Examples:**\n"
                "- `/download rock` — Deliver all matching songs\n"
                "- `/download #artist:linkin_park` — Deliver artist discography\n"
                "- `/download #favorite` — Deliver all starred favorites\n\n"
                "💡 *Use* `/search <query>` *to preview tracks before downloading.*"
            )
            return

        all_tracks = self.indexer.get_all_tracks()
        # Search up to max collection matches
        result = SearchEngine.search(query, all_tracks, page=1, page_size=10000)

        if result.total_count == 0:
            await message.reply(
                f"🔍 **No Matching Tracks Found**\n\n"
                f"No tracks found matching `{query}` to deliver.\n\n"
                "💡 *Use* `/search <query>` *to preview or check* `/library`."
            )
            return

        success, response_text = await self.job_manager.start_delivery_job(
            owner_id=message.sender_id,
            query=query,
            tracks=result.tracks,
            bot_manager=self.bot_manager,
        )
        await message.reply(response_text)

    async def handle_download_all(self, message: Message) -> None:
        text = message.text.strip()
        parts = text.split()
        is_confirmed = len(parts) > 1 and parts[1].lower() == "confirm"

        all_tracks = self.indexer.get_all_tracks()
        count = len(all_tracks)

        if not is_confirmed:
            await message.reply(
                "⚠️ **Bulk Download Confirmation Required** 📥\n\n"
                f"Your library currently contains **{count:,}** tracks.\n"
                f"This operation will deliver **{count:,}** audio files directly to this chat.\n\n"
                "To confirm and begin, send:\n"
                "`/download_all confirm` ⚡"
            )
            return

        if count == 0:
            await message.reply("Your library is currently empty. Upload tracks to your channel first.")
            return

        success, response_text = await self.job_manager.start_delivery_job(
            owner_id=message.sender_id,
            query="Complete Library",
            tracks=all_tracks,
            bot_manager=self.bot_manager,
        )
        await message.reply(response_text)

    async def handle_cancel(self, message: Message) -> None:
        success, response_text = await self.job_manager.cancel_active_job()
        await message.reply(response_text)
