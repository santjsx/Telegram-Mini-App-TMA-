"""
Job data models and status definitions for TPMC.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Set, Optional
import uuid


class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class Job:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    owner_id: int = 0
    query: str = ""
    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    status: JobStatus = JobStatus.QUEUED
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    delivered_ids: Set[int] = field(default_factory=set)
    status_message_id: Optional[int] = None
    error_summary: Optional[str] = None

    @property
    def progress_pct(self) -> int:
        if not self.total:
            return 0
        return int((self.completed + self.skipped + self.failed) / self.total * 100)

    @property
    def progress_bar(self) -> str:
        """Render a 16-character graphical progress bar."""
        total_slots = 16
        pct = self.progress_pct
        filled_slots = int(total_slots * (pct / 100))
        filled_slots = max(0, min(total_slots, filled_slots))
        empty_slots = total_slots - filled_slots
        return "█" * filled_slots + "░" * empty_slots

    def format_progress_message(self) -> str:
        status_name = self.status.value.title()
        return (
            f"🎵 **Delivery Job [{self.id}]**\n\n"
            f"**Query:** `{self.query}`\n"
            f"**Progress:** {self.completed + self.skipped + self.failed} / {self.total} ({self.progress_pct}%)\n"
            f"`{self.progress_bar}`\n\n"
            f"• **Sent:** {self.completed}\n"
            f"• **Skipped:** {self.skipped}\n"
            f"• **Failed:** {self.failed}\n\n"
            f"**Status:** `{status_name}`"
        )
