import pytest
from unittest.mock import AsyncMock, MagicMock
from app.commands.router import CommandRouter
from app.commands.status import StatusCommandHandler
from app.commands.search import SearchCommandHandler
from app.commands.download import DownloadCommandHandler
from app.commands.admin import AdminCommandHandler
from app.index.indexer import MusicIndexer
from app.jobs.manager import JobManager
from app.jobs.delivery import DeliveryEngine
from app.config import Config


class DummyMessage:
    def __init__(self, text: str, sender_id: int = 12345):
        self.text = text
        self.sender_id = sender_id
        self.reply = AsyncMock()


@pytest.fixture
def test_setup():
    indexer = MusicIndexer()
    fake_client = MagicMock()
    delivery_engine = DeliveryEngine(fake_client)
    job_manager = JobManager(delivery_engine)
    conn_manager = MagicMock()
    conn_manager.is_connected = True
    conn_manager.get_status_summary.return_value = {"bot": "connected", "user": "connected"}

    bot_manager = MagicMock()
    bot_manager.send_message = AsyncMock()
    bot_manager.edit_message = AsyncMock()

    cfg = Config(
        api_id=12345,
        api_hash="hash",
        bot_token="token",
        channel_id=-1001,
        telegram_session="session",
        authorized_user_id=12345,
    )

    status_handler = StatusCommandHandler(conn_manager, indexer, job_manager)
    search_handler = SearchCommandHandler(indexer, job_manager)
    download_handler = DownloadCommandHandler(indexer, job_manager, bot_manager)
    admin_handler = AdminCommandHandler(indexer, fake_client, cfg)

    router = CommandRouter(
        status_handler=status_handler,
        search_handler=search_handler,
        download_handler=download_handler,
        admin_handler=admin_handler,
    )
    return router, indexer, job_manager


@pytest.mark.asyncio
async def test_route_start(test_setup):
    router, _, _ = test_setup
    msg = DummyMessage("/start")
    await router.route_message(msg)
    msg.reply.assert_called_once()
    reply_text = msg.reply.call_args[0][0]
    assert "TPMC" in reply_text
    assert "/library" in reply_text


@pytest.mark.asyncio
async def test_route_help(test_setup):
    router, _, _ = test_setup
    msg = DummyMessage("/help")
    await router.route_message(msg)
    msg.reply.assert_called_once()
    reply_text = msg.reply.call_args[0][0]
    assert "Command & Tagging Guide" in reply_text


@pytest.mark.asyncio
async def test_route_status(test_setup):
    router, _, _ = test_setup
    msg = DummyMessage("/status")
    await router.route_message(msg)
    msg.reply.assert_called_once()
    reply_text = msg.reply.call_args[0][0]
    assert "TPMC Status" in reply_text
    assert "**Host:**" in reply_text


@pytest.mark.asyncio
async def test_route_unknown_command(test_setup):
    router, _, _ = test_setup
    msg = DummyMessage("/unknowncommand")
    await router.route_message(msg)
    msg.reply.assert_called_once()
    reply_text = msg.reply.call_args[0][0]
    assert "Unknown command" in reply_text


@pytest.mark.asyncio
async def test_route_reindex_requires_confirm(test_setup):
    router, _, _ = test_setup
    msg = DummyMessage("/reindex")
    await router.route_message(msg)
    msg.reply.assert_called_once()
    reply_text = msg.reply.call_args[0][0]
    assert "Re-index Confirmation Required" in reply_text
    assert "/reindex confirm" in reply_text


@pytest.mark.asyncio
async def test_route_download_all_requires_confirm(test_setup):
    router, _, _ = test_setup
    msg = DummyMessage("/download_all")
    await router.route_message(msg)
    msg.reply.assert_called_once()
    reply_text = msg.reply.call_args[0][0]
    assert "Bulk Download Confirmation Required" in reply_text
    assert "/download_all confirm" in reply_text


