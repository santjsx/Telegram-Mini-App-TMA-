from app.index.parser import (
    normalize_tag,
    parse_caption,
    MetadataParser,
    clean_display_title,
    get_audio_badge,
)
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


def test_clean_display_title():
    assert clean_display_title("5.RAYALASEEMA MUDDU BIDDA") == "RAYALASEEMA MUDDU BIDDA"
    assert clean_display_title("01 - Song Title.mp3") == "Song Title"
    assert clean_display_title("01. Another Song") == "Another Song"
    assert clean_display_title("02_Track Name") == "Track Name"
    assert clean_display_title("[03] Bracket Song") == "Bracket Song"
    assert clean_display_title("(04) Paren Song") == "Paren Song"
    assert clean_display_title("1. Song Name") == "Song Name"
    assert clean_display_title("500 Miles") == "500 Miles"
    assert clean_display_title("21 Guns") == "21 Guns"
    assert clean_display_title("1999") == "1999"


def test_get_audio_badge():
    t_flac = Track(message_id=1, channel_id=-1, title="Hi", performer="Artist", mime_type="audio/flac")
    assert get_audio_badge(t_flac) == "FLAC"

    t_m4a = Track(message_id=2, channel_id=-1, title="Hi", performer="Artist", mime_type="audio/mp4")
    assert get_audio_badge(t_m4a) == "M4A"

    t_mp3 = Track(message_id=3, channel_id=-1, title="Hi", performer="Artist", mime_type="audio/mpeg")
    assert get_audio_badge(t_mp3) == "MP3"

    t_wav = Track(message_id=4, channel_id=-1, title="Hi", performer="Artist", filename="song.wav")
    assert get_audio_badge(t_wav) == "WAV"

