from app.index.models import Track
from app.index.search import SearchEngine


def sample_tracks() -> list[Track]:
    return [
        Track(
            message_id=1,
            channel_id=-1001,
            title="In The End",
            performer="Linkin Park",
            album="Hybrid Theory",
            genre="Nu Metal",
            tags={"rock", "numetal", "favorite", "artist:linkin_park"},
            structured_tags={"artist": "linkin_park", "genre": "nu_metal"},
            is_favorite=True,
        ),
        Track(
            message_id=2,
            channel_id=-1001,
            title="Numb",
            performer="Linkin Park",
            album="Meteora",
            genre="Rock",
            tags={"rock", "alternative", "artist:linkin_park"},
            structured_tags={"artist": "linkin_park", "genre": "rock"},
            is_favorite=False,
        ),
        Track(
            message_id=3,
            channel_id=-1001,
            title="Blinding Lights",
            performer="The Weeknd",
            album="After Hours",
            genre="Synthwave",
            tags={"pop", "synthwave", "favorite", "artist:the_weeknd"},
            structured_tags={"artist": "the_weeknd", "genre": "synthwave"},
            is_favorite=True,
        ),
        Track(
            message_id=4,
            channel_id=-1001,
            title="Starboy",
            performer="The Weeknd",
            album="Starboy",
            genre="R&B",
            tags={"r&b", "pop", "artist:the_weeknd"},
            structured_tags={"artist": "the_weeknd"},
            is_favorite=False,
        ),
    ]


def test_exact_tag_search():
    tracks = sample_tracks()
    res = SearchEngine.search("#rock", tracks)
    assert res.total_count == 2
    ids = {t.message_id for t in res.tracks}
    assert ids == {1, 2}


def test_field_search_artist():
    tracks = sample_tracks()
    res = SearchEngine.search("artist:the_weeknd", tracks)
    assert res.total_count == 2
    ids = {t.message_id for t in res.tracks}
    assert ids == {3, 4}


def test_field_search_album():
    tracks = sample_tracks()
    res = SearchEngine.search("album:meteora", tracks)
    assert res.total_count == 1
    assert res.tracks[0].title == "Numb"


def test_favorite_shortcut():
    tracks = sample_tracks()
    res = SearchEngine.search("favorite", tracks)
    assert res.total_count == 2
    ids = {t.message_id for t in res.tracks}
    assert ids == {1, 3}


def test_keyword_search():
    tracks = sample_tracks()
    res = SearchEngine.search("blinding", tracks)
    assert res.total_count == 1
    assert res.tracks[0].title == "Blinding Lights"


def test_fuzzy_typo_search():
    tracks = sample_tracks()
    # "blindng" typo should still find "Blinding Lights"
    res1 = SearchEngine.search("blindng", tracks)
    assert res1.total_count == 1
    assert res1.tracks[0].title == "Blinding Lights"

    # "linken" typo should find Linkin Park songs
    res2 = SearchEngine.search("linken", tracks)
    assert res2.total_count == 2


def test_pagination():
    tracks = sample_tracks()
    # 4 tracks with page_size=2 should yield 2 pages
    page1 = SearchEngine.search("", tracks, page=1, page_size=2)
    assert page1.total_count == 4
    assert len(page1.tracks) == 2
    assert page1.page == 1
    assert page1.total_pages == 2
    assert page1.has_next_page is True
    assert page1.has_prev_page is False

    page2 = SearchEngine.search("", tracks, page=2, page_size=2)
    assert len(page2.tracks) == 2
    assert page2.page == 2
    assert page2.has_next_page is False
    assert page2.has_prev_page is True
