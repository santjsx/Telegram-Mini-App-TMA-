from app.index.parser import normalize_tag, parse_caption, MetadataParser
from app.index.models import Track


def test_normalize_tag():
    assert normalize_tag("#Rock") == "rock"
    assert normalize_tag("#rock") == "rock"
    assert normalize_tag("#ROCK") == "rock"
    assert normalize_tag("#artist:Arijit_Singh") == "artist:arijit_singh"
    assert normalize_tag("#album:Meteora") == "album:meteora"
    assert normalize_tag("#genre:Bollywood") == "genre:bollywood"
    assert normalize_tag(" #favorite  ") == "favorite"


def test_parse_caption_full_structured():
    caption = (
        "Check out this track!\n"
        "#artist:linkin_park\n"
        "#album:meteora\n"
        "#genre:rock\n"
        "#language:english\n"
        "#year:2003\n"
        "#favorite"
    )
    tags, structured, is_favorite = parse_caption(caption)
    assert is_favorite is True
    assert structured["artist"] == "linkin_park"
    assert structured["album"] == "meteora"
    assert structured["genre"] == "rock"
    assert structured["language"] == "english"
    assert structured["year"] == "2003"
    # Tag sets contain both structured and standalone values
    assert "rock" in tags
    assert "favorite" in tags
    assert "artist:linkin_park" in tags


def test_parse_caption_empty():
    tags, structured, is_favorite = parse_caption("")
    assert tags == set()
    assert structured == {}
    assert is_favorite is False


def test_track_formatting():
    track = Track(
        message_id=101,
        channel_id=-1001234567,
        title="Numb",
        performer="Linkin Park",
        album="Meteora",
        duration=187,
        file_size=7864320,  # ~7.5 MB
    )
    assert track.duration_formatted == "3:07"
    assert "7.5 MB" in track.file_size_formatted
    assert track.display_title == "Linkin Park - Numb"


def test_album_title_normalization():
    from unittest.mock import MagicMock
    from telethon.tl.types import MessageMediaDocument, DocumentAttributeAudio

    mock_msg = MagicMock()
    mock_msg.id = 5
    mock_msg.message = "🎵 **Aa Seetha Devainaa**\n\n#artist:sumedha #album:krishnagadi_veera_prema_gaadha"
    mock_msg.audio = None
    mock_msg.media = MagicMock(spec=MessageMediaDocument)
    mock_doc = MagicMock()
    mock_doc.size = 5000000
    mock_doc.mime_type = "audio/mp4"
    audio_attr = MagicMock(spec=DocumentAttributeAudio)
    audio_attr.duration = 130
    audio_attr.title = "Aa Seetha Devainaa"
    audio_attr.performer = "Sumedha"
    mock_doc.attributes = [audio_attr]
    mock_msg.media.document = mock_doc

    track = MetadataParser.extract_track(mock_msg, channel_id=-1004316652121)
    assert track is not None
    assert track.album == "Krishna Gaadi Veera Prema Gaadha"
