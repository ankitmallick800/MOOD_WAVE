"""HTTP API. Handlers validate inputs and delegate scoring to the engine."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

import time

from app.ml.profile import ExplicitProfile
from app.ml.vocabulary import EVENT_TYPES, GENRES, LANGUAGES, LISTENING_MOODS, PURPOSES
from app.schemas import (
    ConfigIn,
    EvaluateIn,
    FeedbackIn,
    MoodPredictIn,
    MoodRecommendationsIn,
    OnboardingIn,
    AppleMatchIn,
    CatalogImportIn,
    PlaylistIn,
    ReactionIn,
    ResetIn,
    SpotifyPlaylistIn,
)
from app.providers.lrclib import lookup_lyrics
from app.services.engine import Engine, EngineError
from app.spotify import SpotifyClient, SpotifyError, build_queries, missing_credentials, pick_tracks
from app.ytmusic_catalog import YTMusicCatalog, YTMusicError, mark_embeds, pick_songs

router = APIRouter(prefix="/api")


def engine(request: Request) -> Engine:
    return request.app.state.engine


def _check_vocab(body: OnboardingIn) -> ExplicitProfile:
    unknown_genres = [genre for genre in body.genres if genre not in GENRES]
    if unknown_genres:
        raise EngineError(400, f"Unknown genres: {', '.join(unknown_genres)}")
    unknown_languages = [language for language in body.languages if language not in LANGUAGES]
    if unknown_languages:
        raise EngineError(400, f"Unknown languages: {', '.join(unknown_languages)}")
    if body.purpose not in PURPOSES or body.purpose == "none":
        raise EngineError(400, "Choose a listening purpose.")
    artists = [artist.strip() for artist in body.artists if artist.strip()]
    return ExplicitProfile(
        artists=artists,
        genres=list(dict.fromkeys(body.genres)),
        languages=list(dict.fromkeys(body.languages)),
        purpose=body.purpose,
        discovery=body.discovery,
        energy=body.energy,
        danceability=body.danceability,
        acousticness=body.acousticness,
        valence=body.valence,
        tempo=body.tempo,
    )


@router.get("/health")
def health(request: Request) -> dict:
    return engine(request).health()


@router.get("/catalog/facets")
def facets(request: Request) -> dict:
    return engine(request).facets()


@router.post("/onboarding/profile")
def onboarding(body: OnboardingIn, request: Request) -> dict:
    profile = _check_vocab(body)
    return engine(request).save_onboarding(body.user_id, profile, body.reset_inferred)


@router.get("/user/taste")
def taste(request: Request, user_id: str = Query(default="local-user")) -> dict:
    return engine(request).taste(user_id)


@router.post("/user/reset")
def reset(body: ResetIn, request: Request) -> dict:
    if body.scope not in {"inferred", "all"}:
        raise EngineError(400, "scope must be 'inferred' or 'all'.")
    return engine(request).reset(body.user_id, body.scope)


@router.post("/user/reactions")
def reactions(body: ReactionIn, request: Request) -> dict:
    if body.reaction not in {"like", "dislike", "none"}:
        raise EngineError(400, "reaction must be like, dislike, or none.")
    return engine(request).set_reaction(body.user_id, body.track_id, body.reaction)


@router.get("/recommendations")
def recommendations(
    request: Request,
    user_id: str = Query(default="local-user"),
    limit: int = Query(default=20, ge=1, le=50),
    strategy: str = Query(default="hybrid"),
    mood: str | None = None,
    mood_mode: str = Query(default="match"),
    diversify: bool = True,
) -> dict:
    if strategy not in {"hybrid", "content", "collaborative", "collaborative_svd", "popularity"}:
        raise EngineError(400, "Unknown recommendation strategy.")
    if mood is not None and mood not in LISTENING_MOODS:
        raise EngineError(400, "Unknown listening mood.")
    if mood_mode not in {"match", "shift"}:
        raise EngineError(400, "mood_mode must be match or shift.")
    return engine(request).recommend(user_id, limit, strategy, mood, mood_mode, diversify)


@router.post("/recommendations/feedback")
def feedback(body: FeedbackIn, request: Request) -> dict:
    if body.event_type not in EVENT_TYPES:
        raise EngineError(400, "Unknown event type.")
    return engine(request).record_feedback(
        body.user_id,
        body.track_id,
        body.event_type,
        body.listen_ms,
        body.duration_ms,
        body.playlist_id,
    )


@router.get("/tracks/search")
def search_tracks(
    request: Request,
    q: str = "",
    genre: str | None = None,
    language: str | None = None,
    mood: str | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    user_id: str | None = None,
) -> dict:
    return engine(request).search(q, genre, language, mood, limit, user_id)


@router.post("/catalog/import")
def import_catalog_track(body: CatalogImportIn, request: Request) -> dict:
    return engine(request).import_provider_track(body.user_id, body.model_dump())


@router.post("/catalog/apple-match")
def apple_match(body: AppleMatchIn, request: Request) -> dict:
    return engine(request).match_apple_track(body.user_id, body.title, body.artist)


@router.get("/tracks/{track_id}")
def track_detail(track_id: str, request: Request) -> dict:
    return engine(request)._track(track_id).to_public_dict()


@router.get("/tracks/{track_id}/lyrics")
def track_lyrics(track_id: str, request: Request) -> dict:
    track = engine(request)._track(track_id)
    duration = track.song_duration_ms or track.duration_ms or 0
    return lookup_lyrics(track.title, track.artist, track.album, int(duration))


@router.get("/tracks/{track_id}/similar")
def similar(track_id: str, request: Request, limit: int = Query(default=8, ge=1, le=30)) -> dict:
    return engine(request).similar(track_id, limit)


@router.post("/tracks/{track_id}/analyze")
def analyze(track_id: str, request: Request) -> dict:
    return engine(request).analyze_track_audio(track_id)


@router.post("/mood/predict")
def mood_predict(body: MoodPredictIn, request: Request) -> dict:
    return engine(request).predict_mood(body.distribution)


@router.post("/mood/recommendations")
def mood_recommendations(body: MoodRecommendationsIn, request: Request) -> dict:
    if body.mood not in LISTENING_MOODS:
        raise EngineError(400, "Unknown listening mood.")
    if body.mode not in {"match", "shift"}:
        raise EngineError(400, "mode must be match or shift.")
    if body.source not in {"manual", "camera"}:
        raise EngineError(400, "source must be manual or camera.")
    if body.source == "camera" and not body.confirmed:
        raise EngineError(400, "Confirm the detected mood before requesting recommendations.")
    result = engine(request).recommend(body.user_id, body.limit, "hybrid", body.mood, body.mode, True)
    result["mood_source"] = body.source
    result["confirmed"] = body.confirmed or body.source == "manual"
    result["reported_confidence"] = body.confidence
    return result


@router.get("/analytics/listening")
def analytics(request: Request, user_id: str = Query(default="local-user")) -> dict:
    return engine(request).listening_analytics(user_id)


@router.get("/ml/config")
def get_config(request: Request) -> dict:
    return engine(request).config()


@router.post("/ml/config")
def post_config(body: ConfigIn, request: Request) -> dict:
    return engine(request).update_config(body.model_dump(exclude_none=True))


@router.get("/ml/evaluation")
def get_evaluation(request: Request) -> dict:
    return engine(request).last_evaluation()


@router.post("/ml/evaluate")
def post_evaluation(body: EvaluateIn, request: Request) -> dict:
    return engine(request).evaluate(body.k, body.diversify, body.include_svd)


@router.get("/ml/clusters")
def clusters(request: Request) -> dict:
    return engine(request).cluster_view()


@router.get("/library")
def library(request: Request, user_id: str = Query(default="local-user")) -> dict:
    return engine(request).library(user_id)


@router.get("/playlists")
def list_playlists(request: Request, user_id: str = Query(default="local-user")) -> dict:
    return engine(request).playlists(user_id)


@router.post("/playlists")
def create_playlist(body: PlaylistIn, request: Request) -> dict:
    return engine(request).create_playlist(body.user_id, body.name)


@router.delete("/playlists/{playlist_id}")
def delete_playlist(playlist_id: int, request: Request, user_id: str = Query(default="local-user")) -> dict:
    engine(request).delete_playlist(user_id, playlist_id)
    return {"deleted": playlist_id}


@router.delete("/playlists/{playlist_id}/tracks/{track_id}")
def remove_playlist_track(
    playlist_id: int,
    track_id: str,
    request: Request,
    user_id: str = Query(default="local-user"),
) -> dict:
    engine(request).remove_playlist_track(user_id, playlist_id, track_id)
    return {"removed": track_id}


def spotify_client(request: Request) -> SpotifyClient:
    client = getattr(request.app.state, "spotify", None)
    if client is None:
        client = SpotifyClient.from_settings(request.app.state.settings)
        request.app.state.spotify = client
    return client


@router.get("/spotify/status")
def spotify_status(request: Request) -> dict:
    client = spotify_client(request)
    return {"configured": client.configured, "market": client.market}


@router.get("/spotify/playlists")
def list_spotify_playlists(request: Request, user_id: str = Query(default="local-user")) -> dict:
    user_id = engine(request).require_user(user_id)
    return {"playlists": request.app.state.engine.db.list_spotify_playlists(user_id)}


@router.post("/spotify/playlists/generate")
def generate_spotify_playlist(body: SpotifyPlaylistIn, request: Request) -> dict:
    recommender = engine(request)
    user_id = recommender.require_user(body.user_id)
    if body.mood is not None and body.mood not in LISTENING_MOODS:
        raise EngineError(400, "Unknown listening mood.")
    genres: list[str] = []
    if body.use_profile:
        try:
            genres = list(recommender.taste(user_id)["explicit"]["genres"])
        except EngineError as exc:
            if exc.status != 404:
                raise
    queries = build_queries(body.prompt, body.mood, genres)
    if not queries:
        raise EngineError(400, "Describe the playlist or pick a mood.")
    client = spotify_client(request)
    if not client.configured:
        raise missing_credentials()
    found: list[dict] = []
    seen: set[str] = set()
    try:
        for query in queries:
            for track in client.search_tracks(query):
                if track["spotify_id"] in seen:
                    continue
                seen.add(track["spotify_id"])
                found.append(track)
    except SpotifyError as exc:
        raise EngineError(502, str(exc)) from exc
    tracks = pick_tracks(found, body.limit)
    if not tracks:
        raise EngineError(404, "Spotify returned no tracks for that description.")
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    saved = recommender.db.save_spotify_playlist(user_id, body.name.strip(), body.prompt.strip(), created_at, tracks)
    missing = sum(1 for track in tracks if not track["preview_url"])
    notes = [
        "Built from Spotify catalog search. The player uses only the 30-second preview URL Spotify returned.",
        "These tracks are not added to the recommendation model.",
    ]
    if missing:
        notes.append(
            f"Spotify did not include a preview for {missing} track{'s' if missing != 1 else ''}. Those open on Spotify."
        )
    return {**saved, "queries": queries, "notes": notes}


@router.delete("/spotify/playlists/{playlist_id}")
def delete_spotify_playlist(playlist_id: int, request: Request, user_id: str = Query(default="local-user")) -> dict:
    user_id = engine(request).require_user(user_id)
    if not request.app.state.engine.db.delete_spotify_playlist(playlist_id, user_id):
        raise EngineError(404, "Playlist not found.")
    return {"deleted": playlist_id}


def ytmusic_catalog(request: Request) -> YTMusicCatalog:
    catalog = getattr(request.app.state, "ytmusic", None)
    if catalog is None:
        catalog = YTMusicCatalog.from_settings(request.app.state.settings)
        request.app.state.ytmusic = catalog
    return catalog


@router.get("/ytmusic/status")
def ytmusic_status(request: Request) -> dict:
    catalog = ytmusic_catalog(request)
    return {"available": True, "location": catalog.location, "auth": "none"}


@router.get("/ytmusic/playlists")
def list_ytmusic_playlists(request: Request, user_id: str = Query(default="local-user")) -> dict:
    user_id = engine(request).require_user(user_id)
    playlists = request.app.state.engine.db.list_ytmusic_playlists(user_id)
    return {"playlists": _annotate_youtube(request, playlists)}


@router.post("/ytmusic/playlists/generate")
def generate_ytmusic_playlist(body: SpotifyPlaylistIn, request: Request) -> dict:
    recommender = engine(request)
    user_id = recommender.require_user(body.user_id)
    if body.mood is not None and body.mood not in LISTENING_MOODS:
        raise EngineError(400, "Unknown listening mood.")
    genres: list[str] = []
    if body.use_profile:
        try:
            genres = list(recommender.taste(user_id)["explicit"]["genres"])
        except EngineError as exc:
            if exc.status != 404:
                raise
    queries = build_queries(body.prompt, body.mood, genres)
    if not queries:
        raise EngineError(400, "Describe the playlist or pick a mood.")
    catalog = ytmusic_catalog(request)
    found: list[dict] = []
    seen: set[str] = set()
    try:
        for query in queries:
            for track in catalog.search_songs(query):
                if track["video_id"] in seen:
                    continue
                seen.add(track["video_id"])
                found.append(track)
    except YTMusicError as exc:
        raise EngineError(502, str(exc)) from exc
    tracks = pick_songs(found, body.limit)
    if not tracks:
        raise EngineError(404, "YouTube Music returned no songs for that description.")
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    saved = recommender.db.save_ytmusic_playlist(user_id, body.name.strip(), body.prompt.strip(), created_at, tracks)
    _annotate_youtube(request, [saved])
    return {
        **saved,
        "queries": queries,
        "notes": [
            "Built from YouTube Music search. Play uses the matching Apple Music preview.",
            "The song is not downloaded. A playlist saved here is not added to a YouTube Music account.",
        ],
    }


def _annotate_youtube(request: Request, playlists: list[dict]) -> list[dict]:
    if not request.app.state.settings.ytmusic_embed_check:
        return playlists
    tracks = [track for playlist in playlists for track in playlist.get("tracks", [])]
    mark_embeds(tracks, request.app.state.settings.data_dir / "youtube_embed_cache.json")
    return playlists


@router.delete("/ytmusic/playlists/{playlist_id}")
def delete_ytmusic_playlist(playlist_id: int, request: Request, user_id: str = Query(default="local-user")) -> dict:
    user_id = engine(request).require_user(user_id)
    if not request.app.state.engine.db.delete_ytmusic_playlist(playlist_id, user_id):
        raise EngineError(404, "Playlist not found.")
    return {"deleted": playlist_id}
