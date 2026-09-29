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

PAGE_SIZE = 6


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
                "╔══════════════════════════════════╗\n"
                "   🔍 ✦ 𝗜𝗡𝗦𝗧𝗔𝗡𝗧 𝗧𝗥𝗔𝗖𝗞 𝗦𝗘𝗔𝗥𝗖𝗛 ✦ 🔍\n"
                "╚══════════════════════════════════╝\n\n"
                "Please specify a song title, artist, album, or tag to search.\n\n"
                "💡 **Search Syntax Examples:**\n"
                "• `/search rock` — Search by genre or title keyword\n"
                "• `/search album:Abbey Road` — Filter by album name\n"
                "• `/search #favorite` — View your starred tracks"
            )
            return

        all_tracks = self.indexer.get_all_tracks()
        result = SearchEngine.search(query, all_tracks, page=1, page_size=PAGE_SIZE)

        if result.total_count == 0:
            await message.reply(
                "🔍 **No Matching Tracks Found**\n\n"
                f"No songs found matching: `{query}` in your library.\n\n"
                "💡 *Try a broader search term or explore* `/albums` *and* `/songs`."
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
        if is_album_view:
            album_name = query_str[6:].strip()
            header = f"💿 **Album: {album_name}**"
        elif q_lower in ("all", "#all", "songs", "all_songs", "all tracks"):
            header = "🎵 **All Songs (A–Z)**"
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

        # Safe query length in callback (Telegram limit is 64 bytes for callback_data)
        safe_query = (result.query or "")[:35]

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
            if only_track.album and only_track.album != "Unknown Album":
                lines.append(f"   💿 *{only_track.album}*")

            specs = []
            if only_track.duration_formatted:
                specs.append(f"⏱ {only_track.duration_formatted}")
            if only_track.file_size_formatted:
                specs.append(f"💾 {only_track.file_size_formatted}")
            specs.append(quality)
            lines.append(f"   {' · '.join(specs)}\n")

            fav_label = "⭐ Star Favorite" if not only_track.is_favorite else "⭐ Unstar"
            buttons = [
                [
                    Button.inline(
                        f"📥 Send Audio ({only_track.file_size_formatted})",
                        data=f"s:one:{only_track.message_id}".encode("utf-8"),
                    )
                ],
                [
                    Button.inline(fav_label, data=f"s:fav:{only_track.message_id}:{safe_query}".encode("utf-8")),
                    Button.inline("ℹ️ Audio Specs", data=f"s:info:{only_track.message_id}:{safe_query}".encode("utf-8")),
                ],
                [
                    Button.inline("📚 Back to Library", data=b"lib:overview")
                ],
            ]
            return "\n".join(lines), buttons

        # Multi-track layout
        if basket_mask is not None:
            sel_count = bin(basket_mask).count("1")
            lines = [
                f"{header} · **Selection Mode**",
                f"Tap checkboxes to select songs ({sel_count} selected):\n",
            ]
        else:
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

            if not is_album_view:
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
            short_btn_title = clean_title[:13].strip()
            idx_in_page = i - start_num

            if basket_mask is not None:
                is_selected = bool(basket_mask & (1 << idx_in_page))
                box = "☑️" if is_selected else "⬜"
                track_buttons.append(
                    Button.inline(
                        f"{box} {i}. {short_btn_title}",
                        data=f"s:b:{result.page}:{basket_mask}:{idx_in_page + 1}:{safe_query}".encode("utf-8"),
                    )
                )
            else:
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

        if basket_mask is None:
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

            # Action rows: Download Page, Select Tracks, Library
            buttons.append([
                Button.inline(
                    f"⚡ Download Page ({len(result.tracks)})",
                    data=f"s:dl:{result.page}:{safe_query}".encode("utf-8"),
                ),
                Button.inline(
                    "🧺 Select Tracks",
                    data=f"s:b:{result.page}:0:0:{safe_query}".encode("utf-8"),
                ),
            ])
            buttons.append([
                Button.inline("📚 Library", data=b"lib:overview"),
            ])
        else:
            sel_count = bin(basket_mask).count("1")
            buttons.append([
                Button.inline(
                    f"📥 Download Selected ({sel_count})",
                    data=f"s:bdl:{result.page}:{basket_mask}:{safe_query}".encode("utf-8"),
                ),
                Button.inline("✖️ Cancel Selection", data=f"s:p:{result.page}:{safe_query}".encode("utf-8")),
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
