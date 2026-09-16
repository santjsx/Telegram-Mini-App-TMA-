import pytest
import hmac
import hashlib
import json
import urllib.parse
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from aiohttp.test_utils import TestClient, TestServer

from app.health.server import HealthServer, verify_telegram_init_data
from app.auth.manager import AccessManager
from app.index.indexer import MusicIndexer
from app.index.models import Track
from app.config import Config


def generate_mock_init_data(user_id: int, bot_token: str) -> str:
    """Generate cryptographically valid Telegram initData query string for testing."""
    user_data = json.dumps({"id": user_id, "first_name": "Tester", "username": "tester"})
    data_dict = {
        "auth_date": "1700000000",
        "query_id": "AAHdF6IQAAAAAN0XohD12345",
        "user": user_data,
    }
    sorted_items = [f"{k}={v}" for k, v in sorted(data_dict.items())]
    data_check_string = "\n".join(sorted_items)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    data_dict["hash"] = computed_hash
    return urllib.parse.urlencode(data_dict)


@pytest.fixture
def mock_config():
    return Config(
        api_id=1234567,
        api_hash="abcdef0123456789abcdef0123456789",
        bot_token="1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ",
        channel_id=-1001234567890,
        telegram_session="mock_session",
        authorized_user_id=12345,
        port=8080,
    )


@pytest.fixture
def populated_indexer():
    indexer = MusicIndexer()
    track = Track(
        message_id=101,
        channel_id=-1001234567890,
        title="Midnight City",
        performer="M83",
        album="Hurry Up, We're Dreaming",
        duration=244,
        file_size=8388608,
        mime_type="audio/mp3",
        filename="midnight_city.mp3",
        genre="Synthwave",
        is_favorite=True,
    )
    indexer.add_track(track)
    return indexer


@pytest.mark.asyncio
async def test_init_data_verification(mock_config):
    bot_token = mock_config.bot_token
    valid_init_data = generate_mock_init_data(12345, bot_token)

    # Valid data
    user = verify_telegram_init_data(valid_init_data, bot_token)
    assert user is not None
    assert user["id"] == 12345
    assert user["username"] == "tester"

    # Tampered data
    tampered = valid_init_data.replace("12345", "99999")
    assert verify_telegram_init_data(tampered, bot_token) is None

    # Empty string
    assert verify_telegram_init_data("", bot_token) is None


@pytest.mark.asyncio
async def test_webapp_serves_html_and_static(mock_config):
    server = HealthServer(config=mock_config)
    test_server = TestServer(server.app)
    client = TestClient(test_server)
    await client.start_server()

    try:
        # GET /
        resp = await client.get("/")
        assert resp.status == 200
        text = await resp.text()
        assert "TPMC ONLINE" in text
        assert "audio-engine" in text

        # GET /static/style.css
        resp_css = await client.get("/static/style.css")
        assert resp_css.status == 200
        css_text = await resp_css.text()
        assert "--accent-pink" in css_text

        # GET /static/app.js
        resp_js = await client.get("/static/app.js")
        assert resp_js.status == 200
        js_text = await resp_js.text()
        assert "fetchLibrary" in js_text
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_library_authorized_via_init_data(mock_config, populated_indexer, tmp_path):
    access_file = tmp_path / "access.json"
    access_mgr = AccessManager(admin_id=12345, persistence_path=str(access_file))
    server = HealthServer(
        config=mock_config,
        indexer=populated_indexer,
        access_manager=access_mgr,
    )
    test_server = TestServer(server.app)
    client = TestClient(test_server)
    await client.start_server()

    try:
        init_data = generate_mock_init_data(12345, mock_config.bot_token)
        headers = {"X-Telegram-Init-Data": init_data}

        resp = await client.get("/api/library", headers=headers)
        assert resp.status == 200
        data = await resp.json()
        assert data["total_tracks"] == 1
        assert len(data["tracks"]) == 1
        assert data["tracks"][0]["title"] == "Midnight City"
        assert data["tracks"][0]["artist"] == "M83"
        assert data["tracks"][0]["id"] == 101
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_library_unauthorized_rejected(mock_config, populated_indexer, tmp_path):
    access_file = tmp_path / "access.json"
    access_mgr = AccessManager(admin_id=12345, persistence_path=str(access_file))
    server = HealthServer(
        config=mock_config,
        indexer=populated_indexer,
        access_manager=access_mgr,
    )
    test_server = TestServer(server.app)
    client = TestClient(test_server)
    await client.start_server()

    try:
        # User 99999 is unauthorized
        init_data = generate_mock_init_data(99999, mock_config.bot_token)
        headers = {"X-Telegram-Init-Data": init_data}

        resp = await client.get("/api/library", headers=headers)
        assert resp.status == 403
        data = await resp.json()
        assert data["error"] == "unauthorized"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_stream_info(mock_config, populated_indexer, tmp_path):
    access_file = tmp_path / "access.json"
    access_mgr = AccessManager(admin_id=12345, persistence_path=str(access_file))

    mock_user_client = AsyncMock()
    mock_msg = MagicMock()
    mock_msg.document = MagicMock()
    mock_msg.document.size = 8388608
    mock_msg.document.mime_type = "audio/mp3"

    async def fake_get_message(mid):
        if mid == 101:
            return mock_msg
        return None

    mock_user_client.get_message = AsyncMock(side_effect=fake_get_message)

    server = HealthServer(
        config=mock_config,
        indexer=populated_indexer,
        access_manager=access_mgr,
        user_client=mock_user_client,
    )
    test_server = TestServer(server.app)
    client = TestClient(test_server)
    await client.start_server()

    try:
        # Authorized request for existing track
        resp = await client.get("/api/stream-info/101?user_id=12345")
        assert resp.status == 200
        info = await resp.json()
        assert info["id"] == 101
        assert info["size"] == 8388608
        assert info["mime_type"] == "audio/mp3"

        # Nonexistent track
        resp_404 = await client.get("/api/stream-info/9999?user_id=12345")
        assert resp_404.status == 404

        # Unauthorized request
        resp_403 = await client.get("/api/stream-info/101?user_id=88888")
        assert resp_403.status == 403
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_artwork_serving(mock_config, populated_indexer, tmp_path):
    # Setup dummy cached artwork
    cache_dir = Path("data/artwork_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    test_art_file = cache_dir / "101.jpg"
    test_art_file.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 50)

    server = HealthServer(config=mock_config, indexer=populated_indexer)
    test_server = TestServer(server.app)
    client = TestClient(test_server)
    await client.start_server()

    try:
        resp = await client.get("/api/artwork/101")
        assert resp.status == 200
        assert resp.headers["Content-Type"] == "image/jpeg"
        body = await resp.read()
        assert body.startswith(b"\xFF\xD8\xFF\xE0")

        # Invalid ID
        resp_inv = await client.get("/api/artwork/abc")
        assert resp_inv.status == 400

        # Nonexistent without user_client
        resp_404 = await client.get("/api/artwork/999999")
        assert resp_404.status == 404
    finally:
        await client.close()
        if test_art_file.exists():
            test_art_file.unlink()


