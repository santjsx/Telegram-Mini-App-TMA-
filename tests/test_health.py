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
