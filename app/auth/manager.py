"""
Access control manager for Telegram Personal Music Cloud (TPMC).
Handles in-app access requests, admin approvals, denials, revocations,
and thread-safe atomic persistence.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class UserInfo:
    user_id: int
    first_name: str = ""
    last_name: str = ""
    username: Optional[str] = None
    approved_at: str = ""
    approved_by: int = 0

    @property
    def display_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name if name else f"User {self.user_id}"

    @property
    def mention(self) -> str:
        if self.username:
            return f"@{self.username}"
        return self.display_name


@dataclass
class RequestInfo:
    user_id: int
    first_name: str = ""
    last_name: str = ""
    username: Optional[str] = None
    requested_at: str = ""

    @property
    def display_name(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name if name else f"User {self.user_id}"

    @property
    def mention(self) -> str:
        if self.username:
            return f"@{self.username}"
        return self.display_name


class AccessManager:
    """
    Manages approved and pending users with atomic persistent JSON storage.
    Owner is always permanently authorized as Super Admin.
    """

    def __init__(
        self,
        admin_id: int,
        persistence_path: str = "data/access_control.json",
        initial_approved_ids: tuple[int, ...] = (),
    ) -> None:
        self.admin_id = admin_id
        self.persistence_path = Path(persistence_path)
        self.approved_users: dict[int, UserInfo] = {}
        self.pending_requests: dict[int, RequestInfo] = {}
        self._lock = asyncio.Lock()

        # Load persisted data and seed initial IDs
        self._load()
        for uid in initial_approved_ids:
            if uid != self.admin_id and uid not in self.approved_users:
                self.approved_users[uid] = UserInfo(
                    user_id=uid,
                    first_name=f"ConfigUser",
                    approved_at=datetime.now(timezone.utc).isoformat(),
                    approved_by=self.admin_id,
                )
        self._save_sync()

    def is_admin(self, user_id: int) -> bool:
        """Check if user is the primary super admin / owner."""
        return user_id == self.admin_id

    def is_authorized(self, user_id: int) -> bool:
        """Check if user has permission to use bot commands and stream music."""
        return user_id == self.admin_id or user_id in self.approved_users

    def is_pending(self, user_id: int) -> bool:
        """Check if user has an active pending access request."""
        return user_id in self.pending_requests

    def get_user(self, user_id: int) -> Optional[UserInfo]:
        return self.approved_users.get(user_id)

    def get_request(self, user_id: int) -> Optional[RequestInfo]:
        return self.pending_requests.get(user_id)

    def get_all_approved(self) -> list[UserInfo]:
        return list(self.approved_users.values())

    def get_all_pending(self) -> list[RequestInfo]:
        return list(self.pending_requests.values())

    async def add_request(
        self,
        user_id: int,
        first_name: str = "",
        last_name: str = "",
        username: Optional[str] = None,
    ) -> tuple[bool, RequestInfo]:
        """
        Record a new access request from an unauthorized user.
        Returns (is_new, request_info). If already pending or approved, is_new is False.
        """
        async with self._lock:
            if self.is_authorized(user_id):
                info = self.approved_users.get(user_id) or UserInfo(user_id=user_id)
                return False, RequestInfo(
                    user_id=user_id,
                    first_name=info.first_name,
                    last_name=info.last_name,
                    username=info.username,
                )

            if user_id in self.pending_requests:
                # Already pending - return existing request without spamming
                req = self.pending_requests[user_id]
                return False, req

            req = RequestInfo(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
                requested_at=datetime.now(timezone.utc).isoformat(),
            )
            self.pending_requests[user_id] = req
            self._save_sync()
            logger.info(f"Access request recorded: {req.display_name} (ID: {user_id})")
            return True, req

    async def approve_user(self, user_id: int, approved_by: int) -> Optional[UserInfo]:
        """
        Approve an access request. Promotes pending user to approved user and persists.
        """
        async with self._lock:
            pending = self.pending_requests.pop(user_id, None)
            first_name = pending.first_name if pending else ""
            last_name = pending.last_name if pending else ""
            username = pending.username if pending else None

            user = UserInfo(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
                approved_at=datetime.now(timezone.utc).isoformat(),
                approved_by=approved_by,
            )
            self.approved_users[user_id] = user
            self._save_sync()
            logger.info(f"User approved: {user.display_name} (ID: {user_id}) by {approved_by}")
            return user

    async def deny_user(self, user_id: int) -> Optional[RequestInfo]:
        """
        Deny and discard a pending access request.
        """
        async with self._lock:
            pending = self.pending_requests.pop(user_id, None)
            if pending:
                self._save_sync()
                logger.info(f"Access request denied for user {user_id}")
            return pending

    async def revoke_user(self, user_id: int) -> bool:
        """
        Revoke access for an existing approved user.
        Owner (Super Admin) cannot be revoked.
        """
        if user_id == self.admin_id:
            logger.warning("Attempted to revoke Super Admin - action rejected.")
            return False

        async with self._lock:
            if user_id in self.approved_users:
                user = self.approved_users.pop(user_id)
                self._save_sync()
                logger.info(f"Revoked access for user {user.display_name} (ID: {user_id})")
                return True
            return False

    def _load(self) -> None:
        """Load state from persistent JSON file."""
        if not self.persistence_path.exists():
            return

        try:
            with open(self.persistence_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for item in data.get("approved_users", []):
                uid = int(item["user_id"])
                self.approved_users[uid] = UserInfo(
                    user_id=uid,
                    first_name=item.get("first_name", ""),
                    last_name=item.get("last_name", ""),
                    username=item.get("username"),
                    approved_at=item.get("approved_at", ""),
                    approved_by=int(item.get("approved_by", 0)),
                )

            for item in data.get("pending_requests", []):
                uid = int(item["user_id"])
                self.pending_requests[uid] = RequestInfo(
                    user_id=uid,
                    first_name=item.get("first_name", ""),
                    last_name=item.get("last_name", ""),
                    username=item.get("username"),
                    requested_at=item.get("requested_at", ""),
                )
            logger.info(
                f"Loaded access control: {len(self.approved_users)} approved user(s), "
                f"{len(self.pending_requests)} pending request(s)"
            )
        except Exception as e:
            logger.error(f"Failed to load access control persistence file: {e}", exc_info=True)

    def _save_sync(self) -> None:
        """Atomic write to persistence file."""
        try:
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "admin_id": self.admin_id,
                "approved_users": [asdict(u) for u in self.approved_users.values()],
                "pending_requests": [asdict(r) for r in self.pending_requests.values()],
            }
            tmp_path = self.persistence_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.persistence_path)
        except Exception as e:
            logger.error(f"Failed to save access control file: {e}", exc_info=True)
