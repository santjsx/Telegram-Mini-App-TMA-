import pytest
import asyncio
from telethon.errors import FloodWaitError
from app.jobs.retry import retry_telegram_operation


@pytest.mark.asyncio
async def test_retry_success_first_attempt():
    calls = 0

    async def op():
        nonlocal calls
        calls += 1
        return "success"

    res = await retry_telegram_operation(op, max_retries=3)
    assert res == "success"
    assert calls == 1


@pytest.mark.asyncio
async def test_retry_transient_connection_error():
    calls = 0

    async def op():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError("Connection lost")
        return "recovered"

    res = await retry_telegram_operation(op, max_retries=3, base_backoff=0.01)
    assert res == "recovered"
    assert calls == 3


@pytest.mark.asyncio
async def test_retry_permanent_connection_failure():
    async def op():
        raise ConnectionError("Unreachable network")

    with pytest.raises(ConnectionError):
        await retry_telegram_operation(op, max_retries=2, base_backoff=0.01)


@pytest.mark.asyncio
async def test_flood_wait_exceeds_max_raises():
    async def op():
        # FloodWaitError takes a request and seconds (or mock seconds)
        err = FloodWaitError(request=None)
        err.seconds = 500
        raise err

    with pytest.raises(FloodWaitError):
        await retry_telegram_operation(op, flood_wait_max=300)


from app.jobs.delivery import DeliveryEngine
from app.index.models import Track


class MockBotManager:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.forwarded = []

    async def forward_media(self, to_peer: int, from_peer: int, message_ids: list[int]):
        if self.should_fail:
            raise RuntimeError("Bot forward forbidden")
        self.forwarded.append((to_peer, from_peer, message_ids))
        return []


class MockUserClient:
    def __init__(self):
        self.forwarded = []

    async def forward_media(self, to_peer: int, message_ids: list[int]):
        self.forwarded.append((to_peer, message_ids))
        return []


@pytest.mark.asyncio
async def test_delivery_engine_prefers_bot_forwarding(monkeypatch):
    monkeypatch.setattr("app.jobs.delivery.PACING_DELAY_SECONDS", 0.0)
    mock_bot = MockBotManager(should_fail=False)
    mock_user = MockUserClient()
    engine = DeliveryEngine(user_client=mock_user, bot_manager=mock_bot)

    track = Track(message_id=42, channel_id=-1001, title="Test Song", performer="Artist")
    success = await engine.deliver_track(owner_id=999, track=track)

    assert success is True
    assert len(mock_bot.forwarded) == 1
    assert mock_bot.forwarded[0] == (999, -1001, [42])
    # User client should not be called because bot forward succeeded
    assert len(mock_user.forwarded) == 0


@pytest.mark.asyncio
async def test_delivery_engine_falls_back_to_user_client_on_bot_failure(monkeypatch):
    monkeypatch.setattr("app.jobs.delivery.PACING_DELAY_SECONDS", 0.0)
    mock_bot = MockBotManager(should_fail=True)
    mock_user = MockUserClient()
    engine = DeliveryEngine(user_client=mock_user, bot_manager=mock_bot)

    track = Track(message_id=42, channel_id=-1001, title="Test Song", performer="Artist")
    success = await engine.deliver_track(owner_id=999, track=track)

    assert success is True
    # User client was called as fallback
    assert len(mock_user.forwarded) == 1
    assert mock_user.forwarded[0] == (999, [42])


@pytest.mark.asyncio
async def test_delivery_engine_without_bot_manager(monkeypatch):
    monkeypatch.setattr("app.jobs.delivery.PACING_DELAY_SECONDS", 0.0)
    mock_user = MockUserClient()
    engine = DeliveryEngine(user_client=mock_user, bot_manager=None)

    track = Track(message_id=42, channel_id=-1001, title="Test Song", performer="Artist")
    success = await engine.deliver_track(owner_id=999, track=track)

    assert success is True
    assert len(mock_user.forwarded) == 1
    assert mock_user.forwarded[0] == (999, [42])
