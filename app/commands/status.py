"""
Status and Library command handlers.
"""

from __future__ import annotations

import logging
import math
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

    def format_albums_view(
        self,
        page: int = 1,
        page_size: int = 10,
        back_label: str = "🔙 Back to Library",
        back_action: str = "lib:overview",
    ) -> tuple[str, list[list[Button]]]:
        all_albums = self.indexer.get_all_albums()
        if not all_albums:
            return (
                "💿 No albums indexed in your library yet.\n\n"
                "💡 *Ensure your audio tracks have the album tag or `#album:Name` set in captions.*",
                [[Button.inline(back_label, data=back_action.encode("utf-8"))]],
            )

        total_albums = len(all_albums)
        total_pages = max(1, math.ceil(total_albums / page_size))
        current_page = max(1, min(page, total_pages))

        start_idx = (current_page - 1) * page_size
        end_idx = start_idx + page_size
        page_albums = all_albums[start_idx:end_idx]

        if total_pages > 1:
            lines = [f"💿 **Albums in Your Library** · Page **{current_page}** of **{total_pages}** ({total_albums} total)\n"]
        else:
            lines = [f"💿 **Albums in Your Library** ({total_albums} total)\n"]

        inline_buttons = []
        for album, artist, count in page_albums:
            lines.append(f"• **{album}** — {artist}")
            display_label = f"💿 {album[:16]}"
            prefix = "s:p:1:album:"
            max_bytes = 64 - len(prefix.encode("utf-8"))
            safe_album = album.strip().encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore").strip()
            inline_buttons.append(
                Button.inline(display_label, data=f"{prefix}{safe_album}".encode("utf-8"))
            )

        lines.append("\n💡 *Tap an album below to listen:*")
        btn_rows = [inline_buttons[i:i + 2] for i in range(0, len(inline_buttons), 2)]

        if total_pages > 1:
            nav_row = []
            if current_page > 1:
                nav_row.append(
                    Button.inline("⬅️ Prev", data=f"lib:albums:{current_page - 1}".encode("utf-8"))
                )
            nav_row.append(
                Button.inline(f"{current_page} / {total_pages}", data=b"lib:noop")
            )
            if current_page < total_pages:
                nav_row.append(
                    Button.inline("➡️ Next", data=f"lib:albums:{current_page + 1}".encode("utf-8"))
                )
            btn_rows.append(nav_row)

        btn_rows.append([Button.inline(back_label, data=back_action.encode("utf-8"))])
        return "\n".join(lines), btn_rows

    def format_artists_view(
        self,
        page: int = 1,
        page_size: int = 10,
        back_label: str = "🔙 Back to Library",
        back_action: str = "lib:overview",
    ) -> tuple[str, list[list[Button]]]:
        all_artists = self.indexer.get_all_artists()
        if not all_artists:
            return (
                "🎤 No artists indexed in your library yet.\n\n"
                "💡 *Ensure your audio tracks have the artist tag or `#artist:Name` set in captions.*",
                [[Button.inline(back_label, data=back_action.encode("utf-8"))]],
            )

        total_artists = len(all_artists)
        total_pages = max(1, math.ceil(total_artists / page_size))
        current_page = max(1, min(page, total_pages))

        start_idx = (current_page - 1) * page_size
        end_idx = start_idx + page_size
        page_artists = all_artists[start_idx:end_idx]

        if total_pages > 1:
            lines = [f"🎤 **Top Artists in Your Library** · Page **{current_page}** of **{total_pages}** ({total_artists} total)\n"]
        else:
            lines = [f"🎤 **Top Artists in Your Library** ({total_artists} total)\n"]

        inline_buttons = []
        for name, count in page_artists:
            lines.append(f"• **{name}** ({count} tracks)")
            display_label = f"👤 {name[:16]}"
            prefix = "s:p:1:artist:"
            max_bytes = 64 - len(prefix.encode("utf-8"))
            safe_name = name.strip().encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore").strip()
            inline_buttons.append(
                Button.inline(display_label, data=f"{prefix}{safe_name}".encode("utf-8"))
            )

        lines.append("\n💡 *Tap an artist below to listen:*")
        btn_rows = [inline_buttons[i:i + 2] for i in range(0, len(inline_buttons), 2)]

        if total_pages > 1:
            nav_row = []
            if current_page > 1:
                nav_row.append(
                    Button.inline("⬅️ Prev", data=f"lib:artists:{current_page - 1}".encode("utf-8"))
                )
            nav_row.append(
                Button.inline(f"{current_page} / {total_pages}", data=b"lib:noop")
            )
            if current_page < total_pages:
                nav_row.append(
                    Button.inline("➡️ Next", data=f"lib:artists:{current_page + 1}".encode("utf-8"))
                )
            btn_rows.append(nav_row)

        btn_rows.append([Button.inline(back_label, data=back_action.encode("utf-8"))])
        return "\n".join(lines), btn_rows

    def format_genres_view(
        self,
        page: int = 1,
        page_size: int = 10,
        back_label: str = "🔙 Back to Library",
        back_action: str = "lib:overview",
    ) -> tuple[str, list[list[Button]]]:
        all_genres = self.indexer.get_all_genres()
        if not all_genres:
            return (
                "🎸 No genres indexed in your library yet.\n\n"
                "💡 *Ensure your audio tracks have the genre tag or `#genre:Name` set in captions.*",
                [[Button.inline(back_label, data=back_action.encode("utf-8"))]],
            )

        total_genres = len(all_genres)
        total_pages = max(1, math.ceil(total_genres / page_size))
        current_page = max(1, min(page, total_pages))

        start_idx = (current_page - 1) * page_size
        end_idx = start_idx + page_size
        page_genres = all_genres[start_idx:end_idx]

        if total_pages > 1:
            lines = [f"🎸 **Genres in Your Library** · Page **{current_page}** of **{total_pages}** ({total_genres} total)\n"]
        else:
            lines = [f"🎸 **Genres in Your Library** ({total_genres} total)\n"]

        inline_buttons = []
        for genre, count in page_genres:
            lines.append(f"• **{genre}** ({count} tracks)")
            display_label = f"🎸 #{genre[:16]}"
            prefix = "s:p:1:#"
            max_bytes = 64 - len(prefix.encode("utf-8"))
            safe_genre = genre.strip().encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore").strip()
            inline_buttons.append(
                Button.inline(display_label, data=f"{prefix}{safe_genre}".encode("utf-8"))
            )

        lines.append("\n💡 *Tap a genre below to listen:*")
        btn_rows = [inline_buttons[i:i + 2] for i in range(0, len(inline_buttons), 2)]

        if total_pages > 1:
            nav_row = []
            if current_page > 1:
                nav_row.append(
                    Button.inline("⬅️ Prev", data=f"lib:genres:{current_page - 1}".encode("utf-8"))
                )
            nav_row.append(
                Button.inline(f"{current_page} / {total_pages}", data=b"lib:noop")
            )
            if current_page < total_pages:
                nav_row.append(
                    Button.inline("➡️ Next", data=f"lib:genres:{current_page + 1}".encode("utf-8"))
                )
            btn_rows.append(nav_row)

        btn_rows.append([Button.inline(back_label, data=back_action.encode("utf-8"))])
        return "\n".join(lines), btn_rows

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
            performer = track.performer or 'Unknown Artist'
            album_str = f"💿 *{track.album}* · " if track.album else ""
            meta_str = f"({track.duration_formatted} · {track.file_size_formatted})"
            text = (
                f"🎲 **Surprise Track Pick:**\n\n"
                f"**{track.title}** — *{performer}*\n"
                f"{album_str}{meta_str}"
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

        if action == "noop":
            await event.answer()
            return

        if action == "artists" or action.startswith("artists:"):
            if not self.indexer.get_all_artists():
                await event.answer("No artists indexed yet.", alert=True)
                return

            page = 1
            if ":" in action:
                try:
                    page = int(action.split(":", 1)[1])
                except (ValueError, IndexError):
                    page = 1

            text, buttons = self.format_artists_view(page=page)
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if action == "albums" or action.startswith("albums:"):
            if not self.indexer.get_all_albums():
                await event.answer("No albums indexed yet.", alert=True)
                return

            page = 1
            if ":" in action:
                try:
                    page = int(action.split(":", 1)[1])
                except (ValueError, IndexError):
                    page = 1

            text, buttons = self.format_albums_view(page=page)
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if action == "genres" or action.startswith("genres:"):
            if not self.indexer.get_all_genres():
                await event.answer("No genres indexed yet.", alert=True)
                return

            page = 1
            if ":" in action:
                try:
                    page = int(action.split(":", 1)[1])
                except (ValueError, IndexError):
                    page = 1

            text, buttons = self.format_genres_view(page=page)
            await event.edit(text, buttons=buttons)
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
