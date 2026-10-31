from fastapi.testclient import TestClient

from app.config import Settings
from app.factory import create_app


def _client(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", db_path=tmp_path / "data" / "test.db", seed=42, log_level="WARNING")
    return TestClient(create_app(settings))


def _onboard(client: TestClient) -> None:
    response = client.post(
        "/api/onboarding/profile",
        json={
            "user_id": "local-user",
            "artists": ["Anik Sen", "Hanae Ito"],
            "genres": ["bengali-modern", "indie", "ambient"],
            "languages": ["bn", "en"],
            "purpose": "relax",
            "discovery": 0.35,
            "energy": 0.32,
            "danceability": 0.34,
            "acousticness": 0.78,
            "valence": 0.42,
            "tempo": 0.3,
        },
    )
    assert response.status_code == 200, response.text


def test_health_and_recommendation_contract(tmp_path):
    client = _client(tmp_path)
    health = client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["demo_mode"] is True
    assert body["catalog_tracks"] > 40
    assert body["synthetic_interactions"] > 100
    assert "editorial" in body["feature_source"]

    missing = client.get("/api/recommendations")
    assert missing.status_code == 400

    _onboard(client)
    ranked = client.get("/api/recommendations", params={"limit": 8, "strategy": "hybrid"})
    assert ranked.status_code == 200, ranked.text
    payload = ranked.json()
    assert payload["ranking_mode"] == "cold_start_content"
    assert payload["items"]
    first = payload["items"][0]
    assert first["explanations"]
    assert "components" in first
    assert first["components"]["collaborative"] is None
    assert 0.0 <= first["score"] <= 1.0


def test_feedback_updates_taste_without_a_full_retrain(tmp_path):
    client = _client(tmp_path)
    _onboard(client)
    track_id = client.get("/api/tracks/search", params={"q": "Paper Boats"}).json()["tracks"][0]["id"]
    before = client.get("/api/user/taste").json()
    assert before["inferred"]["n_events"] == 0
    feedback = client.post(
        "/api/recommendations/feedback",
        json={"user_id": "local-user", "track_id": track_id, "event_type": "like", "listen_ms": 180000, "duration_ms": 200000},
    )
    assert feedback.status_code == 200, feedback.text
    after = feedback.json()
    genre_affinity = after["inferred"]["genre_affinity"]
    assert genre_affinity
    assert max(genre_affinity.values()) < 0.5
    assert after["inferred"]["confidence"] < 0.2
    assert after["collaborative_unlocked"] is False


def test_mood_endpoints_do_not_require_an_image(tmp_path):
    client = _client(tmp_path)
    _onboard(client)
    predicted = client.post("/api/mood/predict", json={"distribution": {"sad": 0.8, "neutral": 0.2}})
    assert predicted.status_code == 200
    assert predicted.json()["suggested_mood"] == "sad"
    assert predicted.json()["images_stored"] is False

    blocked = client.post(
        "/api/mood/recommendations",
        json={"user_id": "local-user", "mood": "sad", "mode": "match", "source": "camera", "confirmed": False, "confidence": 0.8},
    )
    assert blocked.status_code == 400

    match = client.post(
        "/api/mood/recommendations",
        json={"user_id": "local-user", "mood": "sad", "mode": "match", "source": "manual", "limit": 6},
    )
    shift = client.post(
        "/api/mood/recommendations",
        json={"user_id": "local-user", "mood": "sad", "mode": "shift", "source": "manual", "limit": 6},
    )
    assert match.status_code == 200 and shift.status_code == 200
    assert match.json()["target_mood"] == "sad"
    assert shift.json()["target_mood"] == "hopeful"
    match_ids = [item["track"]["id"] for item in match.json()["items"]]
    shift_ids = [item["track"]["id"] for item in shift.json()["items"]]
    assert match_ids != shift_ids


def test_removing_a_playlist_track_drops_it_from_the_list(tmp_path):
    client = _client(tmp_path)
    _onboard(client)
    track_id = client.get("/api/tracks/search", params={"limit": 1}).json()["tracks"][0]["id"]
    created = client.post("/api/playlists", json={"user_id": "local-user", "name": "Evening"})
    assert created.status_code == 200, created.text
    added = client.post(
        "/api/recommendations/feedback",
        json={
            "user_id": "local-user",
            "track_id": track_id,
            "event_type": "playlist_add",
            "playlist_id": created.json()["id"],
            "listen_ms": 0,
            "duration_ms": 1000,
        },
    )
    assert added.status_code == 200, added.text
    removed = client.delete(
        f"/api/playlists/{created.json()['id']}/tracks/{track_id}",
        params={"user_id": "local-user"},
    )
    assert removed.status_code == 200, removed.text
    listed = client.get("/api/playlists", params={"user_id": "local-user"}).json()
    assert listed["playlists"][0]["track_ids"] == []
    assert listed["playlists"][0]["tracks"] == []


def test_similar_search_and_evaluation_warning(tmp_path):
    client = _client(tmp_path)
    _onboard(client)
    search = client.get("/api/tracks/search", params={"language": "ja", "limit": 5})
    assert search.status_code == 200
    assert search.json()["tracks"]
    track_id = search.json()["tracks"][0]["id"]
    similar = client.get(f"/api/tracks/{track_id}/similar", params={"limit": 4})
    assert similar.status_code == 200
    assert similar.json()["feature_source"].startswith("editorial")
    assert len(similar.json()["items"]) == 4

    unevaluated = client.get("/api/ml/evaluation")
    assert unevaluated.json()["available"] is False

    evaluation = client.post("/api/ml/evaluate", json={"k": 10, "diversify": False, "include_svd": False})
    assert evaluation.status_code == 200, evaluation.text
    result = evaluation.json()
    assert result["meaningful_as_real_world"] is False
    assert result["suppressed"] is False
    assert "synthetic" in result["warning"].lower() or "generated" in result["warning"].lower()
    names = [model["strategy"] for model in result["models"]]
    assert names == ["popularity", "content", "collaborative", "hybrid"]
    for model in result["models"]:
        assert model["metrics"]["ndcg_at_k"]["mean"] is not None
        assert 0.0 <= model["metrics"]["precision_at_k"]["mean"] <= 1.0

    clusters = client.get("/api/ml/clusters")
    assert clusters.status_code == 200
    assert clusters.json()["available"] is True
    assert clusters.json()["diagnostics"]


def test_synth_user_is_rejected(tmp_path):
    client = _client(tmp_path)
    response = client.post(
        "/api/onboarding/profile",
        json={
            "user_id": "synth-001",
            "genres": ["jazz"],
            "languages": ["en"],
            "purpose": "focus",
            "discovery": 0.5,
            "energy": 0.4,
            "danceability": 0.4,
            "acousticness": 0.6,
            "valence": 0.5,
            "tempo": 0.4,
        },
    )
    assert response.status_code == 400
