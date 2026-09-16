"""
Bounded Job Manager for TPMC.
Enforces single-job concurrency, collision prevention, throttled progress updates,
graceful cancellation, and restart protection.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import List, Optional, Tuple, TYPE_CHECKING

from app.jobs.models import Job, JobStatus
from app.jobs.delivery import DeliveryEngine
from app.index.models import Track

if TYPE_CHECKING:
    from app.telegram.bot import BotManager

logger = logging.getLogger(__name__)

THROTTLE_INTERVAL_SECONDS = 3.0
THROTTLE_TRACK_COUNT = 5


class JobManager:
    def __init__(self, delivery_engine: DeliveryEngine) -> None:
        self.delivery_engine = delivery_engine
        self._active_job: Optional[Job] = None
        self._job_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    def get_active_job(self) -> Optional[Job]:
        return self._active_job

    async def start_delivery_job(
        self,
        owner_id: int,
        query: str,
        tracks: List[Track],
        bot_manager: Optional[BotManager] = None,
    ) -> Tuple[bool, str]:
        """
        Start a new delivery job if no other job is running.
        Returns: (success: bool, message: str)
        """
        async with self._lock:
            if self._active_job and self._active_job.status == JobStatus.RUNNING:
                return (
                    False,
                    "⚠️ A music delivery job is already running.\n\nUse `/status` to check progress or `/cancel` to stop it.",
                )

            if not tracks:
                return False, f"🔍 No tracks found to deliver for `{query}`."

            job = Job(
                owner_id=owner_id,
                query=query,
                total=len(tracks),
                status=JobStatus.RUNNING,
            )
            self._active_job = job
            self._job_task = asyncio.create_task(
                self._run_job(job, tracks, bot_manager)
            )
            return (
                True,
                f"🚀 Started delivery job `[{job.id}]` for **{len(tracks)}** tracks (`{query}`).",
            )

    async def cancel_active_job(self) -> Tuple[bool, str]:
        """Gracefully cancel the currently running delivery job."""
        async with self._lock:
            if not self._active_job or self._active_job.status != JobStatus.RUNNING:
                return False, "ℹ️ No delivery job is currently running."

            self._active_job.status = JobStatus.CANCELLED
            if self._job_task and not self._job_task.done():
                self._job_task.cancel()

            job_id = self._active_job.id
            return True, f"🛑 Delivery job `[{job_id}]` has been cancelled."

    async def _run_job(
        self,
        job: Job,
        tracks: List[Track],
        bot_manager: Optional[BotManager] = None,
    ) -> None:
        logger.info(f"Starting delivery job {job.id} for {len(tracks)} tracks...")
        last_update_time = datetime.now(timezone.utc)
        items_since_update = 0
        status_msg = None

        # Send initial progress message
        if bot_manager:
            try:
                status_msg = await bot_manager.send_message(
                    job.owner_id, job.format_progress_message()
                )
                job.status_message_id = status_msg.id
            except Exception as e:
                logger.warning(f"Could not send initial job progress message: {e}")

        try:
            for track in tracks:
                if job.status == JobStatus.CANCELLED:
                    logger.info(f"Job {job.id} was cancelled by user.")
                    break

                # Duplicate protection
                if track.message_id in job.delivered_ids:
                    job.skipped += 1
                else:
                    success = await self.delivery_engine.deliver_track(
                        job.owner_id, track
                    )
                    if success:
                        job.completed += 1
                        job.delivered_ids.add(track.message_id)
                    else:
                        job.failed += 1

                items_since_update += 1
                now = datetime.now(timezone.utc)
                elapsed = (now - last_update_time).total_seconds()

                # Throttled progress report
                if (
                    items_since_update >= THROTTLE_TRACK_COUNT
                    or elapsed >= THROTTLE_INTERVAL_SECONDS
                ):
                    if bot_manager and status_msg:
                        try:
                            await bot_manager.edit_message(
                                status_msg, job.format_progress_message()
                            )
                        except Exception as e:
                            logger.debug(f"Progress update edit skipped: {e}")
                    last_update_time = now
                    items_since_update = 0

            if job.status != JobStatus.CANCELLED:
                job.status = JobStatus.COMPLETED
                logger.info(
                    f"Job {job.id} completed: sent={job.completed}, skipped={job.skipped}, failed={job.failed}"
                )

        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            logger.info(f"Job {job.id} caught cancellation.")
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_summary = str(e)
            logger.error(f"Job {job.id} failed with unhandled exception: {e}", exc_info=True)
        finally:
            job.updated_at = datetime.now(timezone.utc)
            # Final message update
            if bot_manager and status_msg:
                try:
                    await bot_manager.edit_message(
                        status_msg, job.format_progress_message()
                    )
                except Exception as e:
                    logger.debug(f"Final progress update edit skipped: {e}")

            # Notify completion
            if bot_manager:
                try:
                    summary = (
                        f"✅ **Job `[{job.id}]` Finished!**\n\n"
                        f"• Delivered: **{job.completed}**\n"
                        f"• Skipped: **{job.skipped}**\n"
                        f"• Failed: **{job.failed}**"
                        if job.status == JobStatus.COMPLETED
                        else f"🛑 **Job `[{job.id}]` Stopped ({job.status.value.title()}).**"
                    )
                    await bot_manager.send_message(job.owner_id, summary)
                except Exception as e:
                    logger.warning(f"Could not send completion message: {e}")

            async with self._lock:
                self._active_job = None
                self._job_task = None
