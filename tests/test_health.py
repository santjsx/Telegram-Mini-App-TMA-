import pytest
from aiohttp.test_utils import TestClient, TestServer
from app.health.server import HealthServer


@pytest.mark.asyncio
async def test_health_server_root():
    server = HealthServer()
    test_server = TestServer(server.app)
    client = TestClient(test_server)
    await client.start_server()

    try:
        resp = await client.get("/")
        assert resp.status == 200
        text = await resp.text()
        assert "TPMC ONLINE" in text
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_health_server_health_callback():
    status_data = {
        "status": "ok",
        "telegram": "connected",
        "bot": "connected",
        "index": "ready",
        "tracks": 42,
    }
    server = HealthServer(status_provider=lambda: status_data)
    test_server = TestServer(server.app)
    client = TestClient(test_server)
    await client.start_server()

    try:
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
        assert data["telegram"] == "connected"
        assert data["bot"] == "connected"
        assert data["index"] == "ready"
        assert data["tracks"] == 42
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_bot_flood_wait_fault_tolerance():
    from unittest.mock import AsyncMock, MagicMock
    from telethon.errors import FloodWaitError
    from app.telegram.connection import TelegramConnectionManager, ConnectionState
    from app.config import Config

    cfg = Config(
        api_id=12345,
        api_hash="hash",
        bot_token="token",
        channel_id=-1001,
        telegram_session="session",
        authorized_user_id=12345,
    )

    conn_mgr = TelegramConnectionManager(cfg)

    # Mock BotManager that raises FloodWaitError (e.g. 1500s)
    mock_bot = MagicMock()
    flood_err = FloodWaitError(request=None)
    flood_err.seconds = 1500
    mock_bot.connect = AsyncMock(side_effect=flood_err)
    mock_bot.disconnect = AsyncMock()

    # Mock UserClientManager that connects normally
    mock_user = MagicMock()
    mock_user.connect = AsyncMock()
    mock_user.disconnect = AsyncMock()

    # connect_all must complete without crashing
    await conn_mgr.connect_all(mock_bot, mock_user)

    # Bot should be in RECONNECTING state, user should be CONNECTED
    assert conn_mgr.bot_state == ConnectionState.RECONNECTING
    assert conn_mgr.user_state == ConnectionState.CONNECTED

    summary = conn_mgr.get_status_summary()
    assert summary["user"] == "connected"
    assert "reconnecting" in summary["bot"]
    assert "1500" in summary["bot"]
    assert summary["overall"] == "degraded"

    # Health server must return HTTP 200 OK
    server = HealthServer(status_provider=lambda: summary)
    test_server = TestServer(server.app)
    client = TestClient(test_server)
    await client.start_server()

    try:
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["user"] == "connected"
        assert "reconnecting" in data["bot"]
    finally:
        await client.close()
        await conn_mgr.disconnect_all()


@pytest.mark.asyncio
async def test_user_auth_failed_fault_tolerance():
    from unittest.mock import AsyncMock, MagicMock
    from telethon.errors import AuthKeyDuplicatedError
    from app.telegram.connection import TelegramConnectionManager, ConnectionState
    from app.config import Config

    cfg = Config(
        api_id=12345,
        api_hash="hash",
        bot_token="token",
        channel_id=-1001,
        telegram_session="session",
        authorized_user_id=12345,
    )

    conn_mgr = TelegramConnectionManager(cfg)

    # Mock Bot that connects normally
    mock_bot = MagicMock()
    mock_bot.connect = AsyncMock()
    mock_bot.disconnect = AsyncMock()

    # Mock User client that raises AuthKeyDuplicatedError (multi-IP collision)
    mock_user = MagicMock()
    dup_err = AuthKeyDuplicatedError(request=None)
    mock_user.connect = AsyncMock(side_effect=dup_err)
    mock_user.disconnect = AsyncMock()

    # connect_all must complete gracefully without raising
    await conn_mgr.connect_all(mock_bot, mock_user)

    assert conn_mgr.bot_state == ConnectionState.CONNECTED
    assert conn_mgr.user_state == ConnectionState.AUTH_FAILED
    assert conn_mgr.user_error is not None

    summary = conn_mgr.get_status_summary()
    assert summary["bot"] == "connected"
    assert "auth_failed" in summary["user"]
    assert summary["overall"] == "degraded"

    # Health server MUST return HTTP 200 OK (Render health checks will succeed!)
    server = HealthServer(status_provider=lambda: summary)
    test_server = TestServer(server.app)
    client = TestClient(test_server)
    await client.start_server()

    try:
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["overall"] == "degraded"
        assert "auth_failed" in data["user"]
    finally:
        await client.close()
        await conn_mgr.disconnect_all()


