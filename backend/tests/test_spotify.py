from fastapi.testclient import TestClient

from app.config import Settings
from app.factory import create_app
from app.spotify import build_queries, parse_track, pick_tracks


def _track(spotify_id: str, artist: str, popularity: int, preview: str | None) -> dict:
    return {
        "spotify_id": spotify_id,
        "title": f"Song {spotify_id}",
        "artist": artist,
        "album": "Album",
        "image": None,
        "preview_url": preview,
        "spotify_url": f"https://open.spotify.com/track/{spotify_id}",
        "duration_ms": 200000,
        "popularity": popularity,
    }


def test_parse_track_keeps_only_spotify_preview_hosts():
    parsed = parse_track(
        {
            "type": "track",
            "id": "0123456789abcdefGHIJ",
            "name": "Real Song",
            "is_local": False,
            "duration_ms": 180000,
            "popularity": 40,
            "preview_url": "https://evil.example/preview.mp3",
            "artists": [{"name": "Ada"}],
            "album": {"name": "Rooms", "images": [{"url": "https://i.scdn.co/image/abc"}]},
        }
    )
    assert parsed is not None
    assert parsed["preview_url"] is None
    assert parsed["image"] == "https://i.scdn.co/image/abc"
    assert parsed["spotify_url"] == "https://open.spotify.com/track/0123456789abcdefGHIJ"

    allowed = parse_track(
        {
            "type": "track",
            "id": "0123456789abcdefGHIJ",
            "name": "Real Song",
            "preview_url": "https://p.scdn.co/mp3-preview/abc",
            "artists": [{"name": "Ada"}],
            "album": {"name": "Rooms", "images": []},
        }
    )
    assert allowed is not None
    assert allowed["preview_url"] == "https://p.scdn.co/mp3-preview/abc"
    assert parse_track({"type": "track", "id": "short", "name": "Nope"}) is None


def test_pick_tracks_prefers_previews_and_spreads_artists():
    candidates = [
        _track("aaaaaaaaaa0000000001", "Ada", 90, None),
        _track("aaaaaaaaaa0000000002", "Ada", 80, "https://p.scdn.co/mp3-preview/a"),
        _track("aaaaaaaaaa0000000003", "Bea", 70, "https://p.scdn.co/mp3-preview/b"),
        _track("aaaaaaaaaa0000000004", "Ada", 60, "https://p.scdn.co/mp3-preview/c"),
        _track("aaaaaaaaaa0000000005", "Ada", 50, "https://p.scdn.co/mp3-preview/d"),
    ]
    picked = pick_tracks(candidates, limit=3, artist_cap=2)
    assert [track["spotify_id"] for track in picked] == [
        "aaaaaaaaaa0000000002",
        "aaaaaaaaaa0000000003",
        "aaaaaaaaaa0000000004",
    ]
    assert "popularity" not in picked[0]
    assert build_queries("  Arijit Singh  ", "calm", ["indie"]) == ["Arijit Singh", "Arijit Singh calm acoustic"]
    assert build_queries("", "calm", ["bengali-modern"]) == ["calm acoustic", "calm acoustic bengali modern"]


class _FakeSpotify:
    configured = True
    client_id = "test-client"
    market = "IN"

    def search_tracks(self, query: str) -> list[dict]:
        return [
            _track("bbbbbbbbbb0000000001", "Ada", 20, "https://p.scdn.co/mp3-preview/one"),
            _track("bbbbbbbbbb0000000002", "Bea", 10, None),
        ]


def test_generate_saves_a_playlist_of_spotify_tracks(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", db_path=tmp_path / "data" / "test.db", seed=42, log_level="WARNING")
    app = create_app(settings)
    app.state.spotify = _FakeSpotify()
    client = TestClient(app)
    response = client.post(
        "/api/spotify/playlists/generate",
        json={"user_id": "local-user", "name": "Evening", "prompt": "piano", "mood": "calm", "use_profile": False, "limit": 5},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Evening"
    assert body["tracks"][0]["preview_url"].startswith("https://p.scdn.co/")
    assert body["tracks"][1]["preview_url"] is None
    assert "recommendation model" in " ".join(body["notes"])
    listed = client.get("/api/spotify/playlists?user_id=local-user")
    assert listed.status_code == 200
    assert listed.json()["playlists"][0]["id"] == body["id"]
    status = client.get("/api/spotify/status")
    assert status.json()["configured"] is True


def test_generate_requires_spotify_credentials(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", db_path=tmp_path / "data" / "test.db", seed=42, log_level="WARNING")
    client = TestClient(create_app(settings))
    response = client.post(
        "/api/spotify/playlists/generate",
        json={"name": "Evening", "prompt": "piano", "use_profile": False},
    )
    assert response.status_code == 503
    assert "SPOTIFY_CLIENT" in response.json()["detail"]
