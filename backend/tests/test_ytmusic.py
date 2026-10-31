from fastapi.testclient import TestClient

from app.config import Settings
from app.factory import create_app
from app.ytmusic_catalog import parse_song, pick_songs


def _raw(video_id: str, title: str, artist: str, seconds: int) -> dict:
    return {
        "resultType": "song",
        "videoId": video_id,
        "title": title,
        "duration_seconds": seconds,
        "artists": [{"name": artist}],
        "album": {"name": "Album"},
        "thumbnails": [{"url": "https://i.ytimg.com/vi/" + video_id + "/hqdefault.jpg"}],
        "isAvailable": True,
    }


def test_parse_song_keeps_song_length_tracks_and_official_images():
    song = parse_song(_raw("abcdefghijk", "Lamp", "Ada", 180))
    assert song is not None
    assert song["watch_url"] == "https://music.youtube.com/watch?v=abcdefghijk"
    assert song["image"].startswith("https://i.ytimg.com/")
    assert parse_song(_raw("abcdefghijk", "Hours", "Ada", 10774)) is None
    assert parse_song(_raw("short", "Nope", "Ada", 180)) is None
    bad_image = _raw("abcdefghijk", "Lamp", "Ada", 180)
    bad_image["thumbnails"] = [{"url": "https://evil.example/cover.jpg"}]
    parsed = parse_song(bad_image)
    assert parsed is not None
    assert parsed["image"] is None


def test_pick_songs_caps_one_artist():
    songs = [
        parse_song(_raw("aaaaaaaaaaa", "One", "Ada", 180)),
        parse_song(_raw("bbbbbbbbbbb", "Two", "Ada", 190)),
        parse_song(_raw("ccccccccccc", "Three", "Ada", 200)),
        parse_song(_raw("ddddddddddd", "Four", "Bea", 210)),
    ]
    picked = pick_songs([song for song in songs if song], limit=3, artist_cap=2)
    assert [song["video_id"] for song in picked] == ["aaaaaaaaaaa", "bbbbbbbbbbb", "ddddddddddd"]


class _FakeCatalog:
    location = "IN"

    def search_songs(self, query: str) -> list[dict]:
        return [
            parse_song(_raw("eeeeeeeeeee", "River", "Ada", 200)),
            parse_song(_raw("fffffffffff", "Window", "Bea", 210)),
        ]


def test_generate_saves_a_youtube_music_playlist(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", db_path=tmp_path / "data" / "test.db", seed=42, log_level="WARNING")
    app = create_app(settings)
    app.state.ytmusic = _FakeCatalog()
    client = TestClient(app)
    response = client.post(
        "/api/ytmusic/playlists/generate",
        json={"name": "Evening", "prompt": "acoustic", "mood": "calm", "use_profile": False, "limit": 5},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tracks"][0]["watch_url"].startswith("https://music.youtube.com/watch?v=")
    assert "not downloaded" in " ".join(body["notes"])
    listed = client.get("/api/ytmusic/playlists?user_id=local-user")
    assert listed.json()["playlists"][0]["id"] == body["id"]
    status = client.get("/api/ytmusic/status")
    assert status.json()["available"] is True
