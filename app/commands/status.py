"""
Status and Library command handlers.
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
from telethon import Button, events
from telethon.tl.custom.message import Message

from app.index.parser import clean_display_title, get_audio_badge
from app.index.artwork import ArtworkManager
from app.telegram.artwork import send_or_edit_artwork

if TYPE_CHECKING:
    from app.index.indexer import MusicIndexer
    from app.index.models import Track
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
                Button.inline("💿 Browse Albums", data=b"lib:albums"),
                Button.inline("🎵 All Songs", data=b"s:p:1:all"),
            ],
            [
                Button.inline("📁 File Explorer", data=b"exp:root"),
                Button.inline("🔤 Album A–Z Jump", data=b"exp:az:alb"),
            ],
            [
                Button.inline("⭐ Favorites", data=b"s:p:1:favorite"),
                Button.inline("💎 Lossless FLAC", data=b"exp:lossless"),
            ],
            [
                Button.inline("🎲 Surprise Pick", data=b"lib:random"),
                Button.inline("🆕 Recent Tracks", data=b"exp:recent"),
            ],
            [
                Button.inline("⚡ Cloud Status", data=b"lib:status"),
            ],
        ]

    def _format_library_overview(self) -> str:
        stats = self.indexer.get_stats()
        index_state = stats.get("state", "UNKNOWN").upper()
        lossless = len(self.indexer.get_lossless_tracks())

        return (
            "📚 **Music Library Overview**\n\n"
            f"• 💿 **Albums:** {stats.get('total_albums', 0):,} collections\n"
            f"• 🎵 **Total Songs:** {stats.get('total_tracks', 0):,} tracks\n"
            f"• ⭐ **Favorites:** {stats.get('favorites', 0):,} starred tracks\n"
            f"• 💎 **Lossless FLAC:** {lossless:,} audio files\n\n"
            f"🟢 **Cloud Status:** Online (`{index_state}`)\n"
            "💡 *Select an option below to browse your albums or songs.*"
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
        for album, _artist, count in page_albums:
            track_word = "track" if count == 1 else "tracks"
            lines.append(f"💿 **{album}** · 🎵 {count} {track_word}\n")
            display_label = f"💿 {album[:16]}"
            prefix = "s:p:1:album:"
            max_bytes = 64 - len(prefix.encode("utf-8"))
            safe_album = album.strip().encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore").strip()
            inline_buttons.append(
                Button.inline(display_label, data=f"{prefix}{safe_album}".encode("utf-8"))
            )

        lines.append("💡 *Tap an album below to view songs:*")
        btn_rows = [inline_buttons[i:i + 2] for i in range(0, len(inline_buttons), 2)]

        if total_pages > 1:
            nav_row = []
            if current_page > 1:
                nav_row.append(
                    Button.inline("◀️ Prev", data=f"lib:albums:{current_page - 1}".encode("utf-8"))
                )
            nav_row.append(
                Button.inline(f"📄 {current_page} / {total_pages}", data=b"lib:noop")
            )
            if current_page < total_pages:
                nav_row.append(
                    Button.inline("Next ▶️", data=f"lib:albums:{current_page + 1}".encode("utf-8"))
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
            track_word = "track" if count == 1 else "tracks"
            lines.append(f"🎤 **{name}**\n    🎵 {count} {track_word} in library\n")
            display_label = f"👤 {name[:16]}"
            prefix = "s:p:1:artist:"
            max_bytes = 64 - len(prefix.encode("utf-8"))
            safe_name = name.strip().encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore").strip()
            inline_buttons.append(
                Button.inline(display_label, data=f"{prefix}{safe_name}".encode("utf-8"))
            )

        lines.append("💡 *Tap an artist below to view songs:*")
        btn_rows = [inline_buttons[i:i + 2] for i in range(0, len(inline_buttons), 2)]

        if total_pages > 1:
            nav_row = []
            if current_page > 1:
                nav_row.append(
                    Button.inline("◀️ Prev", data=f"lib:artists:{current_page - 1}".encode("utf-8"))
                )
            nav_row.append(
                Button.inline(f"📄 {current_page} / {total_pages}", data=b"lib:noop")
            )
            if current_page < total_pages:
                nav_row.append(
                    Button.inline("Next ▶️", data=f"lib:artists:{current_page + 1}".encode("utf-8"))
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
            track_word = "track" if count == 1 else "tracks"
            lines.append(f"🎸 **#{genre}**\n    🎵 {count} {track_word} in library\n")
            display_label = f"🎸 #{genre[:16]}"
            prefix = "s:p:1:#"
            max_bytes = 64 - len(prefix.encode("utf-8"))
            safe_genre = genre.strip().encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore").strip()
            inline_buttons.append(
                Button.inline(display_label, data=f"{prefix}{safe_genre}".encode("utf-8"))
            )

        lines.append("💡 *Tap a genre below to view songs:*")
        btn_rows = [inline_buttons[i:i + 2] for i in range(0, len(inline_buttons), 2)]

        if total_pages > 1:
            nav_row = []
            if current_page > 1:
                nav_row.append(
                    Button.inline("◀️ Prev", data=f"lib:genres:{current_page - 1}".encode("utf-8"))
                )
            nav_row.append(
                Button.inline(f"📄 {current_page} / {total_pages}", data=b"lib:noop")
            )
            if current_page < total_pages:
                nav_row.append(
                    Button.inline("Next ▶️", data=f"lib:genres:{current_page + 1}".encode("utf-8"))
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

    def format_surprise_pick(self, track: Track) -> tuple[str, list[list[Button]], Optional[Path]]:
        clean_title = clean_display_title(track.title or track.display_title)
        album = track.album if track.album and track.album != "Unknown Album" else ""
        quality = get_audio_badge(track)

        lines = [
            "🎲 **Surprise Track Pick:**\n",
            f"🎧 **{clean_title}**",
        ]
        meta_details = []
        if album and album.lower() != clean_title.lower():
            meta_details.append(f"💿 *{album}*")
        if meta_details:
            lines.append(f"   {' · '.join(meta_details)}")

        specs = []
        if track.duration_formatted:
            specs.append(f"⏱ {track.duration_formatted}")
        if track.file_size_formatted:
            specs.append(f"💾 {track.file_size_formatted}")
        specs.append(quality)
        lines.append(f"   {' · '.join(specs)}")

        fav_label = "⭐ Star Favorite" if not track.is_favorite else "⭐ Unstar"
        buttons = [
            [
                Button.inline(
                    f"📥 Send Audio ({track.file_size_formatted})",
                    data=f"s:one:{track.message_id}".encode("utf-8"),
                )
            ],
            [
                Button.inline(fav_label, data=f"s:fav:{track.message_id}:lib:random".encode("utf-8")),
                Button.inline("🎲 Pick Another", data=b"lib:random"),
            ],
            [
                Button.inline("💿 Browse Albums", data=b"lib:albums"),
                Button.inline("🔙 Back to Library", data=b"lib:overview"),
            ],
        ]
        artwork_path = ArtworkManager.resolve_artwork(track, self.indexer)
        return "\n".join(lines), buttons, artwork_path

    async def handle_surprise_pick(self, target: Any) -> None:
        track = self.indexer.get_random_track()
        if not track:
            if hasattr(target, "reply"):
                await target.reply("🎲 No tracks in your library yet! Upload audio first.")
            elif hasattr(target, "answer"):
                await target.answer("No tracks in library yet.", alert=True)
            return

        text, buttons, artwork_path = self.format_surprise_pick(track)
        clean_title = clean_display_title(track.title or track.display_title)
        if isinstance(target, events.CallbackQuery.Event):
            try:
                await target.answer(f"🎲 Picked: {clean_title[:25]}!")
            except Exception:
                pass
        await send_or_edit_artwork(target, text, buttons=buttons, artwork_path=artwork_path)

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
            await self.handle_surprise_pick(event)
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
