import pytest
from unittest.mock import AsyncMock, MagicMock
from app.commands.router import CommandRouter
from app.commands.status import StatusCommandHandler
from app.commands.search import SearchCommandHandler
from app.commands.download import DownloadCommandHandler
from app.commands.admin import AdminCommandHandler
from app.commands.explorer import ExplorerCommandHandler
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
    explorer_handler = ExplorerCommandHandler(indexer, job_manager, search_handler)

    router = CommandRouter(
        status_handler=status_handler,
        search_handler=search_handler,
        download_handler=download_handler,
        admin_handler=admin_handler,
        explorer_handler=explorer_handler,
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
    if fake_event.respond.called:
        called_text = fake_event.respond.call_args[0][0]
        assert "A Vachi B Padi" in called_text
        assert "file" in fake_event.respond.call_args[1]
    else:
        fake_event.edit.assert_called_once()
        edited_text = fake_event.edit.call_args[0][0]
        assert "A Vachi B Padi" in edited_text


@pytest.mark.asyncio
async def test_callback_albums_pagination(test_setup):
    router, indexer, _ = test_setup
    from app.index.models import Track

    # Add 15 distinct albums
    for i in range(1, 16):
        indexer.add_track(
            Track(
                message_id=100 + i,
                channel_id=-1001,
                title=f"Track {i}",
                performer=f"Artist {i}",
                album=f"Album {i:02d}",
            )
        )

    # Page 1
    event_p1 = MagicMock()
    event_p1.data = b"lib:albums"
    event_p1.edit = AsyncMock()
    event_p1.answer = AsyncMock()

    await router.route_callback(event_p1)
    event_p1.edit.assert_called_once()
    text_p1 = event_p1.edit.call_args[0][0]
    buttons_p1 = event_p1.edit.call_args[1]["buttons"]

    assert "Albums in Your Library" in text_p1
    assert "Page **1** of **2**" in text_p1
    assert "15 total" in text_p1
    assert "Album 01" in text_p1
    # Check that Next button exists
    all_btn_data = [
        btn.type.data.decode("utf-8")
        for row in buttons_p1
        for btn in row
        if hasattr(btn, "type") and hasattr(btn.type, "data") and btn.type.data
    ]
    assert "lib:albums:2" in all_btn_data

    # Page 2
    event_p2 = MagicMock()
    event_p2.data = b"lib:albums:2"
    event_p2.edit = AsyncMock()
    event_p2.answer = AsyncMock()

    await router.route_callback(event_p2)
    event_p2.edit.assert_called_once()
    text_p2 = event_p2.edit.call_args[0][0]
    buttons_p2 = event_p2.edit.call_args[1]["buttons"]

    assert "Page **2** of **2**" in text_p2
    assert "Album 15" in text_p2
    all_btn_data_p2 = [
        btn.type.data.decode("utf-8")
        for row in buttons_p2
        for btn in row
        if hasattr(btn, "type") and hasattr(btn.type, "data") and btn.type.data
    ]
    assert "lib:albums:1" in all_btn_data_p2


@pytest.mark.asyncio
async def test_route_albums_button_and_command(test_setup):
    router, indexer, _ = test_setup
    from app.index.models import Track
    indexer.add_track(
        Track(
            message_id=200,
            channel_id=-1001,
            title="Song",
            performer="Singer",
            album="Masterpiece",
        )
    )

    # Reply keyboard button "💿 Albums"
    msg_btn = DummyMessage("💿 Albums")
    await router.route_message(msg_btn)
    msg_btn.reply.assert_called_once()
    assert "Albums in Your Library" in msg_btn.reply.call_args[0][0]
    assert "Masterpiece" in msg_btn.reply.call_args[0][0]

    # Slash command "/albums"
    msg_cmd = DummyMessage("/albums")
    await router.route_message(msg_cmd)
    msg_cmd.reply.assert_called_once()
    assert "Albums in Your Library" in msg_cmd.reply.call_args[0][0]
    assert "Masterpiece" in msg_cmd.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_search_format_page_layout(test_setup):
    router, indexer, job_manager = test_setup
    from app.index.models import Track
    from app.index.search import SearchEngine

    tracks = [
        Track(
            message_id=1,
            channel_id=-1001,
            title="5.RAYALASEEMA MUDDU BIDDA",
            performer="Dj Mahendar",
            album="Remix Album",
            duration=220,
            file_size=3800000,
            mime_type="audio/mpeg",
        ),
        Track(
            message_id=2,
            channel_id=-1001,
            title="01 - Annochadu Song",
            performer="Jagananna Connects",
            album="Jagan",
            duration=278,
            file_size=36500000,
            mime_type="audio/flac",
            is_favorite=True,
        ),
    ]
    for t in tracks:
        indexer.add_track(t)

    search_handler = SearchCommandHandler(indexer, job_manager)
    res = SearchEngine.search("", tracks, page=1, page_size=6)
    text, buttons = search_handler._format_page(res)

    # Check that ugly prefix "5." and "01 - " were stripped
    assert "RAYALASEEMA MUDDU BIDDA" in text
    assert "5.RAYALASEEMA" not in text
    assert "Annochadu Song" in text
    assert "01 - Annochadu" not in text

    # Check emojis and badges
    assert "🎧" in text
    assert "👤 *Dj Mahendar*" in text
    assert "🎵 MP3" in text
    assert "💎 FLAC" in text
    assert "⭐" in text  # Track 2 is favorite

    # Check button layout: 2 per row
    # Row 0: 2 track buttons
    assert len(buttons[0]) == 2
    btn1_text = buttons[0][0].text
    btn2_text = buttons[0][1].text
    assert "📥 1. RAYALASEEMA" in btn1_text
    assert "📥 2. Annochadu" in btn2_text


@pytest.mark.asyncio
async def test_route_explorer(test_setup):
    router, indexer, _ = test_setup
    from app.index.models import Track
    indexer.add_track(
        Track(message_id=1, channel_id=-1001, title="Song", performer="Artist", album="Album")
    )

    # Message button "📁 File Explorer"
    msg = DummyMessage("📁 File Explorer")
    await router.route_message(msg)
    msg.reply.assert_called_once()
    reply_text = msg.reply.call_args[0][0]
    assert "Music Cloud Explorer" in reply_text
    assert "Artists" in reply_text

    # Slash command "/explore"
    msg_cmd = DummyMessage("/explore")
    await router.route_message(msg_cmd)
    msg_cmd.reply.assert_called_once()
    assert "Music Cloud Explorer" in msg_cmd.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_callback_explorer_az(test_setup):
    router, indexer, _ = test_setup
    fake_event = MagicMock()
    fake_event.data = b"exp:az:art"
    fake_event.edit = AsyncMock()
    fake_event.answer = AsyncMock()

    await router.route_callback(fake_event)
    fake_event.edit.assert_called_once()
    edited_text = fake_event.edit.call_args[0][0]
    assert "A–Z Alphabet Index" in edited_text
    assert "Artists" in edited_text


@pytest.mark.asyncio
async def test_callback_explorer_artist_drilldown(test_setup):
    router, indexer, _ = test_setup
    from app.index.models import Track
    indexer.add_track(
        Track(message_id=1, channel_id=-1001, title="Yellow", performer="Coldplay", album="Parachutes")
    )
    indexer.add_track(
        Track(message_id=2, channel_id=-1001, title="Fix You", performer="Coldplay", album="X&Y")
    )

    fake_event = MagicMock()
    fake_event.data = b"exp:art_v:Coldplay"
    fake_event.edit = AsyncMock()
    fake_event.answer = AsyncMock()

    await router.route_callback(fake_event)
    fake_event.edit.assert_called_once()
    edited_text = fake_event.edit.call_args[0][0]
    assert "Coldplay" in edited_text
    assert "Parachutes" in edited_text
    assert "X&Y" in edited_text
    assert "Discography" in edited_text


@pytest.mark.asyncio
async def test_callback_explorer_lossless(test_setup):
    router, indexer, _ = test_setup
    from app.index.models import Track
    indexer.add_track(
        Track(message_id=1, channel_id=-1001, title="Clocks", performer="Coldplay", mime_type="audio/flac")
    )

    fake_event = MagicMock()
    fake_event.data = b"exp:lossless"
    fake_event.edit = AsyncMock()
    fake_event.answer = AsyncMock()

    await router.route_callback(fake_event)
    fake_event.edit.assert_called_once()
    edited_text = fake_event.edit.call_args[0][0]
    assert "Lossless Audio Collection" in edited_text
    assert "Clocks" in edited_text
    assert "💎 FLAC" in edited_text


@pytest.mark.asyncio
async def test_callback_audio_specs_and_toggle_favorite(test_setup):
    router, indexer, _ = test_setup
    from app.index.models import Track
    indexer.add_track(
        Track(
            message_id=99,
            channel_id=-1001,
            title="Viva La Vida",
            performer="Coldplay",
            album="Viva La Vida",
            duration=242,
            file_size=8500000,
            mime_type="audio/mpeg",
            is_favorite=False,
        )
    )

    # 1. Test Audio Specs Inspector callback
    fake_event_info = MagicMock()
    fake_event_info.data = b"s:info:99:coldplay"
    fake_event_info.edit = AsyncMock()
    fake_event_info.answer = AsyncMock()

    await router.route_callback(fake_event_info)
    fake_event_info.edit.assert_called_once()
    specs_text = fake_event_info.edit.call_args[0][0]
    assert "Audio Specs & File Inspector" in specs_text
    assert "Viva La Vida" in specs_text
    assert "Coldplay" in specs_text
    assert "8.1 MB" in specs_text or "8.5" in specs_text or "8." in specs_text
    assert "🎵 MP3" in specs_text

    # 2. Test 1-Tap Toggle Favorite callback (turn ON)
    fake_event_fav = MagicMock()
    fake_event_fav.data = b"s:fav:99:coldplay"
    fake_event_fav.edit = AsyncMock()
    fake_event_fav.answer = AsyncMock()

    await router.route_callback(fake_event_fav)
    track = indexer.get_track(99)
    assert track.is_favorite is True
    fake_event_fav.answer.assert_called_once()
    assert "Added to Favorites" in fake_event_fav.answer.call_args[0][0]

    # 3. Toggle favorite OFF
    await router.route_callback(fake_event_fav)
    assert track.is_favorite is False


@pytest.mark.asyncio
async def test_handle_inline_query(test_setup):
    router, indexer, job_manager = test_setup
    from app.index.models import Track
    indexer.add_track(
        Track(
            message_id=77,
            channel_id=-1001,
            title="Yellow",
            performer="Coldplay",
            album="Parachutes",
            duration=269,
            file_size=6500000,
            mime_type="audio/mpeg",
        )
    )

    search_handler = SearchCommandHandler(indexer, job_manager)

    fake_inline_event = MagicMock()
    fake_inline_event.text = "yellow"
    fake_inline_event.answer = AsyncMock()
    fake_inline_event.builder = MagicMock()
    fake_inline_event.builder.article = MagicMock(return_value="mock_article")

    await search_handler.handle_inline_query(fake_inline_event)

    fake_inline_event.builder.article.assert_called_once()
    kwargs = fake_inline_event.builder.article.call_args[1]
    assert "Yellow" in kwargs["title"]
    assert "Coldplay" in kwargs["description"]
    assert "Yellow" in kwargs["text"]
    assert "mock_article" in fake_inline_event.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_callback_basket_multi_select(test_setup):
    router, indexer, job_manager = test_setup
    from app.index.models import Track
    indexer.add_track(
        Track(message_id=1, channel_id=-1001, title="Song One", performer="Artist")
    )
    indexer.add_track(
        Track(message_id=2, channel_id=-1001, title="Song Two", performer="Artist")
    )

    # 1. Enter basket selection mode
    event_enter = MagicMock()
    event_enter.data = b"s:b:1:0:0:artist"
    event_enter.edit = AsyncMock()
    event_enter.answer = AsyncMock()

    await router.route_callback(event_enter)
    event_enter.edit.assert_called_once()
    text_enter = event_enter.edit.call_args[0][0]
    buttons_enter = event_enter.edit.call_args[1]["buttons"]
    assert "Selection Mode" in text_enter
    # Both checkboxes should be empty ⬜
    assert "⬜ 1." in buttons_enter[0][0].text
    assert "⬜ 2." in buttons_enter[0][1].text

    # 2. Toggle track 1 checkbox (bit 0 -> mask becomes 1)
    event_toggle = MagicMock()
    event_toggle.data = b"s:b:1:0:1:artist"
    event_toggle.edit = AsyncMock()
    event_toggle.answer = AsyncMock()

    await router.route_callback(event_toggle)
    event_toggle.edit.assert_called_once()
    buttons_toggle = event_toggle.edit.call_args[1]["buttons"]
    assert "☑️ 1." in buttons_toggle[0][0].text
    assert "⬜ 2." in buttons_toggle[0][1].text

    # 3. Download selected track
    job_manager.start_delivery_job = AsyncMock()
    event_dl = MagicMock()
    event_dl.data = b"s:bdl:1:1:artist"
    event_dl.sender_id = 12345
    event_dl.answer = AsyncMock()

    await router.route_callback(event_dl)
    event_dl.answer.assert_called_once()
    assert "Queued 1" in event_dl.answer.call_args[0][0]
    job_manager.start_delivery_job.assert_called_once()
    dl_tracks = job_manager.start_delivery_job.call_args[1]["tracks"]
    assert len(dl_tracks) == 1
    assert dl_tracks[0].title == "Song One"


@pytest.mark.asyncio
async def test_route_albums_and_songs_commands(test_setup):
    router, indexer, _ = test_setup
    from app.index.models import Track
    indexer.add_track(
        Track(message_id=1, channel_id=-1001, title="Billie Jean", performer="Michael Jackson", album="Thriller")
    )
    indexer.add_track(
        Track(message_id=2, channel_id=-1001, title="Beat It", performer="Michael Jackson", album="Thriller")
    )

    # 1. Test "💿 Browse Albums" button
    msg_alb = DummyMessage("💿 Browse Albums")
    await router.route_message(msg_alb)
    msg_alb.reply.assert_called_once()
    reply_alb = msg_alb.reply.call_args[0][0]
    assert "Thriller" in reply_alb

    # 2. Test "/albums" command
    msg_albs = DummyMessage("/albums")
    await router.route_message(msg_albs)
    msg_albs.reply.assert_called_once()
    assert "Thriller" in msg_albs.reply.call_args[0][0]

    # 3. Test "🎵 All Songs" button
    msg_songs = DummyMessage("🎵 All Songs")
    await router.route_message(msg_songs)
    msg_songs.reply.assert_called_once()
    reply_songs = msg_songs.reply.call_args[0][0]
    assert "All Songs (A–Z)" in reply_songs
    assert "Billie Jean" in reply_songs
    assert "Beat It" in reply_songs

    # 4. Test "/songs" command
    msg_songs_cmd = DummyMessage("/songs")
    await router.route_message(msg_songs_cmd)
    msg_songs_cmd.reply.assert_called_once()
    assert "All Songs (A–Z)" in msg_songs_cmd.reply.call_args[0][0]

    # 5. Test "/album Thriller" command
    msg_album_specific = DummyMessage("/album Thriller")
    await router.route_message(msg_album_specific)
    msg_album_specific.reply.assert_called_once()
    assert "Album: Thriller" in msg_album_specific.reply.call_args[0][0]

    # 6. Test "/song Billie Jean" command
    msg_song_specific = DummyMessage("/song Billie Jean")
    await router.route_message(msg_song_specific)
    msg_song_specific.reply.assert_called_once()
    assert "Billie Jean" in msg_song_specific.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_explorer_albums_directory(test_setup):
    router, indexer, _ = test_setup
    from app.index.models import Track
    indexer.add_track(
        Track(message_id=1, channel_id=-1001, title="Song A", performer="P", album="Abbey Road")
    )
    indexer.add_track(
        Track(message_id=2, channel_id=-1001, title="Song B", performer="P", album="Bad")
    )

    # 1. Test exp:alb:1
    fake_event = MagicMock()
    fake_event.data = b"exp:alb:1"
    fake_event.edit = AsyncMock()
    fake_event.answer = AsyncMock()

    await router.route_callback(fake_event)
    fake_event.edit.assert_called_once()
    edit_text = fake_event.edit.call_args[0][0]
    assert "Albums Directory" in edit_text
    assert "Abbey Road" in edit_text
    assert "Bad" in edit_text

    # 2. Test exp:az:alb
    fake_event_az = MagicMock()
    fake_event_az.data = b"exp:az:alb"
    fake_event_az.edit = AsyncMock()
    fake_event_az.answer = AsyncMock()

    await router.route_callback(fake_event_az)
    fake_event_az.edit.assert_called_once()
    az_text = fake_event_az.edit.call_args[0][0]
    assert "A–Z Alphabet Index · Albums" in az_text


@pytest.mark.asyncio
async def test_artwork_manager_and_delivery(tmp_path):
    from app.index.models import Track
    from app.index.indexer import MusicIndexer
    from app.index.artwork import ArtworkManager
    from app.telegram.artwork import send_or_edit_artwork

    # Set up dummy cache file
    cache_dir = tmp_path / "artwork_cache"
    cache_dir.mkdir(parents=True)
    dummy_art = cache_dir / "101.jpg"
    dummy_art.write_bytes(b"dummy_image_data")

    # Monkeypatch CACHE_DIR
    orig_cache = ArtworkManager.CACHE_DIR
    ArtworkManager.CACHE_DIR = cache_dir
    try:
        indexer = MusicIndexer()
        track1 = Track(message_id=101, channel_id=-1001, title="Song 1", performer="Artist", album="Great Album")
        track2 = Track(message_id=102, channel_id=-1001, title="Song 2", performer="Artist", album="Great Album")
        indexer.add_track(track1)
        indexer.add_track(track2)

        # Direct track artwork
        assert ArtworkManager.get_track_artwork(101) == dummy_art
        assert ArtworkManager.get_track_artwork(102) is None

        # Album artwork resolves from sibling track 101
        assert ArtworkManager.get_album_artwork("Great Album", indexer) == dummy_art
        assert ArtworkManager.resolve_artwork(track2, indexer) == dummy_art

        # Test send_or_edit_artwork with Message
        fake_msg = MagicMock()
        fake_msg.reply = AsyncMock()
        await send_or_edit_artwork(fake_msg, "Album View", artwork_path=dummy_art)
        fake_msg.reply.assert_called_once()
        assert fake_msg.reply.call_args[1]["file"] == str(dummy_art)

        # Test send_or_edit_artwork with CallbackQuery
        fake_event = MagicMock()
        fake_event.data = b"exp:alb:1"
        fake_event.message.media = None
        fake_event.respond = AsyncMock()
        fake_event.delete = AsyncMock()
        fake_event.answer = AsyncMock()

        await send_or_edit_artwork(fake_event, "Album View", artwork_path=dummy_art)
        fake_event.respond.assert_called_once()
        assert fake_event.respond.call_args[1]["file"] == str(dummy_art)
        fake_event.delete.assert_called_once()

        # Test ensure_album_artwork and ensure_track_artwork with mock clients
        ensured_alb = await ArtworkManager.ensure_album_artwork("Great Album", indexer)
        assert ensured_alb == dummy_art

        ensured_track = await ArtworkManager.ensure_track_artwork(track2, indexer=indexer)
        assert ensured_track == dummy_art

        # Test precache_library_artworks
        cached_count = await ArtworkManager.precache_library_artworks(indexer)
        assert cached_count == 0  # Already cached
    finally:
        ArtworkManager.CACHE_DIR = orig_cache






