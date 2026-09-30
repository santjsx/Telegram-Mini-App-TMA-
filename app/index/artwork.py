"""
Artwork Manager for TPMC.
Handles disk caching, retrieval, active on-demand extraction,
and embedding of album cover artwork for Telegram bot cards and WebApp mini app streaming.
"""

from __future__ import annotations

import io
import logging
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from app.index.indexer import MusicIndexer
    from app.index.models import Track
    from app.telegram.user_client import UserClientManager
    from app.telegram.bot import BotManager

logger = logging.getLogger(__name__)


def normalize_album_key(album_name: str) -> str:
    """Normalize album name into an alphanumeric lowercase key for deterministic caching."""
    if not album_name:
        return ""
    return re.sub(r"[^a-z0-9]+", "", album_name.lower())


class ArtworkManager:
    """Manages disk-cached album and track artwork for TPMC."""

    CACHE_DIR: Path = Path("data/artwork_cache")
    ALBUMS_DIR: Path = Path("data/artwork_cache/albums")

    _LOCAL_INDEX_BUILT: bool = False
    _LOCAL_FILES_MAP: Dict[str, Path] = {}

    @classmethod
    def get_cache_dir(cls) -> Path:
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return cls.CACHE_DIR

    @classmethod
    def get_album_cache_dir(cls) -> Path:
        album_dir = cls.CACHE_DIR / "albums"
        album_dir.mkdir(parents=True, exist_ok=True)
        return album_dir

    @classmethod
    def _ensure_local_index(cls) -> None:
        """Scan local music directories once to build an in-memory mapping of filenames to paths."""
        if cls._LOCAL_INDEX_BUILT:
            return

        cls._LOCAL_INDEX_BUILT = True
        candidates: List[Path] = []

        env_path = os.getenv("LOCAL_MUSIC_PATH")
        if env_path:
            p = Path(env_path)
            if p.exists():
                candidates.append(p)

        # Standard Windows / development paths
        for fallback in [
            Path(r"C:\Users\heysa\Music\Songs"),
            Path("music"),
            Path("songs"),
        ]:
            if fallback.exists() and fallback not in candidates:
                candidates.append(fallback)

        valid_exts = {".flac", ".mp3", ".m4a", ".wav", ".ogg", ".opus", ".aac"}
        for root_dir in candidates:
            try:
                for root, _, files in os.walk(root_dir):
                    for f in files:
                        p = Path(root) / f
                        if p.suffix.lower() in valid_exts:
                            cls._LOCAL_FILES_MAP[f.lower()] = p
                            clean_fn = re.sub(r"[^a-z0-9]+", "", f.lower())
                            cls._LOCAL_FILES_MAP[clean_fn] = p
            except Exception as e:
                logger.debug(f"Error scanning local dir {root_dir}: {e}")

    @classmethod
    def find_local_track_file(cls, filename: Optional[str]) -> Optional[Path]:
        """Find local audio file path matching a track's filename."""
        if not filename or filename == "unknown.mp3":
            return None
        cls._ensure_local_index()
        fn_lower = filename.lower()
        if fn_lower in cls._LOCAL_FILES_MAP:
            return cls._LOCAL_FILES_MAP[fn_lower]
        clean_fn = re.sub(r"[^a-z0-9]+", "", fn_lower)
        return cls._LOCAL_FILES_MAP.get(clean_fn)

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
    def _save_album_copy(cls, album_name: Optional[str], pic_data: bytes) -> Optional[Path]:
        """Save a copy of artwork data indexed by album name for shared album access."""
        if not album_name or album_name == "Unknown Album" or not pic_data:
            return None
        key = normalize_album_key(album_name)
        if not key:
            return None
        album_dir = cls.get_album_cache_dir()
        album_file = album_dir / f"{key}.jpg"
        try:
            album_file.write_bytes(pic_data)
            return album_file
        except Exception as e:
            logger.debug(f"Failed to write album artwork cache for '{album_name}': {e}")
            return None

    @classmethod
    def get_album_artwork(cls, album_name: str, indexer: Optional[MusicIndexer] = None) -> Optional[Path]:
        """
        Find cached artwork for an album.
        1. Checks if any sibling track in that album has a cached message artwork
        2. Checks data/artwork_cache/albums/{key}.jpg
        3. Checks if any track in that album has a local audio file and extracts it
        """
        if not album_name or album_name == "Unknown Album":
            return None

        # 1. Track message cache check (first check sibling tracks in album)
        if indexer:
            tracks = indexer.get_tracks_by_album(album_name)
            for t in tracks:
                p = cls.get_track_artwork(t.message_id)
                if p:
                    return p

        # 2. Album cache check
        key = normalize_album_key(album_name)
        if key:
            album_dir = cls.get_album_cache_dir()
            album_file = album_dir / f"{key}.jpg"
            if album_file.exists() and album_file.stat().st_size > 0:
                return album_file

        # 3. Local file extraction check
        if indexer:
            tracks = indexer.get_tracks_by_album(album_name)
            for t in tracks:
                local_p = cls.find_local_track_file(t.filename)
                if local_p:
                    p = cls.cache_artwork_from_file(t.message_id, local_p, album_name=album_name)
                    if p:
                        return p

        return None

    @classmethod
    def resolve_artwork(cls, track: Optional[Track], indexer: Optional[MusicIndexer] = None) -> Optional[Path]:
        """
        Resolve artwork path for a track synchronously from disk or local files.
        Checks track message_id, then album, then local track file.
        """
        if not track:
            return None

        # 1. Direct message artwork
        p = cls.get_track_artwork(track.message_id)
        if p:
            return p

        # 2. Album artwork check
        if track.album and track.album != "Unknown Album":
            p = cls.get_album_artwork(track.album, indexer)
            if p:
                return p

        # 3. Local file extraction
        if track.filename:
            local_p = cls.find_local_track_file(track.filename)
            if local_p:
                p = cls.cache_artwork_from_file(track.message_id, local_p, album_name=track.album)
                if p:
                    return p

        return None

    @classmethod
    def cache_artwork_from_bytes(
        cls, message_id: int, data: bytes, album_name: Optional[str] = None
    ) -> Optional[Path]:
        """
        Extract embedded artwork from audio file bytes (FLAC or ID3)
        and write to data/artwork_cache/{message_id}.jpg and optionally albums/{key}.jpg.
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
                cls._save_album_copy(album_name, pic_data)
                return out_file
            except Exception as e:
                logger.warning(f"Failed to write artwork cache for msg {message_id}: {e}")
        return None

    @classmethod
    def cache_artwork_from_file(
        cls, message_id: int, file_path: Path, album_name: Optional[str] = None
    ) -> Optional[Path]:
        """
        Extract embedded artwork from a local audio file and save to disk cache.
        """
        if not message_id or not file_path.exists():
            return None

        pic_data = None
        resolved_album = album_name
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
            if not resolved_album and audio and getattr(audio, "tags", None):
                alb = audio.get("album")
                if alb:
                    resolved_album = alb[0] if isinstance(alb, list) else str(alb)
        except Exception as e:
            logger.debug(f"Mutagen read error for {file_path.name}: {e}")

        if pic_data:
            cache_dir = cls.get_cache_dir()
            out_file = cache_dir / f"{message_id}.jpg"
            try:
                out_file.write_bytes(pic_data)
                cls._save_album_copy(resolved_album, pic_data)
                return out_file
            except Exception as e:
                logger.warning(f"Failed to write artwork cache for msg {message_id}: {e}")
        return None

    @classmethod
    async def ensure_track_artwork(
        cls,
        track: Track,
        user_client: Any = None,
        bot_client: Any = None,
        indexer: Optional[MusicIndexer] = None,
    ) -> Optional[Path]:
        """
        Asynchronously ensure artwork exists for a track.
        First checks disk/album/local cache. If missing, attempts on-demand extraction
        from the Telegram storage channel via Telethon (user_client or bot_client).
        """
        if not track:
            return None

        # 1. Fast local / disk check
        existing = cls.resolve_artwork(track, indexer)
        if existing:
            return existing

        # 2. Active Telegram download fallback
        telethon_client = None
        msg = None

        if user_client:
            try:
                msg = await user_client.get_message(track.message_id)
                telethon_client = getattr(user_client, "client", None)
            except Exception as e:
                logger.debug(f"User client get_message error: {e}")

        if not msg and bot_client:
            try:
                telethon_client = getattr(bot_client, "client", bot_client)
                channel_entity = getattr(user_client, "_channel_entity", None) or track.channel_id
                msg = await telethon_client.get_messages(channel_entity, ids=track.message_id)
            except Exception as e:
                logger.debug(f"Bot client get_messages error: {e}")

        if msg and telethon_client and getattr(msg, "document", None):
            doc = msg.document
            cache_dir = cls.get_cache_dir()
            out_file = cache_dir / f"{track.message_id}.jpg"

            # 2a. Download document thumbnail if present
            if getattr(doc, "thumbs", None):
                try:
                    await telethon_client.download_media(doc.thumbs[0], file=str(out_file))
                    if out_file.exists() and out_file.stat().st_size > 0:
                        cls._save_album_copy(track.album, out_file.read_bytes())
                        return out_file
                except Exception as e:
                    logger.debug(f"Failed to download thumb for msg {track.message_id}: {e}")

            # 2b. Download first 384KB header to extract Mutagen FLAC/ID3 artwork
            try:
                chunks = []
                total = 0
                target_size = 384 * 1024
                chunk_step = 128 * 1024
                async for chunk in telethon_client.iter_download(
                    doc, offset=0, chunk_size=chunk_step, request_size=chunk_step
                ):
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= target_size:
                        break
                data = b"".join(chunks)
                p = cls.cache_artwork_from_bytes(track.message_id, data, album_name=track.album)
                del data
                if p:
                    return p
            except Exception as e:
                logger.debug(f"Failed to download header for msg {track.message_id}: {e}")

        # 3. Sibling track fallback
        if track.album and track.album != "Unknown Album" and indexer:
            alb_art = cls.get_album_artwork(track.album, indexer)
            if alb_art:
                return alb_art

        return None

    @classmethod
    async def ensure_album_artwork(
        cls,
        album_name: str,
        indexer: MusicIndexer,
        user_client: Any = None,
        bot_client: Any = None,
    ) -> Optional[Path]:
        """
        Asynchronously ensure artwork exists for an album.
        Checks album cache and local files first, then fetches up to 3 tracks from Telegram.
        """
        if not album_name or album_name == "Unknown Album":
            return None

        # 1. Fast local / cache check
        existing = cls.get_album_artwork(album_name, indexer)
        if existing:
            return existing

        if not indexer:
            return None

        tracks = indexer.get_tracks_by_album(album_name)
        if not tracks:
            return None

        # 2. Try ensuring artwork for first few tracks
        for t in tracks[:3]:
            p = await cls.ensure_track_artwork(
                t, user_client=user_client, bot_client=bot_client, indexer=indexer
            )
            if p:
                try:
                    cls._save_album_copy(album_name, p.read_bytes())
                except Exception:
                    pass
                return p

        return None

    @classmethod
    async def precache_library_artworks(
        cls,
        indexer: MusicIndexer,
        user_client: Any = None,
        bot_client: Any = None,
    ) -> int:
        """
        Proactively pre-caches artwork for all albums in the index.
        Runs gracefully in the background with small yields to not block bot responsiveness.
        """
        import asyncio
        if not indexer:
            return 0

        albums = indexer.get_all_albums()
        cached_count = 0
        for alb, _artist, _count in albums:
            if not alb or alb == "Unknown Album":
                continue
            if cls.get_album_artwork(alb, indexer):
                continue
            try:
                p = await cls.ensure_album_artwork(alb, indexer, user_client=user_client, bot_client=bot_client)
                if p:
                    cached_count += 1
            except Exception as e:
                logger.debug(f"Precache failed for album '{alb}': {e}")
            await asyncio.sleep(0.05)
        return cached_count

    @classmethod
    def scan_and_cache_local_directory(cls, directory_path: Optional[Path] = None) -> int:
        """
        Scan a local songs directory and populate data/artwork_cache/albums with cover art.
        """
        target_dir = directory_path
        if not target_dir:
            cls._ensure_local_index()
            env_path = os.getenv("LOCAL_MUSIC_PATH")
            if env_path and Path(env_path).exists():
                target_dir = Path(env_path)
            elif Path(r"C:\Users\heysa\Music\Songs").exists():
                target_dir = Path(r"C:\Users\heysa\Music\Songs")
            elif Path("music").exists():
                target_dir = Path("music")

        if not target_dir or not target_dir.exists():
            return 0

        out_dir = cls.get_album_cache_dir()
        valid_exts = {".flac", ".mp3", ".m4a"}
        cached = 0

        for root, _, files in os.walk(target_dir):
            for f in files:
                p = Path(root) / f
                if p.suffix.lower() not in valid_exts:
                    continue
                try:
                    from mutagen import File as MutagenFile
                    audio = MutagenFile(str(p))
                    if not audio or not getattr(audio, "tags", None):
                        continue
                    alb = audio.get("album")
                    if not alb:
                        continue
                    alb_str = alb[0] if isinstance(alb, list) else str(alb)
                    key = normalize_album_key(alb_str)
                    if not key:
                        continue
                    out_file = out_dir / f"{key}.jpg"
                    if out_file.exists() and out_file.stat().st_size > 0:
                        continue

                    pic_data = None
                    if hasattr(audio, "pictures") and audio.pictures:
                        pic_data = audio.pictures[0].data
                    elif audio.tags:
                        for k in audio.tags.keys():
                            if k.startswith("APIC"):
                                pic_data = audio.tags[k].data
                                break
                    if pic_data:
                        out_file.write_bytes(pic_data)
                        cached += 1
                except Exception:
                    pass
        return cached
