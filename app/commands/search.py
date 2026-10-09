"""
Search command and pagination handler.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Any
from telethon import Button, events
from telethon.tl.custom.message import Message

from app.index.search import SearchEngine
from app.index.parser import clean_display_title, get_audio_badge
from app.index.artwork import ArtworkManager
from app.telegram.artwork import send_or_edit_artwork

if TYPE_CHECKING:
    from app.index.indexer import MusicIndexer
    from app.jobs.manager import JobManager

logger = logging.getLogger(__name__)

PAGE_SIZE = 8


class SearchCommandHandler:
    def __init__(
        self,
        indexer: MusicIndexer,
        job_manager: JobManager,
        webapp_url: Optional[str] = None,
    ) -> None:
        self.indexer = indexer
        self.job_manager = job_manager
        self.webapp_url = webapp_url

    @property
    def user_client(self) -> Any:
        if hasattr(self.job_manager, "delivery_engine"):
            return getattr(self.job_manager.delivery_engine, "user_client", None)
        return None

    @property
    def bot_client(self) -> Any:
        if hasattr(self.job_manager, "delivery_engine"):
            bm = getattr(self.job_manager.delivery_engine, "bot_manager", None)
            if bm and hasattr(bm, "client"):
                return bm.client
        return None

    async def handle_search(self, message: Message) -> None:
        text = message.text.strip()
        if text.startswith("/search"):
            parts = text.split(maxsplit=1)
            query = parts[1].strip() if len(parts) > 1 else ""
        else:
            query = text

        if not query:
            await message.reply(
                "🔎 **Instant Music Search** 🎵\n\n"
                "Search through your personal music sanctuary in seconds!\n\n"
                "**Search Examples:**\n"
                "- Song or artist: `/search blinding lights` or `/search coldplay`\n"
                "- By album: `/search album:Abbey Road`\n"
                "- By tag / genre: `/search #favorite` or `/search #rock`\n\n"
                "💡 *You can also type any song title directly into this chat!*"
            )
            return

        all_tracks = self.indexer.get_all_tracks()
        result = SearchEngine.search(query, all_tracks, page=1, page_size=PAGE_SIZE)

        if result.total_count == 0:
            await message.reply(
                f"No songs found matching: `{query}`",
                buttons=[[
                    Button.inline("⬅️", data=b"s:noop"),
                    Button.inline("❌", data=b"s:close"),
                    Button.inline("➡️", data=b"s:noop"),
                ]],
            )
            return

        msg_text, buttons = self._format_page(result)

        artwork_path = None
        q_lower = query.lower()
        if q_lower.startswith("album:"):
            album_name = query[6:].strip()
            artwork_path = await ArtworkManager.ensure_album_artwork(
                album_name, self.indexer, user_client=self.user_client, bot_client=self.bot_client
            )
        elif result.total_count == 1:
            artwork_path = await ArtworkManager.ensure_track_artwork(
                result.tracks[0], user_client=self.user_client, bot_client=self.bot_client, indexer=self.indexer
            )

        await send_or_edit_artwork(message, msg_text, buttons=buttons, artwork_path=artwork_path)

    async def handle_callback(self, event: events.CallbackQuery.Event) -> None:
        data = event.data.decode("utf-8")
        if not data.startswith("s:"):
            return

        if data in {"s:noop", "s:p:noop"}:
            await event.answer()
            return

        if data == "s:close":
            try:
                await event.delete()
            except Exception:
                await event.answer("Closed.")
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

        # Audio Specs Inspector
        if action == "info":
            msg_id = int(parts[2])
            return_query = parts[3] if len(parts) > 3 else ""
            track = self.indexer.get_track(msg_id)
            if not track:
                await event.answer("Track not found.", alert=True)
                return
            msg_text, buttons = self._format_track_info(track, return_query=return_query)
            artwork_path = await ArtworkManager.ensure_track_artwork(
                track, user_client=self.user_client, bot_client=self.bot_client, indexer=self.indexer
            )
            await send_or_edit_artwork(event, msg_text, buttons=buttons, artwork_path=artwork_path)
            return

        # 1-Tap Favorite Toggle
        if action == "fav":
            msg_id = int(parts[2])
            return_query = parts[3] if len(parts) > 3 else ""
            is_fav = self.indexer.toggle_favorite(msg_id)
            if is_fav is None:
                await event.answer("Track not found.", alert=True)
                return
            status_text = "⭐ Added to Favorites!" if is_fav else "Removed from Favorites."
            await event.answer(status_text)
            track = self.indexer.get_track(msg_id)
            if track:
                msg_text, buttons = self._format_track_info(track, return_query=return_query)
                await event.edit(msg_text, buttons=buttons)
            return

        # Basket multi-select toggle: s:b:<page>:<mask_int>:<toggle_idx>:<query>
        if action == "b":
            b_parts = data.split(":", 5)
            if len(b_parts) >= 6:
                page = int(b_parts[2])
                mask = int(b_parts[3])
                toggle = int(b_parts[4])
                query = b_parts[5]
                if toggle > 0:
                    mask ^= (1 << (toggle - 1))
                all_tracks = self.indexer.get_all_tracks()
                result = SearchEngine.search(query, all_tracks, page=page, page_size=PAGE_SIZE)
                msg_text, buttons = self._format_page(result, basket_mask=mask)
                await event.edit(msg_text, buttons=buttons)
                await event.answer()
                return

        # Basket download selected: s:bdl:<page>:<mask_int>:<query>
        if action == "bdl":
            b_parts = data.split(":", 4)
            if len(b_parts) >= 5:
                page = int(b_parts[2])
                mask = int(b_parts[3])
                query = b_parts[4]
                all_tracks = self.indexer.get_all_tracks()
                result = SearchEngine.search(query, all_tracks, page=page, page_size=PAGE_SIZE)
                selected = [t for idx, t in enumerate(result.tracks) if (mask & (1 << idx))]
                if not selected:
                    await event.answer("⚠️ No tracks selected. Tap checkboxes first.", alert=True)
                    return
                await event.answer(f"Queued {len(selected)} selected track(s) for delivery!")
                await self.job_manager.start_delivery_job(
                    owner_id=event.sender_id,
                    query=f"Selected {len(selected)} tracks of '{query}'",
                    tracks=selected,
                )
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
        artwork_path = None
        q_lower = query.lower()
        if q_lower.startswith("album:"):
            album_name = query[6:].strip()
            artwork_path = await ArtworkManager.ensure_album_artwork(
                album_name, self.indexer, user_client=self.user_client, bot_client=self.bot_client
            )
        elif result.total_count == 1:
            artwork_path = await ArtworkManager.ensure_track_artwork(
                result.tracks[0], user_client=self.user_client, bot_client=self.bot_client, indexer=self.indexer
            )

        await send_or_edit_artwork(event, msg_text, buttons=buttons, artwork_path=artwork_path)

    def _format_track_info(self, track, return_query: str = "") -> tuple[str, list[list[Button]]]:
        clean_title = clean_display_title(track.title or track.display_title)
        quality = get_audio_badge(track)
        lines = [
            "ℹ️ **Audio Specs & File Inspector**\n",
            f"🎧 **Title:** {clean_title}",
        ]
        if track.performer and track.performer != "Unknown Artist":
            lines.append(f"👤 **Artist:** {track.performer}")
        lines.extend([
            f"💿 **Album:** {track.album}",
            f"⏱ **Duration:** {track.duration_formatted}",
            f"💾 **File Size:** {track.file_size_formatted} ({track.file_size:,} bytes)",
            f"💽 **Codec Quality:** {quality}",
            f"📁 **Filename:** `{track.filename}`",
            f"🏷 **MIME Type:** `{track.mime_type}`",
            f"⭐ **Favorite:** {'Yes ⭐' if track.is_favorite else 'No'}",
        ])
        fav_label = "⭐ Add to Favorites" if not track.is_favorite else "⭐ Remove Favorite"
        safe_query = return_query[:35]
        buttons = [
            [
                Button.inline(
                    f"📥 Send Audio ({track.file_size_formatted})",
                    data=f"s:one:{track.message_id}".encode("utf-8"),
                )
            ],
            [
                Button.inline(fav_label, data=f"s:fav:{track.message_id}:{safe_query}".encode("utf-8")),
            ],
        ]
        if return_query:
            buttons.append([
                Button.inline("🔙 Back to Results", data=f"s:p:1:{safe_query}".encode("utf-8"))
            ])
        else:
            buttons.append([
                Button.inline("📁 Root Explorer", data=b"exp:root")
            ])
        return "\n".join(lines), buttons

    def _format_page(self, result, basket_mask: Optional[int] = None) -> tuple[str, list[list[Button]]]:
        query_str = (result.query or "").strip()
        q_lower = query_str.lower()
        is_album_view = q_lower.startswith("album:")

        start_num = (result.page - 1) * result.page_size + 1
        end_num = min(start_num + len(result.tracks) - 1, result.total_count)

        if result.total_count > 1:
            count_str = f"{start_num}–{end_num} of {result.total_count}"
        else:
            count_str = "1 of 1"

        if is_album_view:
            album_name = query_str[6:].strip()
            header = f"💿 **Album: {album_name} · Results {count_str}**"
        elif q_lower.startswith("artist:"):
            artist_name = query_str[7:].strip()
            header = f"🎤 **Artist: {artist_name} · Results {count_str}**"
        elif q_lower.startswith("genre:") or query_str.startswith("#"):
            tag_name = query_str.split(":", 1)[-1].lstrip("#").strip()
            header = f"🎸 **Genre: #{tag_name} · Results {count_str}**"
        elif q_lower in ("favorite", "#favorite"):
            header = f"⭐ **Favorites · Results {count_str}**"
        elif q_lower in ("all", "#all", "songs", "all_songs", "all tracks"):
            header = f"🎵 **All Songs (A–Z) · Results {count_str}**"
        else:
            header = f"Results {count_str}"

        safe_query = (result.query or "")[:35]

        if basket_mask is not None:
            sel_count = bin(basket_mask).count("1")
            lines = [
                f"{header} · Selection Mode ({sel_count} selected)\n",
            ]
        else:
            lines = [
                f"{header}\n",
            ]

        track_buttons: list[Button] = []
        track_rows: list[list[Button]] = []

        for i, t in enumerate(result.tracks, start=1):
            fav = " ⭐" if t.is_favorite else ""
            raw_title = t.title or t.display_title
            clean_title = clean_display_title(raw_title)
            performer = t.performer if t.performer and t.performer != "Unknown Artist" else ""
            quality = get_audio_badge(t)

            if performer and performer.lower() not in clean_title.lower():
                display_str = f"{clean_title} – {performer}"
            else:
                display_str = clean_title

            meta_parts = []
            if t.duration_formatted:
                meta_parts.append(t.duration_formatted)
            if t.file_size_formatted:
                meta_parts.append(t.file_size_formatted)
            if quality:
                meta_parts.append(quality)

            lines.append(f"{i}. {display_str}{fav} {' '.join(meta_parts)}")

            idx_in_page = i - 1
            if basket_mask is not None:
                is_selected = bool(basket_mask & (1 << idx_in_page))
                box = "☑️" if is_selected else "⬜"
                track_buttons.append(
                    Button.inline(
                        f"{box} {i}.",
                        data=f"s:b:{result.page}:{basket_mask}:{idx_in_page + 1}:{safe_query}".encode("utf-8"),
                    )
                )
            else:
                track_buttons.append(
                    Button.inline(f"{i}", data=f"s:one:{t.message_id}".encode("utf-8"))
                )

            if len(track_buttons) == 4:
                track_rows.append(track_buttons)
                track_buttons = []

        if track_buttons:
            track_rows.append(track_buttons)

        buttons: list[list[Button]] = []
        buttons.extend(track_rows)

        if basket_mask is None:
            prev_btn = (
                Button.inline("⬅️", data=f"s:p:{result.page - 1}:{safe_query}".encode("utf-8"))
                if result.has_prev_page
                else Button.inline("⬅️", data=b"s:noop")
            )
            close_btn = Button.inline("❌", data=b"s:close")
            next_btn = (
                Button.inline("➡️", data=f"s:p:{result.page + 1}:{safe_query}".encode("utf-8"))
                if result.has_next_page
                else Button.inline("➡️", data=b"s:noop")
            )
            buttons.append([prev_btn, close_btn, next_btn])
        else:
            sel_count = bin(basket_mask).count("1")
            buttons.append([
                Button.inline(
                    f"📥 Download ({sel_count})",
                    data=f"s:bdl:{result.page}:{basket_mask}:{safe_query}".encode("utf-8"),
                ),
                Button.inline("❌ Cancel", data=f"s:p:{result.page}:{safe_query}".encode("utf-8")),
            ])

        return "\n".join(lines), buttons

    async def handle_inline_query(self, event: events.InlineQuery.Event) -> None:
        """Handle live inline queries (@bot <query>) across Telegram."""
        query = (event.text or "").strip()
        all_tracks = self.indexer.get_all_tracks()
        if not all_tracks:
            await event.answer([], switch_pm="No songs in library yet", switch_pm_param="lib")
            return

        if not query:
            tracks = all_tracks[:10]
        else:
            result = SearchEngine.search(query, all_tracks, page=1, page_size=10)
            tracks = result.tracks

        results = []
        for t in tracks:
            clean_title = clean_display_title(t.title or t.display_title)
            quality = get_audio_badge(t)
            desc_parts = []
            if t.performer and t.performer != "Unknown Artist":
                desc_parts.append(t.performer)
            if t.album and t.album != "Unknown Album":
                desc_parts.append(f"💿 {t.album}")
            if t.duration_formatted:
                desc_parts.append(t.duration_formatted)
            desc_parts.append(quality)
            desc = " · ".join(desc_parts)

            msg_lines = [
                f"🎧 **{clean_title}**",
            ]
            if t.album and t.album != "Unknown Album":
                msg_lines.append(f"💿 *{t.album}*")
            specs = []
            if t.duration_formatted:
                specs.append(f"⏱ {t.duration_formatted}")
            if t.file_size_formatted:
                specs.append(f"💾 {t.file_size_formatted}")
            specs.append(quality)
            msg_lines.append(f"   {' · '.join(specs)}")

            buttons = [
                [
                    Button.inline(
                        f"📥 Send Audio ({t.file_size_formatted})",
                        data=f"s:one:{t.message_id}".encode("utf-8"),
                    )
                ]
            ]
            thumb_url = f"{self.webapp_url}/api/artwork/{t.message_id}" if self.webapp_url else None
            try:
                results.append(
                    event.builder.article(
                        title=f"🎧 {clean_title}",
                        description=desc,
                        text="\n".join(msg_lines),
                        buttons=buttons,
                        thumb=thumb_url,
                    )
                )
            except Exception:
                results.append(
                    event.builder.article(
                        title=f"🎧 {clean_title}",
                        description=desc,
                        text="\n".join(msg_lines),
                        buttons=buttons,
                    )
                )

        await event.answer(results, cache_time=5)
