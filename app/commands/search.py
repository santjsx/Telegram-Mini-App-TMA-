"""
Search command and pagination handler.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from telethon import Button, events
from telethon.tl.custom.message import Message

from app.index.search import SearchEngine
from app.index.parser import clean_display_title, get_audio_badge

if TYPE_CHECKING:
    from app.index.indexer import MusicIndexer
    from app.jobs.manager import JobManager

logger = logging.getLogger(__name__)

PAGE_SIZE = 6


class SearchCommandHandler:
    def __init__(self, indexer: MusicIndexer, job_manager: JobManager) -> None:
        self.indexer = indexer
        self.job_manager = job_manager

    async def handle_search(self, message: Message) -> None:
        text = message.text.strip()
        if text.startswith("/search"):
            parts = text.split(maxsplit=1)
            query = parts[1].strip() if len(parts) > 1 else ""
        else:
            query = text

        if not query:
            await message.reply(
                "🔍 **TPMC Search**\n\n"
                "Please specify a search term or tag.\n"
                "Examples:\n"
                "• `/search rock`\n"
                "• `/search artist:theweeknd`\n"
                "• `/search #favorite`"
            )
            return

        all_tracks = self.indexer.get_all_tracks()
        result = SearchEngine.search(query, all_tracks, page=1, page_size=PAGE_SIZE)

        if result.total_count == 0:
            await message.reply(
                f"🔍 No tracks found matching: `{query}`\n\n"
                "Try a broader keyword or check `/library`."
            )
            return

        msg_text, buttons = self._format_page(result)
        await message.reply(msg_text, buttons=buttons)

    async def handle_callback(self, event: events.CallbackQuery.Event) -> None:
        data = event.data.decode("utf-8")
        if not data.startswith("s:"):
            return

        if data in {"s:noop", "s:p:noop"}:
            await event.answer()
            return

        parts = data.split(":", 3)
        if len(parts) < 3:
            await event.answer("Invalid request.", alert=True)
            return

        action = parts[1]

        # 1-Tap Single Track Delivery
        if action == "one":
            msg_id = int(parts[2])
            track = self.indexer.get_track(msg_id)
            if not track:
                await event.answer("Track not found in index.", alert=True)
                return
            await event.answer(f"Sending: {track.display_title[:30]}...")
            success = await self.job_manager.delivery_engine.deliver_track(
                event.sender_id, track
            )
            if not success:
                await event.respond(f"❌ Could not deliver **{track.display_title}**.")
            return

        # Format for dl and p: s:<action>:<page>:<query>
        if len(parts) < 4:
            await event.answer("Invalid request.", alert=True)
            return

        page_str, query = parts[2], parts[3]
        page = int(page_str)

        all_tracks = self.indexer.get_all_tracks()
        result = SearchEngine.search(query, all_tracks, page=page, page_size=PAGE_SIZE)

        if action == "dl":
            # User clicked 'Download Page'
            await event.answer("Starting download of current page...")
            await self.job_manager.start_delivery_job(
                owner_id=event.sender_id,
                query=f"Page {page} of '{query}'",
                tracks=result.tracks,
            )
            return

        # Pagination update
        msg_text, buttons = self._format_page(result)
        try:
            await event.edit(msg_text, buttons=buttons)
            await event.answer()
        except Exception as e:
            logger.debug(f"Search pagination edit skipped: {e}")
            await event.answer()

    def _format_page(self, result) -> tuple[str, list[list[Button]]]:
        query_str = (result.query or "").strip()
        q_lower = query_str.lower()
        if q_lower.startswith("album:"):
            album_name = query_str[6:].strip()
            header = f"💿 **Album: {album_name}**"
        elif q_lower.startswith("artist:"):
            artist_name = query_str[7:].strip()
            header = f"🎤 **Artist: {artist_name}**"
        elif q_lower.startswith("genre:") or query_str.startswith("#"):
            tag_name = query_str.split(":", 1)[-1].lstrip("#").strip()
            header = f"🎸 **Genre: #{tag_name}**"
        elif q_lower in ("favorite", "#favorite"):
            header = "⭐ **Favorite Tracks**"
        else:
            header = f"🔍 **Search Results for:** `{query_str}`"

        # If only 1 track matched, show a direct high-visibility download card
        if result.total_count == 1:
            only_track = result.tracks[0]
            fav = " ⭐" if only_track.is_favorite else ""
            clean_title = clean_display_title(only_track.title or only_track.display_title)
            quality = get_audio_badge(only_track)

            lines = [
                f"{header}\nFound **1** track in your library:\n",
                f"🎧 **{clean_title}**{fav}",
            ]
            if only_track.performer and only_track.performer != "Unknown Artist":
                lines.append(f"   👤 *{only_track.performer}*")
            if only_track.album and only_track.album != "Unknown Album":
                lines.append(f"   💿 *{only_track.album}*")

            specs = []
            if only_track.duration_formatted:
                specs.append(f"⏱ {only_track.duration_formatted}")
            if only_track.file_size_formatted:
                specs.append(f"💾 {only_track.file_size_formatted}")
            specs.append(quality)
            lines.append(f"   {' · '.join(specs)}\n")

            buttons = [
                [
                    Button.inline(
                        f"📥 Send Audio ({only_track.file_size_formatted})",
                        data=f"s:one:{only_track.message_id}".encode("utf-8"),
                    )
                ],
                [
                    Button.inline("📚 Back to Library", data=b"lib:overview")
                ],
            ]
            return "\n".join(lines), buttons

        # Multi-track layout
        lines = [
            header,
            f"Found **{result.total_count}** tracks · Page **{result.page}** of **{result.total_pages}**\n",
        ]

        start_num = (result.page - 1) * result.page_size + 1
        track_buttons: list[Button] = []
        track_rows: list[list[Button]] = []

        for i, t in enumerate(result.tracks, start=start_num):
            fav = " ⭐" if t.is_favorite else ""
            raw_title = t.title or t.display_title
            clean_title = clean_display_title(raw_title)
            performer = t.performer if t.performer and t.performer != "Unknown Artist" else ""
            album = t.album if t.album and t.album != "Unknown Album" else ""
            quality = get_audio_badge(t)

            num_str = f"{i:02d}" if result.total_count >= 10 else f"{i}"
            item_lines = [f"🎧 **{num_str}. {clean_title}**{fav}"]

            meta_details = []
            if performer:
                meta_details.append(f"👤 *{performer}*")
            if album and album.lower() != clean_title.lower():
                meta_details.append(f"💿 *{album}*")
            if meta_details:
                item_lines.append(f"    {' · '.join(meta_details)}")

            specs = []
            if t.duration_formatted:
                specs.append(f"⏱ {t.duration_formatted}")
            if t.file_size_formatted:
                specs.append(f"💾 {t.file_size_formatted}")
            specs.append(quality)
            item_lines.append(f"    {' · '.join(specs)}")

            lines.append("\n".join(item_lines) + "\n")

            # 2 buttons per row, showing number and clean title preview
            short_btn_title = clean_title[:14].strip()
            track_buttons.append(
                Button.inline(f"📥 {i}. {short_btn_title}", data=f"s:one:{t.message_id}".encode("utf-8"))
            )
            if len(track_buttons) == 2:
                track_rows.append(track_buttons)
                track_buttons = []

        if track_buttons:
            track_rows.append(track_buttons)

        buttons: list[list[Button]] = []
        buttons.extend(track_rows)

        # Safe query length in callback (Telegram limit is 64 bytes for callback_data)
        safe_query = result.query[:45]

        nav_row: list[Button] = []
        if result.has_prev_page:
            nav_row.append(
                Button.inline("◀️ Prev", data=f"s:p:{result.page - 1}:{safe_query}".encode("utf-8"))
            )
        if result.total_pages > 1:
            nav_row.append(
                Button.inline(f"📄 {result.page} / {result.total_pages}", data=b"s:noop")
            )
        if result.has_next_page:
            nav_row.append(
                Button.inline("Next ▶️", data=f"s:p:{result.page + 1}:{safe_query}".encode("utf-8"))
            )

        if nav_row:
            buttons.append(nav_row)

        # Action row: Download Page & Back to Library
        action_row: list[Button] = [
            Button.inline(
                f"⚡ Download Page ({len(result.tracks)})",
                data=f"s:dl:{result.page}:{safe_query}".encode("utf-8"),
            ),
            Button.inline("📚 Library", data=b"lib:overview"),
        ]
        buttons.append(action_row)

        return "\n".join(lines), buttons