@pytest.mark.asyncio
async def test_api_stream_range_and_cache(mock_config, populated_indexer):
    mock_user_client = AsyncMock()
    mock_msg = MagicMock()
    mock_msg.document = MagicMock()
    mock_msg.document.size = 1000000
    mock_msg.document.mime_type = "audio/mpeg"

    async def fake_get_message(mid):
        if mid == 101:
            return mock_msg
        return None

    mock_user_client.get_message = AsyncMock(side_effect=fake_get_message)

    # Simulated iter_download that yields 128KB chunks
    async def fake_iter_download(doc, offset=0, request_size=None, chunk_size=128*1024):
        # Yield dummy bytes corresponding to offset
        bytes_left = request_size or doc.size
        curr = offset
        while bytes_left > 0:
            take = min(bytes_left, chunk_size)
            yield b"X" * take
            curr += take
            bytes_left -= take

    mock_user_client.client = MagicMock()
    mock_user_client.client.iter_download = fake_iter_download

    server = HealthServer(
        config=mock_config,
        indexer=populated_indexer,
        user_client=mock_user_client,
    )
    test_server = TestServer(server.app)
    client = TestClient(test_server)
    await client.start_server()

    try:
        # 1. Test probe request Range: bytes=0-1
        resp = await client.get("/api/stream/101?user_id=12345", headers={"Range": "bytes=0-1"})
        assert resp.status == 206
        assert resp.headers["Content-Range"] == "bytes 0-1/1000000"
        assert resp.headers["Content-Length"] == "2"
        body = await resp.read()
        assert len(body) == 2

        # 2. Test seeking with unaligned offset Range: bytes=150000-200000
        resp_seek = await client.get("/api/stream/101?user_id=12345", headers={"Range": "bytes=150000-200000"})
        assert resp_seek.status == 206
        assert resp_seek.headers["Content-Range"] == "bytes 150000-200000/1000000"
        assert resp_seek.headers["Content-Length"] == str(200000 - 150000 + 1)
        seek_body = await resp_seek.read()
        assert len(seek_body) == (200000 - 150000 + 1)

        # 3. Test that header cache accelerates subsequent start requests
        server._audio_header_cache[101] = b"A" * 65536
        resp_cached = await client.get("/api/stream/101?user_id=12345", headers={"Range": "bytes=0-100"})
        assert resp_cached.status == 206
        cached_body = await resp_cached.read()
        assert len(cached_body) == 101
        assert cached_body == b"A" * 101
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_stream_prefetch(mock_config, populated_indexer):
    mock_user_client = AsyncMock()
    mock_msg = MagicMock()
    mock_msg.document = MagicMock()
    mock_msg.document.size = 500000
    mock_msg.document.mime_type = "audio/mpeg"

    async def fake_get_message(mid):
        if mid == 101:
            return mock_msg
        return None

    mock_user_client.get_message = AsyncMock(side_effect=fake_get_message)

    server = HealthServer(
        config=mock_config,
        indexer=populated_indexer,
        user_client=mock_user_client,
    )
    test_server = TestServer(server.app)
    client = TestClient(test_server)
    await client.start_server()

    try:
        # 1. First prefetch when not cached
        resp = await client.get("/api/stream/prefetch/101?user_id=12345")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] in ("prefetching", "ready")
        assert data["message_id"] == 101

        # 2. When header is cached, prefetch returns ready
        server._audio_header_cache[101] = b"XYZ" * 100
        resp_cached = await client.post("/api/stream/prefetch/101?user_id=12345")
        assert resp_cached.status == 200
        data_cached = await resp_cached.json()
        assert data_cached["status"] == "ready"
        assert data_cached["cached"] is True
    finally:
        await client.close()


