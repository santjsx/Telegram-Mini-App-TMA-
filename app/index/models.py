"""
Track and metadata data models for TPMC in-memory indexing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Track:
    message_id: int
    channel_id: int
    title: str
    performer: str
    album: str = "Unknown Album"
    genre: str = "Unknown Genre"
    duration: int = 0
    file_size: int = 0
    filename: str = "unknown.mp3"
    mime_type: str = "audio/mpeg"
    caption: str = ""
    tags: set[str] = field(default_factory=set)
    structured_tags: dict[str, str] = field(default_factory=dict)
    is_favorite: bool = False
    upload_timestamp: Optional[datetime] = None
    indexed_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def duration_formatted(self) -> str:
        """Format duration in mm:ss."""
        if not self.duration:
            return "0:00"
        mins, secs = divmod(int(self.duration), 60)
        return f"{mins}:{secs:02d}"

    @property
    def file_size_formatted(self) -> str:
        """Format file size in human-readable MB."""
        if not self.file_size:
            return "0 MB"
        mb = self.file_size / (1024 * 1024)
        return f"{mb:.1f} MB"

    @property
    def display_title(self) -> str:
        """Formatted track title and performer."""
        if self.performer and self.performer != "Unknown Artist":
            return f"{self.performer} - {self.title}"
        return self.title
