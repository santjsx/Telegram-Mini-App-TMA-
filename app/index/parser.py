"""
Metadata parsing, audio validation, and tag normalization for TPMC.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from typing import Optional, Tuple, Set, Dict, Any
from telethon.tl.custom.message import Message
from telethon.tl.types import (
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    MessageMediaDocument,
)

from app.index.models import Track

logger = logging.getLogger(__name__)

SUPPORTED_AUDIO_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".flac",
    ".wav",
    ".ogg",
    ".opus",
    ".aac",
}

# Regex to extract hashtag tokens: e.g. #artist:linkin_park, #genre:rock, #favorite
HASHTAG_REGEX = re.compile(r"#([A-Za-z0-9_:\-]+)")

# Canonical album titles for titles that have common typos or missing spaces in hashtag tags
ALBUM_TITLE_CORRECTIONS: Dict[str, str] = {
    "krishnagadi veera prema gaadha": "Krishna Gaadi Veera Prema Gaadha",
    "krishnagadi_veera_prema_gaadha": "Krishna Gaadi Veera Prema Gaadha",
    "krishnagadi": "Krishna Gaadi",
    "adhento gaani vunnapaatugajersey": "Adhento Gaani Vunnapaatuga (Jersey)",
    "adhento_gaani_vunnapaatugajersey": "Adhento Gaani Vunnapaatuga (Jersey)",
    "aasa kooda from think indie": "Think Indie",
    "aaya sher from the paradise single": "The Paradise",
}


def normalize_string(val: str) -> str:
    """Normalize unicode and strip non-alphanumeric noise."""
    normalized = unicodedata.normalize("NFKD", val).encode("ascii", "ignore").decode("utf-8")
    return normalized.lower().strip()


def normalize_tag(tag: str) -> str:
    """
    Normalize tag according to PRD section 13:
    - Strips leading '#'
    - Lowercases
    - Normalizes unicode
    - Strips edge punctuation
    - Preserves key:value structures (e.g. artist:linkin_park)
    """
    cleaned = tag.strip().lstrip("#").strip()
    if ":" in cleaned:
        parts = cleaned.split(":", 1)
        key = normalize_string(parts[0])
        val = normalize_string(parts[1]).replace(" ", "_")
        return f"{key}:{val}"
    return normalize_string(cleaned).replace(" ", "_")


def parse_caption(caption: Optional[str]) -> Tuple[Set[str], Dict[str, str], bool]:
    """
    Parse a message caption to extract normalized tags and structured metadata.
    Returns: (all_tags, structured_tags, is_favorite)
    """
    if not caption:
        return set(), {}, False

    all_tags: Set[str] = set()
    structured_tags: Dict[str, str] = {}
    is_favorite = False

    raw_matches = HASHTAG_REGEX.findall(caption)
    for raw in raw_matches:
        normalized = normalize_tag(raw)
        if not normalized:
            continue
        all_tags.add(normalized)

        if ":" in normalized:
            k, v = normalized.split(":", 1)
            structured_tags[k] = v
            # Also add the value as a standalone tag for easy searching
            # e.g., #genre:rock enables searching both "#genre:rock" and "#rock"
            all_tags.add(v)

        if normalized in {"favorite", "fav", "favourites", "favorites"}:
            is_favorite = True

    return all_tags, structured_tags, is_favorite


class MetadataParser:
    @staticmethod
    def is_audio_message(message: Message) -> bool:
        """
        Verify that message is audio media, checking MIME type,
        Telegram audio attributes, and file extension.
        """
        if not message.media:
            return False

        # Direct audio attribute on message
        if getattr(message, "audio", None) is not None:
            return True

        if isinstance(message.media, MessageMediaDocument) and message.media.document:
            doc = message.media.document
            mime = getattr(doc, "mime_type", "").lower()
            if mime.startswith("audio/"):
                return True

            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeAudio):
                    return True
                if isinstance(attr, DocumentAttributeFilename):
                    ext = os.path.splitext(attr.file_name.lower())[1]
                    if ext in SUPPORTED_AUDIO_EXTENSIONS:
                        return True

        return False

    @classmethod
    def extract_track(cls, message: Message, channel_id: int) -> Optional[Track]:
        """
        Extract Track metadata with fallback hierarchy:
        Caption tags -> Telegram audio metadata -> Filename -> Fallback defaults.
        Never crashes on malformed data.
        """
        if not cls.is_audio_message(message):
            return None

        try:
            caption = message.message or ""
            tags, structured, is_favorite = parse_caption(caption)

            # Audio attribute defaults
            performer = ""
            title = ""
            duration = 0
            file_size = getattr(message, "file", None).size if getattr(message, "file", None) else 0
            filename = "unknown.mp3"
            mime_type = "audio/mpeg"

            if isinstance(message.media, MessageMediaDocument) and message.media.document:
                doc = message.media.document
                file_size = doc.size or file_size
                mime_type = doc.mime_type or mime_type

                for attr in doc.attributes:
                    if isinstance(attr, DocumentAttributeAudio):
                        performer = attr.performer or performer
                        title = attr.title or title
                        duration = attr.duration or duration
                    elif isinstance(attr, DocumentAttributeFilename):
                        filename = attr.file_name or filename

            # Apply Fallback Hierarchy
            # 1. Title
            resolved_title = structured.get("title")
            if not resolved_title:
                resolved_title = title.strip() if title else ""
            if not resolved_title and filename != "unknown.mp3":
                resolved_title = os.path.splitext(filename)[0]
            if not resolved_title:
                resolved_title = f"Track {message.id}"

            # 2. Performer / Artist
            resolved_performer = structured.get("artist")
            if not resolved_performer:
                resolved_performer = performer.strip() if performer else ""
            if not resolved_performer:
                # If filename contains 'Artist - Title', try splitting
                base_fn = os.path.splitext(filename)[0]
                if " - " in base_fn:
                    parts = base_fn.split(" - ", 1)
                    resolved_performer = parts[0].strip()
                    if not resolved_title or resolved_title == base_fn:
                        resolved_title = parts[1].strip()
            if not resolved_performer:
                resolved_performer = "Unknown Artist"

            # 3. Album
            resolved_album = structured.get("album", "Unknown Album")
            if resolved_album != "Unknown Album":
                # Clean underscores
                resolved_album = resolved_album.replace("_", " ").title()

            # Canonical correction for known album titles (e.g., Krishnagadi -> Krishna Gaadi)
            clean_alb = resolved_album.lower().strip()
            if clean_alb in ALBUM_TITLE_CORRECTIONS:
                resolved_album = ALBUM_TITLE_CORRECTIONS[clean_alb]
            elif "krishnagadi" in clean_alb:
                resolved_album = re.sub(r"(?i)krishnagadi", "Krishna Gaadi", resolved_album)

            # 4. Genre
            resolved_genre = structured.get("genre", "Unknown Genre")
            if resolved_genre != "Unknown Genre":
                resolved_genre = resolved_genre.replace("_", " ").title()

            # Normalization on performer & title display
            resolved_performer = resolved_performer.replace("_", " ").title()

            upload_time = getattr(message, "date", None)

            return Track(
                message_id=message.id,
                channel_id=channel_id,
                title=resolved_title,
                performer=resolved_performer,
                album=resolved_album,
                genre=resolved_genre,
                duration=duration,
                file_size=file_size,
                filename=filename,
                mime_type=mime_type,
                caption=caption,
                tags=tags,
                structured_tags=structured,
                is_favorite=is_favorite,
                upload_timestamp=upload_time,
            )
        except Exception as e:
            logger.warning(
                f"Failed to extract track metadata for message {message.id}: {e}",
                exc_info=True,
            )
            return None
