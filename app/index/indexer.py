"""
In-memory resilient indexer for TPMC.
Rebuilds rapidly from Telegram storage channel history in the background.
Survives Render restarts logically without persistent disk dependencies.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import Dict, Set, Optional, List, Tuple, Any, TYPE_CHECKING

from app.index.models import Track
from app.index.parser import MetadataParser, normalize_string

if TYPE_CHECKING:
    from app.telegram.user_client import UserClientManager

logger = logging.getLogger(__name__)


class IndexState:
    INITIALIZING = "INITIALIZING"
    INDEXING = "INDEXING"
    READY = "READY"
    ERROR = "ERROR"


class MusicIndexer:
    def __init__(self) -> None:
        self.state = IndexState.INITIALIZING
        self._tracks: Dict[int, Track] = {}

        # Inverted index mappings: key -> set of message_ids
        self._tag_index: Dict[str, Set[int]] = {}
        self._artist_index: Dict[str, Set[int]] = {}
        self._album_index: Dict[str, Set[int]] = {}
        self._genre_index: Dict[str, Set[int]] = {}

        self.messages_scanned: int = 0
        self.last_sync_time: Optional[datetime] = None
        self._indexing_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    @property
    def total_tracks(self) -> int:
        return len(self._tracks)

    def get_track(self, message_id: int) -> Optional[Track]:
        return self._tracks.get(message_id)

    def get_all_tracks(self) -> List[Track]:
        return list(self._tracks.values())

    def add_track(self, track: Track) -> None:
        """Add or replace a track and update secondary search indexes."""
        mid = track.message_id
        # If updating, clean previous inverted index references
        if mid in self._tracks:
            self._remove_from_indexes(mid)

        self._tracks[mid] = track

        # Index tags
        for tag in track.tags:
            self._tag_index.setdefault(tag, set()).add(mid)

        # Index artist
        if track.performer:
            norm_artist = normalize_string(track.performer)
            self._artist_index.setdefault(norm_artist, set()).add(mid)

        # Index album
        if track.album and track.album != "Unknown Album":
            norm_album = normalize_string(track.album)
            self._album_index.setdefault(norm_album, set()).add(mid)

        # Index genre
        if track.genre and track.genre != "Unknown Genre":
            norm_genre = normalize_string(track.genre)
            self._genre_index.setdefault(norm_genre, set()).add(mid)

    def remove_track(self, message_id: int) -> None:
        """Remove a track and clean all index entries."""
        if message_id in self._tracks:
            self._remove_from_indexes(message_id)
            del self._tracks[message_id]

    def _remove_from_indexes(self, message_id: int) -> None:
        for tag_set in self._tag_index.values():
            tag_set.discard(message_id)
        for artist_set in self._artist_index.values():
            artist_set.discard(message_id)
        for album_set in self._album_index.values():
            album_set.discard(message_id)
        for genre_set in self._genre_index.values():
            genre_set.discard(message_id)

    def get_top_artists(self, limit: int = 15) -> List[Tuple[str, int]]:
        """Return list of (artist_name, track_count) sorted by count descending."""
        counts = []
        for norm_artist, m_ids in self._artist_index.items():
            if not m_ids:
                continue
            # Pick display name from first track
            first_track = next((self._tracks[mid] for mid in m_ids if mid in self._tracks), None)
            display_name = first_track.performer if first_track and first_track.performer else norm_artist.title()
            counts.append((display_name, len(m_ids)))
        counts.sort(key=lambda x: x[1], reverse=True)
        return counts[:limit]

    def get_top_albums(self, limit: int = 15) -> List[Tuple[str, str, int]]:
        """Return list of (album_name, artist_name, track_count) sorted by count descending."""
        counts = []
        for norm_album, m_ids in self._album_index.items():
            if not m_ids:
                continue
            first_track = next((self._tracks[mid] for mid in m_ids if mid in self._tracks), None)
            display_album = first_track.album if first_track and first_track.album else norm_album.title()
            display_artist = first_track.performer if first_track and first_track.performer else "Various"
            counts.append((display_album, display_artist, len(m_ids)))
        counts.sort(key=lambda x: x[2], reverse=True)
        return counts[:limit]

    def get_top_genres(self, limit: int = 15) -> List[Tuple[str, int]]:
        """Return list of (genre_name, track_count) sorted by count descending."""
        counts = []
        for norm_genre, m_ids in self._genre_index.items():
            if not m_ids:
                continue
            first_track = next((self._tracks[mid] for mid in m_ids if mid in self._tracks), None)
            display_genre = first_track.genre if first_track and first_track.genre else norm_genre.title()
            counts.append((display_genre, len(m_ids)))
        counts.sort(key=lambda x: x[1], reverse=True)
        return counts[:limit]

    def get_favorites_count(self) -> int:
        return sum(1 for t in self._tracks.values() if t.is_favorite)

    def get_random_track(self) -> Optional[Track]:
        import random
        if not self._tracks:
            return None
        return random.choice(list(self._tracks.values()))

    def get_stats(self) -> Dict[str, Any]:
        """Return library metrics and index health status."""
        return {
            "state": self.state,
            "total_tracks": len(self._tracks),
            "total_artists": len(self._artist_index),
            "total_albums": len(self._album_index),
            "total_genres": len(self._genre_index),
            "favorites": self.get_favorites_count(),
            "messages_scanned": self.messages_scanned,
            "last_sync_time": (
                self.last_sync_time.strftime("%Y-%m-%d %H:%M:%S UTC")
                if self.last_sync_time
                else "Never"
            ),
        }

    async def start_indexing(
        self, user_client: UserClientManager, channel_id: int, reset: bool = False
    ) -> None:
        """Launch background non-blocking indexing task."""
        if self._indexing_task and not self._indexing_task.done():
            logger.warning("Indexing is already actively running.")
            return

        self._indexing_task = asyncio.create_task(
            self._run_indexing(user_client, channel_id, reset=reset)
        )

    async def _run_indexing(
        self, user_client: UserClientManager, channel_id: int, reset: bool = False
    ) -> None:
        async with self._lock:
            self.state = IndexState.INDEXING
            logger.info(f"Starting channel index scan on channel={channel_id} (reset={reset})...")

            if reset:
                self._tracks.clear()
                self._tag_index.clear()
                self._artist_index.clear()
                self._album_index.clear()
                self._genre_index.clear()
                self.messages_scanned = 0

            try:
                min_id = 0
                if not reset and self._tracks:
                    # Incremental scan: start from latest indexed message ID
                    min_id = max(self._tracks.keys())

                scanned_count = 0
                indexed_count = 0

                async for message in user_client.iter_channel_messages(min_id=min_id):
                    scanned_count += 1
                    self.messages_scanned += 1

                    track = MetadataParser.extract_track(message, channel_id)
                    if track:
                        self.add_track(track)
                        indexed_count += 1

                    if scanned_count % 100 == 0:
                        logger.info(
                            f"Indexing progress: scanned={scanned_count}, tracks_indexed={len(self._tracks)}"
                        )
                        # Yield to event loop to keep the bot responsive
                        await asyncio.sleep(0.01)

                self.last_sync_time = datetime.now(timezone.utc)
                self.state = IndexState.READY
                logger.info(
                    f"Indexing completed successfully! Scanned {scanned_count} messages, "
                    f"indexed {indexed_count} tracks. Total tracks in library: {len(self._tracks)}."
                )
            except asyncio.CancelledError:
                logger.info("Indexing task was cancelled.")
                self.state = IndexState.READY
                raise
            except Exception as e:
                logger.error(f"Error during channel indexing: {e}", exc_info=True)
                self.state = IndexState.ERROR