@pytest.mark.asyncio
async def test_route_keyboard_buttons(test_setup):
    router, _, _ = test_setup
    # Test Library button
    msg_lib = DummyMessage("📚 My Library")
    await router.route_message(msg_lib)
    msg_lib.reply.assert_called_once()
    assert "Music Library Overview" in msg_lib.reply.call_args[0][0]

    # Test Cloud Status button
    msg_status = DummyMessage("⚡ Cloud Status")
    await router.route_message(msg_status)
    msg_status.reply.assert_called_once()
    assert "TPMC Status" in msg_status.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_route_natural_search(test_setup):
    router, indexer, _ = test_setup
    from app.index.models import Track
    indexer.add_track(
        Track(
            message_id=99,
            channel_id=-1001,
            title="Viva La Vida",
            performer="Coldplay",
            album="Viva La Vida",
        )
    )

    msg = DummyMessage("coldplay")
    await router.route_message(msg)
    msg.reply.assert_called_once()
    reply_text = msg.reply.call_args[0][0]
    assert "Viva La Vida" in reply_text


@pytest.mark.asyncio
async def test_callback_single_track_delivery(test_setup):
    router, indexer, job_manager = test_setup
    from app.index.models import Track
    indexer.add_track(
        Track(
            message_id=42,
            channel_id=-1001,
            title="Yellow",
            performer="Coldplay",
            album="Parachutes",
        )
    )

    job_manager.delivery_engine.deliver_track = AsyncMock(return_value=True)

    fake_event = MagicMock()
    fake_event.data = b"s:one:42"
    fake_event.sender_id = 12345
    fake_event.answer = AsyncMock()

    await router.route_callback(fake_event)
    fake_event.answer.assert_called_once()
    assert "Yellow" in fake_event.answer.call_args[0][0]
    job_manager.delivery_engine.deliver_track.assert_called_once()


@pytest.mark.asyncio
async def test_callback_library_explorer(test_setup):
    router, indexer, _ = test_setup
    from app.index.models import Track
    indexer.add_track(
        Track(
            message_id=10,
            channel_id=-1001,
            title="Fix You",
            performer="Coldplay",
            album="X&Y",
            genre="Alternative",
        )
    )

    fake_event = MagicMock()
    fake_event.data = b"lib:artists"
    fake_event.edit = AsyncMock()
    fake_event.answer = AsyncMock()

    await router.route_callback(fake_event)
    fake_event.edit.assert_called_once()
    edited_text = fake_event.edit.call_args[0][0]
    assert "Top Artists" in edited_text
    assert "Coldplay" in edited_text


@pytest.mark.asyncio
async def test_callback_surprise_me(test_setup):
    router, indexer, _ = test_setup
    from app.index.models import Track
    indexer.add_track(
        Track(
            message_id=55,
            channel_id=-1001,
            title="Paradise",
            performer="Coldplay",
            album="Mylo Xyloto",
        )
    )

    fake_event = MagicMock()
    fake_event.data = b"lib:random"
    fake_event.edit = AsyncMock()
    fake_event.answer = AsyncMock()

    await router.route_callback(fake_event)
    fake_event.edit.assert_called_once()
    edited_text = fake_event.edit.call_args[0][0]
    assert "Surprise Track Pick" in edited_text
    assert "Paradise" in edited_text


@pytest.mark.asyncio
async def test_callback_album_search(test_setup):
    router, indexer, _ = test_setup
    from app.index.models import Track
    indexer.add_track(
        Track(
            message_id=77,
            channel_id=-1001,
            title="A Vachi B Padi",
            performer="Mathangi",
            album="Chatrapathi",
        )
    )

    fake_event = MagicMock()
    fake_event.data = b"s:p:1:album:Chatrapathi"
    fake_event.edit = AsyncMock()
    fake_event.answer = AsyncMock()

    await router.route_callback(fake_event)
    fake_event.edit.assert_called_once()
    edited_text = fake_event.edit.call_args[0][0]
    assert "A Vachi B Padi" in edited_text
