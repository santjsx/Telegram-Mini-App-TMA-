"""
Command router that dispatches incoming owner messages to specific handlers.
"""

from __future__ import annotations

import logging
from telethon import Button, events
from telethon.tl.custom.message import Message

from typing import Optional, TYPE_CHECKING
from app.commands.start import handle_start, handle_help, handle_player
from app.commands.status import StatusCommandHandler
from app.commands.search import SearchCommandHandler
from app.commands.download import DownloadCommandHandler
from app.commands.admin import AdminCommandHandler
from app.auth.manager import AccessManager

if TYPE_CHECKING:
    from app.commands.explorer import ExplorerCommandHandler

logger = logging.getLogger(__name__)


class CommandRouter:
    def __init__(
        self,
        status_handler: StatusCommandHandler,
        search_handler: SearchCommandHandler,
        download_handler: DownloadCommandHandler,
        admin_handler: AdminCommandHandler,
        access_manager: Optional[AccessManager] = None,
        webapp_url: Optional[str] = None,
        explorer_handler: Optional[ExplorerCommandHandler] = None,
    ) -> None:
        self.status_handler = status_handler
        self.search_handler = search_handler
        self.download_handler = download_handler
        self.admin_handler = admin_handler
        self.access_manager = access_manager
        self.webapp_url = webapp_url
        self.explorer_handler = explorer_handler

    async def route_message(self, message: Message) -> None:
        raw_text = (message.text or "").strip()
        if not raw_text:
            return

        command = raw_text.split()[0].lower()
        # Strip bot username suffix if present, e.g. /start@MyBot -> /start
        if "@" in command:
            command = command.split("@")[0]

        logger.info(f"Routing command or query: '{raw_text[:40]}' from sender={message.sender_id}")

        admin_name = getattr(self.admin_handler.config, "admin_name", "Santhosh Reddy")

        # 1. Permanent Touch Keyboard Button Mappings
        if raw_text in {"🎵 Web Player", "🎵 Player", "Web Player"}:
            await handle_player(message, self.webapp_url, admin_name=admin_name)
            return
        elif raw_text in {"🔍 Search Songs & Albums", "🔍 Search Music", "🔍 Search"}:
            text = (
                "🔎 **Search Your Music Library** 🎵\n\n"
                "Looking for a specific song, artist, or album? You can find it instantly!\n\n"
                "1️⃣ Send any song title or artist directly in this chat.\n"
                "2️⃣ Get instant 1-tap playback and audio files.\n\n"
                "Or explore curated collections using the portals below: 💡"
            )
            buttons = [
                [
                    Button.inline("🎲 Surprise Pick", data=b"lib:random"),
                    Button.inline("⭐ Favorites", data=b"s:p:1:favorite"),
                ],
                [
                    Button.inline("💿 Browse Albums", data=b"lib:albums"),
                    Button.inline("🎵 All Songs", data=b"s:p:1:all"),
                ],
                [
                    Button.inline("📁 File Explorer", data=b"exp:root"),
                ],
            ]
            await message.reply(text, buttons=buttons)
            return
        elif raw_text in {"📁 File Explorer", "📁 Explorer", "📂 Explorer"} or command in {"/explore", "/explorer"}:
            if self.explorer_handler:
                await self.explorer_handler.handle_explorer(message)
            else:
                await self.status_handler.handle_library(message)
            return
        elif raw_text in {"📚 My Library"}:
            await self.status_handler.handle_library(message)
            return
        elif raw_text in {"💿 Browse Albums", "💿 Albums", "💿 Top Albums"} or command in {"/albums"}:
            if not self.status_handler.indexer.get_all_albums():
                await message.reply("💿 No albums indexed in your library yet.")
            else:
                text, buttons = self.status_handler.format_albums_view(page=1, back_label="🔙 Open Library")
                await message.reply(text, buttons=buttons)
            return
        elif raw_text in {"🎵 All Songs", "🎵 Songs"} or command in {"/songs"}:
            message.text = "/search all"
            await self.search_handler.handle_search(message)
            return
        elif raw_text in {"🎲 Surprise Pick", "🎲 Surprise Me"} or command in {"/random"}:
            await self.status_handler.handle_surprise_pick(message)
            return
        elif raw_text in {"🎤 Top Artists", "🎤 Artists"} or command in {"/artists"}:
            if not self.status_handler.indexer.get_all_artists():
                await message.reply("🎤 No artists indexed in your library yet.")
            else:
                text, buttons = self.status_handler.format_artists_view(page=1, back_label="🔙 Open Library")
                await message.reply(text, buttons=buttons)
            return
        elif raw_text in {"🎸 Genres"} or command in {"/genres"}:
            if not self.status_handler.indexer.get_all_genres():
                await message.reply("🎸 No genres indexed in your library yet.")
            else:
                text, buttons = self.status_handler.format_genres_view(page=1, back_label="🔙 Open Library")
                await message.reply(text, buttons=buttons)
            return
        elif raw_text in {"⭐ Favorites"}:
            fav_count = self.status_handler.indexer.get_favorites_count()
            if fav_count == 0:
                await message.reply(
                    "⭐ **Favorite Tracks** 🎧\n\n"
                    "You haven't starred any songs as favorites yet.\n\n"
                    "💡 *Tip: Add `#favorite` to any song caption in your storage channel to pin it here!*",
                    buttons=[[Button.inline("📚 Open Library", data=b"lib:overview")]],
                )
            else:
                message.text = "/search #favorite"
                await self.search_handler.handle_search(message)
            return
        elif raw_text in {"⚡ Cloud Status", "⚡ Status"}:
            await self.status_handler.handle_status(message)
            return

        # Admin-only command gating
        if command in {"/reindex", "/download_all", "/users", "/revoke"}:
            if self.access_manager and not self.access_manager.is_admin(message.sender_id):
                await message.reply(f"⚠️ This command is reserved for the bot administrator ({admin_name}).")
                return

        # 2. Slash Commands
        if command in {"/start"}:
            await handle_start(message, self.webapp_url, admin_name=admin_name)
        elif command in {"/player", "/webapp", "/app"}:
            await handle_player(message, self.webapp_url, admin_name=admin_name)
        elif command in {"/help"}:
            await handle_help(message)
        elif command in {"/status"}:
            await self.status_handler.handle_status(message)
        elif command in {"/library"}:
            await self.status_handler.handle_library(message)
        elif command in {"/albums"}:
            if not self.status_handler.indexer.get_all_albums():
                await message.reply("💿 No albums indexed in your library yet.")
            else:
                text, buttons = self.status_handler.format_albums_view(page=1, back_label="🔙 Open Library")
                await message.reply(text, buttons=buttons)
        elif command in {"/songs"}:
            message.text = "/search all"
            await self.search_handler.handle_search(message)
        elif command.startswith("/album"):
            parts = raw_text.split(maxsplit=1)
            if len(parts) > 1:
                message.text = f"/search album:{parts[1].strip()}"
                await self.search_handler.handle_search(message)
            else:
                text, buttons = self.status_handler.format_albums_view(page=1, back_label="🔙 Open Library")
                await message.reply(text, buttons=buttons)
        elif command.startswith("/song"):
            parts = raw_text.split(maxsplit=1)
            if len(parts) > 1:
                message.text = f"/search {parts[1].strip()}"
                await self.search_handler.handle_search(message)
            else:
                message.text = "/search all"
                await self.search_handler.handle_search(message)
        elif command in {"/random"}:
            await self.status_handler.handle_surprise_pick(message)
        elif command in {"/search"}:
            await self.search_handler.handle_search(message)
        elif command in {"/download"}:
            await self.download_handler.handle_download(message)
        elif command in {"/download_all"}:
            await self.download_handler.handle_download_all(message)
        elif command in {"/cancel"}:
            await self.download_handler.handle_cancel(message)
        elif command in {"/reindex"}:
            await self.admin_handler.handle_reindex(message)
        elif command in {"/users"}:
            await self.admin_handler.handle_users(message)
        elif command in {"/revoke"}:
            await self.admin_handler.handle_revoke(message)
        elif command.startswith("/"):
            await message.reply(
                "❓ **Unknown command.**\n\n"
                "Type `/help` or use the menu below to view all available commands. 💡"
            )
        else:
            # 3. Natural Language Search
            # When user sends plain text (e.g. "blinding lights", "coldplay", "#rock"),
            # perform an instant fuzzy search with 1-tap download buttons!
            await self.search_handler.handle_search(message)

    async def route_callback(self, event: events.CallbackQuery.Event) -> None:
        data = event.data.decode("utf-8")
        if data.startswith("s:"):
            await self.search_handler.handle_callback(event)
        elif data.startswith("exp:"):
            if self.explorer_handler:
                await self.explorer_handler.handle_callback(event)
            else:
                await event.answer("Explorer not available.", alert=True)
        elif data.startswith("lib:"):
            await self.status_handler.handle_callback(event)
        elif data.startswith("auth:"):
            await self.admin_handler.handle_auth_callback(event)
        elif data.startswith("req:"):
            await self.admin_handler.handle_request_access_callback(event)
        else:
            await event.answer("Unknown action.", alert=True)
