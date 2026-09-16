"""
Command router that dispatches incoming owner messages to specific handlers.
"""

from __future__ import annotations

import logging
from telethon import Button, events
from telethon.tl.custom.message import Message

from typing import Optional
from app.commands.start import handle_start, handle_help, handle_player
from app.commands.status import StatusCommandHandler
from app.commands.search import SearchCommandHandler
from app.commands.download import DownloadCommandHandler
from app.commands.admin import AdminCommandHandler
from app.auth.manager import AccessManager

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
    ) -> None:
        self.status_handler = status_handler
        self.search_handler = search_handler
        self.download_handler = download_handler
        self.admin_handler = admin_handler
        self.access_manager = access_manager
        self.webapp_url = webapp_url

    async def route_message(self, message: Message) -> None:
        raw_text = (message.text or "").strip()
        if not raw_text:
            return

        command = raw_text.split()[0].lower()
        # Strip bot username suffix if present, e.g. /start@MyBot -> /start
        if "@" in command:
            command = command.split("@")[0]

        logger.info(f"Routing command or query: '{raw_text[:40]}' from sender={message.sender_id}")

        # 1. Permanent Touch Keyboard Button Mappings
        if raw_text in {"🎵 Web Player", "🎵 Player", "Web Player"}:
            await handle_player(message, self.webapp_url)
            return
        elif raw_text in {"🔍 Search Music", "🔍 Search"}:
            text = (
                "🔍 **Search Your Music Cloud**\n\n"
                "Type any song title, artist, or album directly into chat.\n\n"
                "💡 **Quick Discover:**"
            )
            buttons = [
                [
                    Button.inline("🎲 Surprise Me", data=b"lib:random"),
                    Button.inline("⭐ Favorites", data=b"lib:favs"),
                ],
                [
                    Button.inline("🎤 Top Artists", data=b"lib:artists"),
                    Button.inline("💿 Top Albums", data=b"lib:albums"),
                ],
            ]
            await message.reply(text, buttons=buttons)
            return
        elif raw_text in {"📚 My Library"}:
            await self.status_handler.handle_library(message)
            return
        elif raw_text in {"🎤 Top Artists"}:
            artists = self.status_handler.indexer.get_top_artists(10)
            if not artists:
                await message.reply("🎤 No artists indexed in your library yet.")
            else:
                lines = ["🎤 **Top Artists in Your Library**\n"]
                inline_buttons = []
                for name, count in artists:
                    lines.append(f"• **{name}** ({count} tracks)")
                    display_label = f"👤 {name[:16]}"
                    safe_name = name[:30].strip()
                    inline_buttons.append(
                        Button.inline(display_label, data=f"s:p:1:artist:{safe_name}".encode("utf-8"))
                    )
                lines.append("\n💡 *Tap an artist below to listen:*")
                btn_rows = [inline_buttons[i:i + 2] for i in range(0, len(inline_buttons), 2)]
                btn_rows.append([Button.inline("🔙 Open Library", data=b"lib:overview")])
                await message.reply("\n".join(lines), buttons=btn_rows)
            return
        elif raw_text in {"💿 Albums"}:
            albums = self.status_handler.indexer.get_top_albums(10)
            if not albums:
                await message.reply("💿 No albums indexed in your library yet.")
            else:
                lines = ["💿 **Top Albums in Your Library**\n"]
                inline_buttons = []
                for album, artist, count in albums:
                    lines.append(f"• **{album}** — {artist}")
                    display_label = f"💿 {album[:16]}"
                    safe_album = album[:30].strip()
                    inline_buttons.append(
                        Button.inline(display_label, data=f"s:p:1:album:{safe_album}".encode("utf-8"))
                    )
                lines.append("\n💡 *Tap an album below to listen:*")
                btn_rows = [inline_buttons[i:i + 2] for i in range(0, len(inline_buttons), 2)]
                btn_rows.append([Button.inline("🔙 Open Library", data=b"lib:overview")])
                await message.reply("\n".join(lines), buttons=btn_rows)
            return
        elif raw_text in {"⭐ Favorites"}:
            fav_count = self.status_handler.indexer.get_favorites_count()
            if fav_count == 0:
                await message.reply(
                    "⭐ **Favorites**\n\n"
                    "You don't have any songs marked as favorites yet.\n\n"
                    "💡 *Add `#favorite` to any song caption in your storage channel to pin it here!*",
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
                await message.reply("⚠️ This command is reserved for the bot administrator.")
                return

        # 2. Slash Commands
        if command in {"/start"}:
            await handle_start(message, self.webapp_url)
        elif command in {"/player", "/webapp", "/app"}:
            await handle_player(message, self.webapp_url)
        elif command in {"/help"}:
            await handle_help(message)
        elif command in {"/status"}:
            await self.status_handler.handle_status(message)
        elif command in {"/library"}:
            await self.status_handler.handle_library(message)
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
            await message.reply("❓ Unknown command. Type `/help` to view all available commands.")
        else:
            # 3. Natural Language Search
            # When user sends plain text (e.g. "blinding lights", "coldplay", "#rock"),
            # perform an instant fuzzy search with 1-tap download buttons!
            await self.search_handler.handle_search(message)

    async def route_callback(self, event: events.CallbackQuery.Event) -> None:
        data = event.data.decode("utf-8")
        if data.startswith("s:"):
            await self.search_handler.handle_callback(event)
        elif data.startswith("lib:"):
            await self.status_handler.handle_callback(event)
        elif data.startswith("auth:"):
            await self.admin_handler.handle_auth_callback(event)
        elif data.startswith("req:"):
            await self.admin_handler.handle_request_access_callback(event)
        else:
            await event.answer("Unknown action.", alert=True)
