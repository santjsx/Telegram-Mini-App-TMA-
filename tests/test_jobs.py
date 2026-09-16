import pytest
import asyncio
from app.jobs.models import Job, JobStatus
from app.jobs.manager import JobManager
from app.jobs.delivery import DeliveryEngine
from app.index.models import Track


class FakeUserClient:
    async def forward_media(self, to_peer: int, message_ids: list[int]):
        # Simulate successful forwarding
        await asyncio.sleep(0.01)
        return []


def test_job_progress_calculation():
    job = Job(id="test1", total=10, completed=5, skipped=2, failed=1)
    # (5 + 2 + 1) / 10 = 80%
    assert job.progress_pct == 80
    bar = job.progress_bar
    assert len(bar) == 16
    assert "█" in bar
    assert "░" in bar


@pytest.mark.asyncio
async def test_job_manager_concurrency_and_collision():
    fake_client = FakeUserClient()
    delivery_engine = DeliveryEngine(fake_client)
    manager = JobManager(delivery_engine)

    tracks = [
        Track(message_id=i, channel_id=-1001, title=f"Track {i}", performer="Artist")
        for i in range(1, 4)
    ]

    # Start first job
    success1, msg1 = await manager.start_delivery_job(
        owner_id=123,
        query="test query",
        tracks=tracks,
    )
    assert success1 is True
    assert "Started delivery job" in msg1

    # Attempt second job while first is running -> should be rejected
    success2, msg2 = await manager.start_delivery_job(
        owner_id=123,
        query="second query",
        tracks=tracks,
    )
    assert success2 is False
    assert "already running" in msg2

    # Cancel first job
    can_success, can_msg = await manager.cancel_active_job()
    assert can_success is True
    assert "cancelled" in can_msg
