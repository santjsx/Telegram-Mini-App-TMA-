"""
Hierarchical File Manager & Breadcrumb Explorer for TPMC.
Enables native file-manager style folder drill-down, A-Z alphabet quick jumping,
and seamless breadcrumb navigation (Library > Artist > Album > Tracks).
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Optional
from telethon import Button, events
from telethon.tl.custom.message import Message

from app.index.parser import clean_display_title, get_audio_badge

if TYPE_CHECKING:
    from app.index.indexer import MusicIndexer
    from app.jobs.manager import JobManager
    from app.commands.search import SearchCommandHandler

logger = logging.getLogger(__name__)

ALPHABET = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L",
            "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "#"]


class ExplorerCommandHandler:
    def __init__(
        self,
        indexer: MusicIndexer,
        job_manager: JobManager,
        search_handler: Optional[SearchCommandHandler] = None,
    ) -> None:
        self.indexer = indexer
        self.job_manager = job_manager
        self.search_handler = search_handler

    # ---------------------------------------------------------
    # Root File Manager Screen
    # ---------------------------------------------------------
    def format_root_view(self) -> tuple[str, list[list[Button]]]:
        stats = self.indexer.get_stats()
        lossless = len(self.indexer.get_lossless_tracks())
        favs = stats.get("favorites", 0)
        tracks = stats.get("total_tracks", 0)
        artists = stats.get("total_artists", 0)
        albums = stats.get("total_albums", 0)
        genres = stats.get("total_genres", 0)

        text = (
            "📁 **Music Cloud Explorer**\n"
            "Browse your personal audio drive like a file manager:\n\n"
            f"• 💿 **Albums:** {albums:,} collections\n"
            f"• 🎵 **All Songs:** {tracks:,} audio files\n"
            f"• 🎤 **Artists:** {artists:,} performers\n"
            f"• ⭐ **Favorites:** {favs:,} starred songs\n"
            f"• 💎 **Lossless FLAC:** {lossless:,} tracks\n"
            f"• 🎸 **Genres & Tags:** {genres:,} styles\n\n"
            "💡 *Select a folder below to explore:* "
        )

        buttons = [
            [
                Button.inline("💿 Browse Albums", data=b"exp:alb:1"),
                Button.inline("🎵 All Songs", data=b"s:p:1:all"),
            ],
            [
                Button.inline("🔤 Album A–Z Jump", data=b"exp:az:alb"),
                Button.inline("⭐ Favorites", data=b"s:p:1:favorite"),
            ],
            [
                Button.inline("💎 Lossless FLAC", data=b"exp:lossless"),
                Button.inline("🆕 Recently Added", data=b"exp:recent"),
            ],
            [
                Button.inline("🎸 Genres & Tags", data=b"exp:gnr:1"),
                Button.inline("🎲 Surprise Pick", data=b"lib:random"),
            ],
            [
                Button.inline("📚 Library Dashboard", data=b"lib:overview"),
            ],
        ]
        return text, buttons

    # ---------------------------------------------------------
    # A-Z Alphabet Jump View
    # ---------------------------------------------------------
    def format_az_view(self, target_type: str = "alb") -> tuple[str, list[list[Button]]]:
        title = "Albums" if target_type == "alb" else "Artists"
        text = (
            f"🔤 **A–Z Alphabet Index · {title}**\n\n"
            "Tap any letter below to instantly jump to that section:"
        )

        rows: list[list[Button]] = []
        current_row: list[Button] = []
        for ch in ALPHABET:
            current_row.append(
                Button.inline(ch, data=f"exp:{target_type}:1:{ch}".encode("utf-8"))
            )
            if len(current_row) == 6:
                rows.append(current_row)
                current_row = []
        if current_row:
            rows.append(current_row)

        rows.append([
            Button.inline(f"All {title}", data=f"exp:{target_type}:1".encode("utf-8")),
            Button.inline("🔙 Back to Explorer", data=b"exp:root"),
        ])
        return text, rows

    # ---------------------------------------------------------
    # Artists Explorer View (with optional letter filter)
    # ---------------------------------------------------------
    def format_artists_explorer(
        self, page: int = 1, letter: Optional[str] = None, page_size: int = 8
    ) -> tuple[str, list[list[Button]]]:
        if letter:
            artists = self.indexer.get_artists_by_letter(letter)
            header_prefix = f"🎤 **Artists starting with '{letter.upper()}'**"
        else:
            artists = self.indexer.get_all_artists()
            header_prefix = "🎤 **All Artists in Library**"

        if not artists:
            return (
                f"{header_prefix}\n\nNo artists found in this category.",
                [
                    [Button.inline("🔤 Pick Another Letter", data=b"exp:az:art")],
                    [Button.inline("📁 Root Explorer", data=b"exp:root")],
                ],
            )

        total = len(artists)
        total_pages = max(1, math.ceil(total / page_size))
        current_page = max(1, min(page, total_pages))

        start = (current_page - 1) * page_size
        page_items = artists[start:start + page_size]

        lines = [f"{header_prefix} · Page **{current_page}** of **{total_pages}** ({total} total)\n"]
        buttons: list[list[Button]] = []

        item_buttons: list[Button] = []
        for name, count in page_items:
            track_word = "track" if count == 1 else "tracks"
            lines.append(f"🎤 **{name}**\n    🎵 {count} {track_word}\n")

            # Max 64-byte safe button data: exp:art_view:<name[:35]>
            safe_name = name[:35].strip()
            item_buttons.append(
                Button.inline(f"👤 {name[:16]}", data=f"exp:art_v:{safe_name}".encode("utf-8"))
            )
            if len(item_buttons) == 2:
                buttons.append(item_buttons)
                item_buttons = []

        if item_buttons:
            buttons.append(item_buttons)

        # Nav row
        nav_row: list[Button] = []
        letter_suffix = f":{letter}" if letter else ""
        if current_page > 1:
            nav_row.append(
                Button.inline("◀️ Prev", data=f"exp:art:{current_page - 1}{letter_suffix}".encode("utf-8"))
            )
        nav_row.append(
            Button.inline(f"📄 {current_page} / {total_pages}", data=b"exp:noop")
        )
        if current_page < total_pages:
            nav_row.append(
                Button.inline("Next ▶️", data=f"exp:art:{current_page + 1}{letter_suffix}".encode("utf-8"))
            )
        if nav_row:
            buttons.append(nav_row)

        buttons.append([
            Button.inline("🔤 A–Z Jump", data=b"exp:az:art"),
            Button.inline("📁 Root Explorer", data=b"exp:root"),
        ])
        return "\n".join(lines), buttons

    # ---------------------------------------------------------
    # Artist Subfolder Drilldown (Albums & Tracks)
    # ---------------------------------------------------------
    def format_artist_drilldown(self, artist_name: str) -> tuple[str, list[list[Button]]]:
        albums = self.indexer.get_albums_by_artist(artist_name)
        lines = [
            f"📂 Library > 🎤 **{artist_name}**\n",
        ]

        buttons: list[list[Button]] = []

        if albums:
            lines.append(f"💿 **Discography ({len(albums)} collections):**")
            album_btns: list[Button] = []
            for alb_name, track_count in albums[:8]:
                track_word = "track" if track_count == 1 else "tracks"
                lines.append(f"• **{alb_name}** ({track_count} {track_word})")
                safe_alb = alb_name[:35].strip()
                album_btns.append(
                    Button.inline(f"💿 {alb_name[:16]}", data=f"s:p:1:album:{safe_alb}".encode("utf-8"))
                )
                if len(album_btns) == 2:
                    buttons.append(album_btns)
                    album_btns = []
            if album_btns:
                buttons.append(album_btns)
            lines.append("")
        else:
            lines.append("No organized album folders found for this artist.\n")

        safe_artist = artist_name[:35].strip()
        buttons.append([
            Button.inline(f"🎵 View All Tracks by {artist_name[:14]}", data=f"s:p:1:artist:{safe_artist}".encode("utf-8"))
        ])
        buttons.append([
            Button.inline("⬆️ Up to Artists", data=b"exp:art:1"),
            Button.inline("📁 Root Explorer", data=b"exp:root"),
        ])
        return "\n".join(lines), buttons

    # ---------------------------------------------------------
    # Albums Explorer View (with optional letter filter)
    # ---------------------------------------------------------
    def format_albums_explorer(
        self, page: int = 1, letter: Optional[str] = None, page_size: int = 8
    ) -> tuple[str, list[list[Button]]]:
        if letter:
            albums = self.indexer.get_albums_by_letter(letter)
            header_prefix = f"💿 **Albums starting with '{letter.upper()}'**"
        else:
            albums = self.indexer.get_all_albums()
            header_prefix = "💿 **Albums Directory**"

        if not albums:
            text = (
                f"{header_prefix}\n\n"
                "No albums found matching this filter.\n"
                "Try browsing another letter or check All Albums."
            )
            buttons = [
                [
                    Button.inline("🔤 Album A–Z Jump", data=b"exp:az:alb"),
                    Button.inline("📁 Root Explorer", data=b"exp:root"),
                ]
            ]
            return text, buttons

        total_albums = len(albums)
        total_pages = max(1, math.ceil(total_albums / page_size))
        current_page = max(1, min(page, total_pages))

        start_idx = (current_page - 1) * page_size
        end_idx = start_idx + page_size
        page_albums = albums[start_idx:end_idx]

        lines = [
            f"📂 Library > {header_prefix}",
            f"Page **{current_page}** of **{total_pages}** ({total_albums} collections):\n",
        ]

        buttons: list[list[Button]] = []
        item_buttons: list[Button] = []

        for alb, _artist, count in page_albums:
            track_word = "track" if count == 1 else "tracks"
            lines.append(f"💿 **{alb}** · 🎵 {count} {track_word}")
            safe_name = alb[:35].strip()
            item_buttons.append(
                Button.inline(f"💿 {alb[:16]}", data=f"s:p:1:album:{safe_name}".encode("utf-8"))
            )
            if len(item_buttons) == 2:
                buttons.append(item_buttons)
                item_buttons = []

        if item_buttons:
            buttons.append(item_buttons)

        # Nav row
        nav_row: list[Button] = []
        letter_suffix = f":{letter}" if letter else ""
        if current_page > 1:
            nav_row.append(
                Button.inline("◀️ Prev", data=f"exp:alb:{current_page - 1}{letter_suffix}".encode("utf-8"))
            )
        nav_row.append(
            Button.inline(f"📄 {current_page} / {total_pages}", data=b"exp:noop")
        )
        if current_page < total_pages:
            nav_row.append(
                Button.inline("Next ▶️", data=f"exp:alb:{current_page + 1}{letter_suffix}".encode("utf-8"))
            )
        if nav_row:
            buttons.append(nav_row)

        buttons.append([
            Button.inline("🔤 Album A–Z Jump", data=b"exp:az:alb"),
            Button.inline("📁 Root Explorer", data=b"exp:root"),
        ])
        return "\n".join(lines), buttons

    # ---------------------------------------------------------
    # Lossless FLAC / WAV Folder
    # ---------------------------------------------------------
    def format_lossless_view(self) -> tuple[str, list[list[Button]]]:
        tracks = self.indexer.get_lossless_tracks()
        if not tracks:
            return (
                "💎 **Lossless Audio Collection**\n\n"
                "No FLAC or WAV lossless tracks detected in your library.\n"
                "Upload FLAC or WAV files to browse them here!",
                [[Button.inline("🔙 Back to Explorer", data=b"exp:root")]],
            )

        lines = [
            "💎 **Lossless Audio Collection (FLAC / WAV)**\n"
            f"Found **{len(tracks)}** studio-quality lossless tracks:\n",
        ]
        buttons: list[list[Button]] = []
        track_btns: list[Button] = []

        for i, t in enumerate(tracks[:6], start=1):
            clean_title = clean_display_title(t.title or t.display_title)
            badge = get_audio_badge(t)
            lines.append(f"🎧 **{i:02d}. {clean_title}**\n    👤 *{t.performer}* · 💾 {t.file_size_formatted} · {badge}\n")

            track_btns.append(
                Button.inline(f"📥 {i}. {clean_title[:14]}", data=f"s:one:{t.message_id}".encode("utf-8"))
            )
            if len(track_btns) == 2:
                buttons.append(track_btns)
                track_btns = []

        if track_btns:
            buttons.append(track_btns)

        if len(tracks) > 6:
            buttons.append([
                Button.inline("🔍 Search All Lossless", data=b"s:p:1:flac")
            ])

        buttons.append([
            Button.inline("📁 Root Explorer", data=b"exp:root")
        ])
        return "\n".join(lines), buttons

    # ---------------------------------------------------------
    # Recently Added Tracks
    # ---------------------------------------------------------
    def format_recent_view(self) -> tuple[str, list[list[Button]]]:
        tracks = self.indexer.get_recent_tracks(limit=6)
        if not tracks:
            return (
                "🆕 **Recently Added Tracks**\n\n"
                "No tracks indexed yet. Upload music to get started!",
                [[Button.inline("🔙 Back to Explorer", data=b"exp:root")]],
            )

        lines = [
            "🆕 **Recently Added Tracks**\n"
            "Your freshest additions to the music cloud:\n",
        ]
        buttons: list[list[Button]] = []
        track_btns: list[Button] = []

        for i, t in enumerate(tracks, start=1):
            clean_title = clean_display_title(t.title or t.display_title)
            badge = get_audio_badge(t)
            lines.append(f"🎧 **{i:02d}. {clean_title}**\n    👤 *{t.performer}* · ⏱ {t.duration_formatted} · {badge}\n")

            track_btns.append(
                Button.inline(f"📥 {i}. {clean_title[:14]}", data=f"s:one:{t.message_id}".encode("utf-8"))
            )
            if len(track_btns) == 2:
                buttons.append(track_btns)
                track_btns = []

        if track_btns:
            buttons.append(track_btns)

        buttons.append([
            Button.inline("📁 Root Explorer", data=b"exp:root")
        ])
        return "\n".join(lines), buttons

    # ---------------------------------------------------------
    # Command and Callback Dispatchers
    # ---------------------------------------------------------
    async def handle_explorer(self, message: Message) -> None:
        text, buttons = self.format_root_view()
        await message.reply(text, buttons=buttons)

    async def handle_callback(self, event: events.CallbackQuery.Event) -> None:
        data = event.data.decode("utf-8")
        if not data.startswith("exp:"):
            return

        parts = data.split(":")
        sub = parts[1] if len(parts) > 1 else "root"

        if sub == "noop":
            await event.answer()
            return

        if sub == "root":
            text, buttons = self.format_root_view()
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if sub == "az":
            target = parts[2] if len(parts) > 2 else "art"
            text, buttons = self.format_az_view(target_type=target)
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if sub == "alb":
            page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
            letter = parts[3] if len(parts) > 3 else None
            text, buttons = self.format_albums_explorer(page=page, letter=letter)
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if sub == "art":
            page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
            letter = parts[3] if len(parts) > 3 else None
            text, buttons = self.format_artists_explorer(page=page, letter=letter)
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if sub == "art_v":
            artist_name = ":".join(parts[2:]) if len(parts) > 2 else ""
            text, buttons = self.format_artist_drilldown(artist_name)
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if sub == "lossless":
            text, buttons = self.format_lossless_view()
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if sub == "recent":
            text, buttons = self.format_recent_view()
            await event.edit(text, buttons=buttons)
            await event.answer()
            return
