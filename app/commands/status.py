"""
Status and Library command handlers.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING
from telethon import Button, events
from telethon.tl.custom.message import Message

if TYPE_CHECKING:
    from app.index.indexer import MusicIndexer
    from app.telegram.connection import TelegramConnectionManager
    from app.jobs.manager import JobManager

logger = logging.getLogger(__name__)


class StatusCommandHandler:
    def __init__(
        self,
        connection_manager: TelegramConnectionManager,
        indexer: MusicIndexer,
        job_manager: JobManager,
    ) -> None:
        self.connection_manager = connection_manager
        self.indexer = indexer
        self.job_manager = job_manager

    def _get_library_buttons(self) -> list[list[Button]]:
        return [
            [
                Button.inline("🎤 Top Artists", data=b"lib:artists"),
                Button.inline("💿 Albums", data=b"lib:albums"),
            ],
            [
                Button.inline("🎸 Genres", data=b"lib:genres"),
                Button.inline("⭐ Favorites", data=b"lib:favs"),
            ],
            [
                Button.inline("🎲 Surprise Me", data=b"lib:random"),
                Button.inline("⚡ Cloud Status", data=b"lib:status"),
            ],
        ]

    def _format_library_overview(self) -> str:
        stats = self.indexer.get_stats()
        index_state = stats.get("state", "UNKNOWN").upper()

        return (
            "📚 **Music Library Overview**\n\n"
            f"• 🎵 **Tracks:** {stats.get('total_tracks', 0):,} songs\n"
            f"• 🎤 **Artists:** {stats.get('total_artists', 0):,} performers\n"
            f"• 💿 **Albums:** {stats.get('total_albums', 0):,} collections\n"
            f"• ⭐ **Favorites:** {stats.get('favorites', 0):,} tracks\n\n"
            f"🟢 **Cloud Status:** Online (`{index_state}`)\n"
            "💡 *Tap any category below to browse your collection.*"
        )

    def _format_status_text(self) -> str:
        conn_summary = self.connection_manager.get_status_summary()
        tg_status = "Connected" if self.connection_manager.is_connected else "Connecting/Degraded"
        bot_status = "Online" if conn_summary.get("bot") == "connected" else "Offline"

        index_stats = self.indexer.get_stats()
        index_state = index_stats.get("state", "UNKNOWN").upper()
        if index_state == "INDEXING":
            indexed = index_stats.get("tracks_indexed", 0)
            scanned = index_stats.get("messages_scanned", 0)
            index_display = f"Indexing ({indexed} tracks / {scanned} scanned)"
        else:
            index_display = index_state

        active_job = self.job_manager.get_active_job()
        if active_job:
            job_display = f"Running: {active_job.query} ({active_job.completed}/{active_job.total})"
        else:
            job_display = "None"

        # Determine runtime host environment
        is_render = bool(os.getenv("RENDER"))
        host_display = "Render Cloud" if is_render else "Local Server"

        return (
            "📊 **TPMC Status**\n\n"
            f"• **Telegram:** {tg_status}\n"
            f"• **Bot:** {bot_status}\n"
            f"• **Index:** {index_display}\n"
            f"• **Tracks:** {index_stats.get('total_tracks', 0):,}\n"
            f"• **Active Job:** {job_display}\n"
            f"• **Host:** {host_display} (Online)"
        )

    async def handle_status(self, message: Message) -> None:
        text = self._format_status_text()
        buttons = [
            [
                Button.inline("📚 Open Library", data=b"lib:overview"),
            ]
        ]
        await message.reply(text, buttons=buttons)

    async def handle_library(self, message: Message) -> None:
        text = self._format_library_overview()
        buttons = self._get_library_buttons()
        await message.reply(text, buttons=buttons)

    async def handle_callback(self, event: events.CallbackQuery.Event) -> None:
        data = event.data.decode("utf-8")
        if not data.startswith("lib:"):
            return

        action = data.split(":", 1)[1]

        if action == "overview":
            text = self._format_library_overview()
            buttons = self._get_library_buttons()
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if action == "status":
            text = self._format_status_text()
            buttons = [[Button.inline("🔙 Back to Library", data=b"lib:overview")]]
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if action == "random":
            track = self.indexer.get_random_track()
            if not track:
                await event.answer("No tracks in library yet.", alert=True)
                return
            await event.answer(f"🎲 Picked: {track.display_title[:25]}!")
            text = (
                f"🎲 **Surprise Track Pick:**\n\n"
                f"**{track.title}**\n"
                f"└ 👤 {track.performer or 'Unknown Artist'} • 💿 {track.album or 'Single'}\n"
                f"└ ⏱ `{track.duration_formatted}` • 💾 `{track.file_size_formatted}`"
            )
            buttons = [
                [
                    Button.inline(
                        f"📥 Send Audio ({track.file_size_formatted})",
                        data=f"s:one:{track.message_id}".encode("utf-8"),
                    )
                ],
                [
                    Button.inline("🎲 Pick Another", data=b"lib:random"),
                    Button.inline("🔙 Back to Library", data=b"lib:overview"),
                ],
            ]
            await event.edit(text, buttons=buttons)
            return

        if action == "artists":
            artists = self.indexer.get_top_artists(10)
            if not artists:
                await event.answer("No artists indexed yet.", alert=True)
                return

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
            btn_rows.append([Button.inline("🔙 Back to Library", data=b"lib:overview")])

            await event.edit("\n".join(lines), buttons=btn_rows)
            await event.answer()
            return

        if action == "albums":
            albums = self.indexer.get_top_albums(10)
            if not albums:
                await event.answer("No albums indexed yet.", alert=True)
                return

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
            btn_rows.append([Button.inline("🔙 Back to Library", data=b"lib:overview")])

            await event.edit("\n".join(lines), buttons=btn_rows)
            await event.answer()
            return

        if action == "genres":
            genres = self.indexer.get_top_genres(10)
            if not genres:
                await event.answer("No genres indexed yet.", alert=True)
                return

            lines = ["🎸 **Genres in Your Library**\n"]
            inline_buttons = []
            for genre, count in genres:
                lines.append(f"• **{genre}** ({count} tracks)")
                display_label = f"🎸 #{genre[:16]}"
                safe_genre = genre[:20].strip()
                inline_buttons.append(
                    Button.inline(display_label, data=f"s:p:1:#{safe_genre}".encode("utf-8"))
                )

            lines.append("\n💡 *Tap a genre below to listen:*")
            btn_rows = [inline_buttons[i:i + 2] for i in range(0, len(inline_buttons), 2)]
            btn_rows.append([Button.inline("🔙 Back to Library", data=b"lib:overview")])

            await event.edit("\n".join(lines), buttons=btn_rows)
            await event.answer()
            return

        if action == "favs":
            fav_count = self.indexer.get_favorites_count()
            if fav_count == 0:
                lines = [
                    "⭐ **Your Favorites**\n",
                    "You don't have any songs marked as favorites yet.\n",
                    "💡 *Add `#favorite` to any song caption in your storage channel to pin it here!*",
                ]
                buttons = [
                    [Button.inline("🔙 Back to Library", data=b"lib:overview")],
                ]
            else:
                lines = [
                    "⭐ **Your Favorites**\n",
                    f"You have **{fav_count}** favorite song(s) pinned in your cloud.",
                ]
                buttons = [
                    [Button.inline(f"🎧 View All Favorites ({fav_count})", data=b"s:p:1:favorite")],
                    [Button.inline("🔙 Back to Library", data=b"lib:overview")],
                ]
            await event.edit("\n".join(lines), buttons=buttons)
            await event.answer()
            return
