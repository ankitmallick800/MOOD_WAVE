import json
import time

from fastapi.testclient import TestClient

from app.config import Settings
from app.data.catalog import language_factor
from app.factory import create_app
from app.ml.hybrid import rank_tracks
from app.ml.profile import ExplicitProfile, InferredProfile
from dataclasses import replace

from app.providers.itunes import is_browse_noise, pick_itunes_match, track_from_itunes


def _item(track_id: int, title: str, artist: str, genre: str, preview: str | None) -> dict:
    return {
        "kind": "song",
        "trackId": track_id,
        "trackName": title,
        "artistName": artist,
        "collectionName": "Album",
        "primaryGenreName": genre,
        "previewUrl": preview,
        "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/Features/100x100bb.jpg",
        "trackViewUrl": "https://music.apple.com/us/album/album/1?i=" + str(track_id),
        "trackTimeMillis": 214000,
        "releaseDate": "2015-11-27T12:00:00Z",
    }


def _profile() -> ExplicitProfile:
    return ExplicitProfile(
        artists=["Ada"],
        genres=["indie"],
        languages=["bn"],
        purpose="relax",
        discovery=0.4,
        energy=0.3,
        danceability=0.3,
        acousticness=0.7,
        valence=0.4,
        tempo=0.3,
    )


def test_itunes_track_keeps_real_metadata_and_leaves_audio_unknown():
    preview = "https://audio-ssl.itunes.apple.com/itunes-assets/preview.m4a"
    track = track_from_itunes(_item(42, "Window", "Ada", "Indie Pop", preview))
    assert track is not None
    assert track.energy is None
    assert track.tempo is None
    assert track.language == ""
    assert track.mood_tags == ()
    assert track.genres == ("indie", "pop")
    public = track.to_public_dict()
    assert public["preview"] == "preview"
    assert public["audio_url"] == preview
    assert public["artwork_url"] is not None and "600x600bb" in public["artwork_url"]
    assert public["provider"] == "itunes"
    assert public["duration_ms"] == 0
    assert public["song_duration_ms"] == 214000
    assert "/audio/" not in (public["audio_url"] or "")
    assert language_factor(track, _profile(), InferredProfile.empty()) == 1.0

    blocked = track_from_itunes(_item(43, "Window", "Ada", "Indie Pop", "https://evil.example/preview.mp3"))
    assert blocked is not None
    assert blocked.to_public_dict()["preview"] == "unavailable"
    assert blocked.to_public_dict()["audio_url"] is None


def test_metadata_rank_uses_genre_and_does_not_claim_energy():
    indie = track_from_itunes(_item(1, "Window", "Ada", "Indie Pop", "https://audio-ssl.itunes.apple.com/a.m4a"))
    other = track_from_itunes(_item(2, "March", "Bea", "Soundtrack", "https://audio-ssl.itunes.apple.com/b.m4a"))
    assert indie is not None and other is not None
    ranked, meta = rank_tracks(
        [other, indie],
        _profile(),
        InferredProfile.empty(),
        collab_scores=None,
        pop_scores={indie.id: 0.0, other.id: 0.0},
        neighbor_for=None,
        strategy="content",
        diversify=False,
        limit=2,
        catalog_kind="metadata",
    )
    assert ranked[0].track.id == indie.id
    assert ranked[0].components["mood"] is None
    blob = " ".join(ranked[0].explanations).lower()
    assert "indie" in blob
    assert "preferred tempo" not in blob
    assert "energy and valence" not in blob
    assert any("unknown" in note.lower() or "not filled" in note.lower() for note in meta["notes"])

    hybrid, _ = rank_tracks(
        [other, indie],
        _profile(),
        InferredProfile.empty(),
        collab_scores=None,
        pop_scores={indie.id: 0.0, other.id: 0.0},
        neighbor_for=None,
        strategy="hybrid",
        diversify=False,
        limit=2,
        catalog_kind="metadata",
    )
    assert hybrid[0].track.id == indie.id
    assert hybrid[0].score > hybrid[1].score
    hybrid_text = " ".join(hybrid[0].explanations).lower()
    assert "indie" in hybrid_text
    assert "preferred tempo" not in hybrid_text
    assert "energy" not in hybrid_text


