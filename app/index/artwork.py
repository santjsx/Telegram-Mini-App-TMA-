"""
Artwork Manager for TPMC.
Handles disk caching, retrieval, and embedding of album cover artwork
for Telegram bot cards and WebApp mini app streaming.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.index.indexer import MusicIndexer
    from app.index.models import Track

logger = logging.getLogger(__name__)

CACHE_DIR = Path("data/artwork_cache")


class ArtworkManager:
    """Manages disk-cached album and track artwork for TPMC."""

    CACHE_DIR: Path = Path("data/artwork_cache")

    @classmethod
    def get_cache_dir(cls) -> Path:
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return cls.CACHE_DIR

    @classmethod
    def get_track_artwork(cls, message_id: int) -> Optional[Path]:
        """Return Path to cached artwork for a message ID if it exists on disk."""
        if not message_id:
            return None
        p = cls.CACHE_DIR / f"{message_id}.jpg"
        if p.exists() and p.stat().st_size > 0:
            return p
        return None

    @classmethod
    def get_album_artwork(cls, album_name: str, indexer: Optional[MusicIndexer]) -> Optional[Path]:
        """
        Find cached artwork for an album by searching indexed tracks in that album.
        Returns the path to the first track with cached artwork.
        """
        if not album_name or not indexer:
            return None
        tracks = indexer.get_tracks_by_album(album_name)
        for t in tracks:
            p = cls.get_track_artwork(t.message_id)
            if p:
                return p
        return None

    @classmethod
    def resolve_artwork(cls, track: Optional[Track], indexer: Optional[MusicIndexer]) -> Optional[Path]:
        """
        Resolve artwork path for a track. Checks track message_id first,
        then falls back to any sibling track in the same album.
        """
        if not track:
            return None
        # 1. Direct message artwork
        p = cls.get_track_artwork(track.message_id)
        if p:
            return p
        # 2. Album artwork fallback
        if track.album and track.album != "Unknown Album" and indexer:
            return cls.get_album_artwork(track.album, indexer)
        return None

    @classmethod
    def cache_artwork_from_bytes(cls, message_id: int, data: bytes) -> Optional[Path]:
        """
        Extract embedded artwork from audio file bytes (FLAC or ID3)
        and write directly to data/artwork_cache/{message_id}.jpg.
        """
        if not message_id or not data:
            return None

        pic_data = None
        # 1. Try FLAC
        try:
            from mutagen.flac import FLAC
            fl = FLAC(io.BytesIO(data))
            if fl.pictures:
                pic_data = fl.pictures[0].data
        except Exception:
            pass

        # 2. Try MutagenFile (ID3 / MP3 / APIC)
        if not pic_data:
            try:
                from mutagen import File as MutagenFile
                mf = MutagenFile(io.BytesIO(data))
                if hasattr(mf, "pictures") and mf.pictures:
                    pic_data = mf.pictures[0].data
                elif mf and mf.tags:
                    for k in mf.tags.keys():
                        if k.startswith("APIC"):
                            pic_data = mf.tags[k].data
                            break
            except Exception:
                pass

        if pic_data:
            cache_dir = cls.get_cache_dir()
            out_file = cache_dir / f"{message_id}.jpg"
            try:
                out_file.write_bytes(pic_data)
                return out_file
            except Exception as e:
                logger.warning(f"Failed to write artwork cache for msg {message_id}: {e}")
        return None

    @classmethod
    def cache_artwork_from_file(cls, message_id: int, file_path: Path) -> Optional[Path]:
        """
        Extract embedded artwork from a local audio file and save to disk cache.
        """
        if not message_id or not file_path.exists():
            return None

        pic_data = None
        try:
            from mutagen import File as MutagenFile
            audio = MutagenFile(str(file_path))
            if hasattr(audio, "pictures") and audio.pictures:
                pic_data = audio.pictures[0].data
            elif audio and getattr(audio, "tags", None):
                for k in audio.tags.keys():
                    if k.startswith("APIC"):
                        pic_data = audio.tags[k].data
                        break
        except Exception as e:
            logger.debug(f"Mutagen read error for {file_path.name}: {e}")

        if pic_data:
            cache_dir = cls.get_cache_dir()
            out_file = cache_dir / f"{message_id}.jpg"
            try:
                out_file.write_bytes(pic_data)
                return out_file
            except Exception as e:
                logger.warning(f"Failed to write artwork cache for msg {message_id}: {e}")
        return None