def test_itunes_server_skips_synthetic_listeners_and_imports_youtube(tmp_path):
    cache = tmp_path / "data" / "itunes_catalog.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(
        json.dumps(
            {
                "fetched_at": time.time(),
                "items": [_item(7, "Agar Tum Saath Ho", "Arijit Singh", "Bollywood", "https://audio-ssl.itunes.apple.com/preview.m4a")],
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "test.db",
        seed=42,
        log_level="WARNING",
        catalog_source="itunes",
    )
    client = TestClient(create_app(settings))
    health = client.get("/api/health").json()
    assert health["demo_mode"] is False
    assert health["synthetic_interactions"] == 0
    assert health["catalog_tracks"] == 1
    assert health["feature_source"] == "itunes_metadata"

    onboard = client.post(
        "/api/onboarding/profile",
        json={
            "user_id": "local-user",
            "artists": ["Arijit Singh"],
            "genres": ["bollywood"],
            "languages": ["bn", "en"],
            "purpose": "relax",
            "discovery": 0.4,
            "energy": 0.4,
            "danceability": 0.4,
            "acousticness": 0.5,
            "valence": 0.5,
            "tempo": 0.4,
        },
    )
    assert onboard.status_code == 200, onboard.text
    ranked = client.get("/api/recommendations", params={"limit": 5, "strategy": "hybrid"})
    assert ranked.status_code == 200, ranked.text
    song = ranked.json()["items"][0]["track"]
    assert song["title"] == "Agar Tum Saath Ho"
    assert song["artist"] == "Arijit Singh"
    assert song["audio_url"].startswith("https://audio-ssl.itunes.apple.com/")
    assert song["energy"] is None
    assert "preferred tempo" not in " ".join(ranked.json()["items"][0]["explanations"]).lower()

    same = client.post(
        "/api/catalog/import",
        json={
            "provider": "youtube",
            "provider_id": "abcdefghijk",
            "title": "Agar Tum Saath Ho",
            "artist": "Arijit Singh",
            "external_url": "https://music.youtube.com/watch?v=abcdefghijk",
            "song_duration_ms": 340000,
            "embeddable": True,
        },
    )
    assert same.status_code == 200, same.text
    assert same.json()["id"] == song["id"]

    fresh = client.post(
        "/api/catalog/import",
        json={
            "provider": "youtube",
            "provider_id": "bbbbbbbbbbb",
            "title": "River",
            "artist": "Bea",
            "artwork_url": "https://i.ytimg.com/vi/bbbbbbbbbbb/hqdefault.jpg",
            "external_url": "https://music.youtube.com/watch?v=bbbbbbbbbbb",
            "song_duration_ms": 180000,
            "embeddable": False,
        },
    )
    assert fresh.status_code == 200, fresh.text
    body = fresh.json()
    assert body["id"] == "yt:bbbbbbbbbbb"
    assert body["preview"] == "unavailable"
    assert body["audio_url"] is None
    assert body["energy"] is None
    assert body["external_url"].startswith("https://music.youtube.com/watch?v=")

    created = client.post("/api/playlists", json={"user_id": "local-user", "name": "Evening"})
    added = client.post(
        "/api/recommendations/feedback",
        json={
            "user_id": "local-user",
            "track_id": body["id"],
            "event_type": "playlist_add",
            "playlist_id": created.json()["id"],
            "listen_ms": 0,
            "duration_ms": 180000,
        },
    )
    assert added.status_code == 200, added.text
    listed = client.get("/api/playlists", params={"user_id": "local-user"}).json()
    assert listed["playlists"][0]["tracks"][0]["title"] == "River"


def test_pick_itunes_match_requires_the_artist_and_noise_is_marked():
    preview = "https://audio-ssl.itunes.apple.com/a.m4a"
    gym = track_from_itunes(_item(1, "Gym", "Sippy Gill", "Pop", preview))
    other = track_from_itunes(_item(2, "Gym", "Someone Else", "Pop", preview))
    demo = track_from_itunes(_item(3, "Changes (Demo)", "Yot Club", "Indie Pop", preview))
    folk = track_from_itunes(_item(4, "Indie Folk (1) (Outro)", "Sindall", "Easy Listening", preview))
    real = track_from_itunes(_item(5, "POP!", "NAYEON", "Dance", preview))
    assert gym is not None and other is not None and demo is not None and folk is not None and real is not None
    assert pick_itunes_match([other, gym], "Gym", "Sippy Gill").id == gym.id
    assert pick_itunes_match([other], "Gym", "Sippy Gill") is None
    assert is_browse_noise(demo)
    assert is_browse_noise(folk)
    assert is_browse_noise(replace(real, id="mw-004", provider="demo"))
    assert is_browse_noise(replace(real, id="yt:abcdefghijk", provider="youtube"))
    assert not is_browse_noise(real)


def test_itunes_search_hides_demo_versions_placeholders_and_dislikes(tmp_path, monkeypatch):
    cache = tmp_path / "data" / "itunes_catalog.json"
    cache.parent.mkdir(parents=True)
    preview = "https://audio-ssl.itunes.apple.com/preview.m4a"
    cache.write_text(
        json.dumps(
            {
                "fetched_at": time.time(),
                "items": [
                    _item(1, "Changes (Demo)", "Yot Club", "Indie Pop", preview),
                    _item(2, "Indie Folk", "Z-Studio", "Pop", preview),
                    _item(3, "Agar Tum Saath Ho", "Arijit Singh", "Bollywood", preview),
                    _item(4, "POP!", "NAYEON", "Dance", preview),
                ],
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "test.db",
        seed=42,
        log_level="WARNING",
        catalog_source="itunes",
    )
    client = TestClient(create_app(settings))
    listed = client.get("/api/tracks/search", params={"limit": 20})
    assert listed.status_code == 200, listed.text
    titles = [track["title"] for track in listed.json()["tracks"]]
    assert titles == ["Agar Tum Saath Ho", "POP!"]
    onboard = client.post(
        "/api/onboarding/profile",
        json={
            "user_id": "local-user",
            "artists": ["Arijit Singh"],
            "genres": ["bollywood"],
            "languages": ["bn"],
            "purpose": "relax",
            "discovery": 0.4,
            "energy": 0.4,
            "danceability": 0.4,
            "acousticness": 0.5,
            "valence": 0.5,
            "tempo": 0.4,
        },
    )
    assert onboard.status_code == 200, onboard.text
    song_id = listed.json()["tracks"][0]["id"]
    disliked = client.post(
        "/api/user/reactions",
        json={"user_id": "local-user", "track_id": song_id, "reaction": "dislike"},
    )
    assert disliked.status_code == 200, disliked.text
    hidden = client.get("/api/tracks/search", params={"limit": 20, "user_id": "local-user"}).json()
    assert [track["title"] for track in hidden["tracks"]] == ["POP!"]
    ranked = client.get("/api/recommendations", params={"limit": 10}).json()
    ranked_titles = [item["track"]["title"] for item in ranked["items"]]
    assert "Changes (Demo)" not in ranked_titles
    assert "Indie Folk" not in ranked_titles

    matched = track_from_itunes(_item(9, "Gym", "Sippy Gill", "Pop", preview))
    monkeypatch.setattr("app.services.engine.search_itunes", lambda *_args, **_kwargs: [matched])
    found = client.post("/api/catalog/apple-match", json={"title": "Gym (Official Video)", "artist": "Sippy Gill"})
    assert found.status_code == 200, found.text
    assert found.json()["id"] == "itunes:9"
    assert found.json()["provider"] == "itunes"
    assert found.json()["preview"] == "preview"
    assert found.json()["embed_url"] is None

    monkeypatch.setattr("app.services.engine.search_itunes", lambda *_args, **_kwargs: [])
    missing = client.post("/api/catalog/apple-match", json={"title": "Missing Song", "artist": "Nobody"})
    assert missing.status_code == 404
