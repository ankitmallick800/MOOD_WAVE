"""Ties the catalog, live profile, and ranker together.

Collaborative similarities are fit once on the synthetic matrix. Live clicks
update the saved profile and the query weights. They do not refit the model.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

import joblib
import numpy as np

from app.audio.cluster import cluster_catalog
from app.audio.extract import extract_audio_file, librosa_status
from app.config import Settings
from app.data.catalog import Track, track_blocks
from app.data.demo_catalog import FEATURE_SOURCE, build_demo_catalog
from app.data.ingest import IngestError, load_catalog_csv
from app.data.synthetic import ORIGIN, generate_interactions
from app.providers.itunes import (
    ItunesError,
    ensure_itunes_catalog,
    identity_key,
    is_browse_noise,
    pick_itunes_match,
    search_itunes,
)
from app.providers.records import track_from_record, track_record
from app.providers.youtube import track_from_youtube
from app.db import Database
from app.ml.collaborative import ItemItemModel, SVDModel, build_matrix, popularity_scores
from app.ml.evaluate import evaluate_models
from app.ml.features import masked_weighted_cosine
from app.ml.hybrid import rank_tracks
from app.ml.mood import interpret_expression
from app.ml.profile import ExplicitProfile, InferredProfile, interaction_weights, replay_events
from app.ml.vocabulary import (
    DEFAULT_GROUP_WEIGHTS,
    DEFAULT_WEIGHTS,
    DIVERSITY_LAMBDA_DEFAULT,
    GENRES,
    LANGUAGE_LABELS,
    LISTENING_MOODS,
    MIN_COLLAB_TRACKS,
    PURPOSE_LABELS,
    PURPOSES,
)

logger = logging.getLogger("moodwave.engine")

AUDIO_EXTENSIONS = (".wav", ".mp3", ".flac", ".ogg")


class EngineError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class Engine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db = Database(settings.db_path)
        self.tracks: list[Track] = []
        self.tracks_by_id: dict[str, Track] = {}
        self.events: list[dict] = []
        self.item_item = ItemItemModel()
        self.svd = SVDModel()
        self.popularity: dict[str, float] = {}
        self.clusters: dict = {}
        self.dataset_origin = "synthetic_demo"
        self.catalog_warning: str | None = None
        self._identity: dict[str, Track] = {}
        self._lock = threading.Lock()
        self._last_evaluation: dict | None = None
        self.weights = dict(DEFAULT_WEIGHTS)
        self.group_weights = dict(DEFAULT_GROUP_WEIGHTS)
        self.diversity_lambda = DIVERSITY_LAMBDA_DEFAULT
        self.artist_cap = 2
        self.recommendation_limit = 20

    def startup(self) -> None:
        np.random.seed(self.settings.seed)
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings.audio_dir.mkdir(parents=True, exist_ok=True)
        self.settings.audio_features_dir.mkdir(parents=True, exist_ok=True)
        self.settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._load_sources()
        self._fit_models()
        self.clusters = cluster_catalog(self.tracks, seed=self.settings.seed)
        self._load_config()
        source = self.tracks[0].feature_source if self.tracks else "none"
        logger.info(
            "MOODWAVE ready: %s tracks, %s events, origin %s, feature source %s",
            len(self.tracks),
            len(self.events),
            self.dataset_origin,
            source,
        )

    def _load_sources(self) -> None:
        if self.settings.catalog_csv:
            tracks, report = load_catalog_csv(self.settings.catalog_csv, impute_numeric=False)
            self.tracks = tracks
            self.dataset_origin = "external_catalog"
            logger.info("Loaded external catalog: %s accepted, %s rejected", report["tracks_accepted"], len(report["rejected"]))
        elif self.settings.catalog_source == "itunes":
            self.tracks, self.catalog_warning = ensure_itunes_catalog(self.settings.data_dir / "itunes_catalog.json")
            self.dataset_origin = "itunes_catalog"
            logger.info("Loaded %s Apple Music catalog tracks", len(self.tracks))
        else:
            self.tracks = build_demo_catalog()
            self.dataset_origin = "synthetic_demo"
            self._write_catalog_snapshot()
        self._reindex()
        if self.settings.catalog_source == "itunes" and not self.settings.catalog_csv:
            self._load_extras()

        if self.settings.interactions_json:
            payload = json.loads(self.settings.interactions_json.read_text(encoding="utf-8"))
            events = payload["events"] if isinstance(payload, dict) else payload
            if not isinstance(events, list):
                raise EngineError(500, "Interaction file must be a list or an object with an events list.")
            self.events = events
            origin = payload.get("origin", "external") if isinstance(payload, dict) else "external"
            self.dataset_origin = "synthetic_demo" if origin == "synthetic" else "external_interactions"
            logger.info("Loaded %s interactions from file", len(events))
        elif self.settings.catalog_csv or self.settings.catalog_source == "itunes":
            self.events = []
            if self.settings.catalog_csv:
                self.dataset_origin = "external_catalog_without_interactions"
            logger.warning("Catalog loaded without an interaction file. Collaborative filtering stays off.")
        else:
            self.events = generate_interactions(self.tracks, seed=self.settings.seed)
            self.dataset_origin = "synthetic_demo"
            self._write_interactions_snapshot()

    def _write_catalog_snapshot(self) -> None:
        path = self.settings.data_dir / "demo_catalog.json"
        payload = {
            "origin": "editorial_demo",
            "feature_source": FEATURE_SOURCE,
            "warning": "Fictional catalog. Audio numbers are editorial metadata, not measurements.",
            "tracks": [track.to_public_dict() for track in self.tracks],
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _write_interactions_snapshot(self) -> None:
        path = self.settings.data_dir / "synthetic_interactions.json"
        users = sorted({event["user_id"] for event in self.events})
        payload = {
            "origin": ORIGIN,
            "seed": self.settings.seed,
            "warning": "Generated interactions. Not real listeners.",
            "n_users": len(users),
            "n_events": len(self.events),
            "events": self.events,
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _fit_models(self) -> None:
        item_ids = [track.id for track in self.tracks]
        user_ids = sorted({event["user_id"] for event in self.events})
        if len(user_ids) < 3 or len(item_ids) < 3:
            self.item_item = ItemItemModel()
            self.svd = SVDModel()
            self.popularity = {track_id: 0.0 for track_id in item_ids}
            logger.warning("Collaborative models were not fit. Need at least 3 users and 3 tracks with interactions.")
            return
        matrix = build_matrix(user_ids, item_ids, self.events)
        self.item_item.fit(item_ids, matrix)
        self.svd.fit(user_ids, item_ids, matrix)
        self.popularity = popularity_scores(item_ids, matrix)
        joblib.dump(
            {
                "seed": self.settings.seed,
                "n_users": len(user_ids),
                "n_tracks": len(item_ids),
                "n_events": len(self.events),
                "popularity": self.popularity,
            },
            self.settings.artifacts_dir / "popularity.joblib",
        )

    def _load_config(self) -> None:
        stored = self.db.get_kv("rank_config")
        if not stored:
            return
        self.weights.update({key: float(stored["weights"][key]) for key in DEFAULT_WEIGHTS if key in stored.get("weights", {})})
        if stored.get("group_weights"):
            self.group_weights.update(stored["group_weights"])
        self.diversity_lambda = float(stored.get("diversity_lambda", self.diversity_lambda))
        self.artist_cap = int(stored.get("artist_cap", self.artist_cap))
        self.recommendation_limit = int(stored.get("limit", self.recommendation_limit))

    def health(self) -> dict:
        users = sorted({event["user_id"] for event in self.events})
        audio = librosa_status()
        demo = self.dataset_origin == "synthetic_demo"
        feature_source = self.tracks[0].feature_source if self.tracks else "none"
        warnings = [
            "Facial analysis, when enabled, runs in the browser. This server does not accept face images.",
        ]
        if self.catalog_warning:
            warnings.insert(0, self.catalog_warning)
        if demo:
            warnings.insert(0, "The catalog is fictional and its audio features are editorial.")
            warnings.insert(1, "Collaborative filtering is fit on generated listeners, not real behavior.")
        elif self._catalog_kind() == "metadata":
            warnings.insert(0, "Tempo, energy, danceability, valence, and mood are unknown for this catalog. They are not filled in.")
            warnings.insert(1, "Playback uses an official preview, an official embed, or a link. Songs are not downloaded.")
            if not self.events:
                warnings.append("Collaborative filtering is off until enough listening is saved in this app.")
        elif not self.events:
            warnings.insert(0, "No interaction file is loaded, so collaborative filtering is off.")
        return {
            "status": "ok",
            "demo_mode": demo,
            "dataset_origin": self.dataset_origin,
            "catalog_tracks": len(self.tracks),
            "synthetic_users": len(users) if demo else 0,
            "synthetic_interactions": len(self.events) if demo else 0,
            "interaction_count": len(self.events),
            "feature_source": feature_source,
            "models": {
                "content": "weighted_masked_cosine",
                "collaborative": "item_item_cosine" if self.item_item.fitted else "not_fit",
                "collaborative_svd": "truncated_svd" if self.svd.fitted else "not_fit",
                "popularity": "log_scaled_positive_mass" if self.events else "unavailable",
                "audio_extraction": "librosa_ready" if audio["available"] else "librosa_unavailable",
                "clustering": "ready" if self.clusters.get("available") else "unavailable",
                "vision": "browser_local_face_expression",
            },
            "librosa": audio,
            "warnings": warnings,
        }

    def facets(self) -> dict:
        artists: dict[str, dict] = {}
        for track in self.tracks:
            bucket = artists.setdefault(track.artist, {"name": track.artist, "genres": set(), "count": 0})
            bucket["genres"].update(track.genres)
            bucket["count"] += 1
        languages: dict[str, int] = {}
        for track in self.tracks:
            languages[track.language] = languages.get(track.language, 0) + 1
        return {
            "genres": list(GENRES),
            "languages": [
                {"code": code, "label": LANGUAGE_LABELS[code], "count": languages.get(code, 0)}
                for code in LANGUAGE_LABELS
            ],
            "artists": [
                {"name": name, "genres": sorted(info["genres"]), "count": info["count"]}
                for name, info in sorted(artists.items())
            ],
            "moods": list(LISTENING_MOODS),
            "purposes": [{"id": purpose, "label": PURPOSE_LABELS[purpose]} for purpose in PURPOSES if purpose != "none"],
        }

    def require_user(self, user_id: str) -> str:
        if not user_id or user_id.startswith("synth-"):
            raise EngineError(400, "The live listener id cannot be a synthetic demo user.")
        if len(user_id) > 64 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in user_id):
            raise EngineError(400, "user_id may contain only letters, numbers, hyphens, and underscores.")
        return user_id

    def save_onboarding(self, user_id: str, explicit: ExplicitProfile, reset_inferred: bool) -> dict:
        user_id = self.require_user(user_id)
        with self._lock:
            if reset_inferred:
                self.db.clear_behavior(user_id)
            self.db.save_profile(user_id, explicit.to_dict(), _now())
        return self.taste(user_id)

    def taste(self, user_id: str) -> dict:
        user_id = self.require_user(user_id)
        stored = self.db.get_profile(user_id)
        if stored is None:
            raise EngineError(404, "No onboarding profile for this listener yet.")
        explicit = ExplicitProfile.from_dict(stored["explicit"])
        inferred = replay_events(self.db.list_events(user_id), self.tracks_by_id)
        positive_tracks = sum(1 for weight in interaction_weights(self.db.list_events(user_id)).values() if weight > 0)
        # One listener can have several likes and still have no collaborative
        # model. The item-item matrix needs other listeners before it is fit.
        collab_ready = self.item_item.fitted and positive_tracks >= MIN_COLLAB_TRACKS
        if collab_ready:
            stage = "hybrid"
        elif inferred.n_events == 0:
            stage = "cold_start_content"
        else:
            stage = "content_with_early_feedback"
        return {
            "user_id": user_id,
            "explicit": explicit.to_dict(),
            "inferred": inferred.to_dict(),
            "stage": stage,
            "positive_tracks": positive_tracks,
            "collaborative_unlocked": collab_ready,
            "session_mood": None,
            "notes": [
                "Explicit preferences come from onboarding and stay until you edit them.",
                "Inferred preferences are rebuilt by replaying your events with a small learning rate.",
                "Session mood is not stored in this profile. Pass it when you ask for recommendations.",
                f"Confidence is {inferred.confidence:.2f}. Ranking blends inferred taste at that rate.",
            ],
        }

    def reset(self, user_id: str, scope: str) -> dict:
        user_id = self.require_user(user_id)
        with self._lock:
            if scope == "all":
                self.db.delete_profile(user_id)
                return {"user_id": user_id, "reset": "all"}
            if self.db.get_profile(user_id) is None:
                raise EngineError(404, "No onboarding profile for this listener yet.")
            self.db.clear_behavior(user_id)
        return self.taste(user_id)

    def record_feedback(self, user_id: str, track_id: str, event_type: str, listen_ms: int, duration_ms: int, playlist_id: int | None) -> dict:
        user_id = self.require_user(user_id)
        track = self._track(track_id)
        if self.db.get_profile(user_id) is None:
            raise EngineError(400, "Finish onboarding before sending listening feedback.")
        duration = duration_ms or track.duration_ms
        ratio = 0.0 if duration <= 0 else max(0.0, min(1.0, listen_ms / duration))
        if event_type == "play" and ratio == 0.0 and listen_ms <= 0:
            ratio = 0.2
        if event_type == "playlist_add" and playlist_id is None:
            raise EngineError(400, "playlist_id is required when adding a track to a playlist.")
        now = int(time.time())
        with self._lock:
            if event_type == "playlist_add" and not self.db.add_playlist_track(playlist_id, user_id, track_id, _now()):
                raise EngineError(404, "Playlist not found.")
            if event_type == "like":
                self.db.set_reaction(user_id, track_id, "like")
            elif event_type == "dislike":
                self.db.set_reaction(user_id, track_id, "dislike")
            self.db.add_event(user_id, track_id, event_type, now, listen_ms, duration, ratio)
        return self.taste(user_id)

    def set_reaction(self, user_id: str, track_id: str, reaction: str) -> dict:
        user_id = self.require_user(user_id)
        self._track(track_id)
        if self.db.get_profile(user_id) is None:
            raise EngineError(400, "Finish onboarding before saving a reaction.")
        with self._lock:
            current = self.db.reactions(user_id).get(track_id, "none")
            if reaction == "none":
                if current != "none":
                    self.db.delete_latest_reaction_event(user_id, track_id)
                self.db.set_reaction(user_id, track_id, "none")
            elif reaction != current:
                self.db.set_reaction(user_id, track_id, reaction)
                self.db.add_event(user_id, track_id, reaction, int(time.time()), 0, 0, 1.0 if reaction == "like" else 0.2)
        return self.taste(user_id)

    def recommend(
        self,
        user_id: str,
        limit: int | None = None,
        strategy: str = "hybrid",
        mood: str | None = None,
        mood_mode: str | None = None,
        diversify: bool | None = None,
    ) -> dict:
        user_id = self.require_user(user_id)
        explicit, inferred, reactions = self._profiles(user_id)
        weights_user = interaction_weights(self.db.list_events(user_id))
        collab = self._collab_for(strategy, user_id, weights_user)
        chosen, meta = rank_tracks(
            self._rankable_tracks(),
            explicit,
            inferred,
            collab,
            self.popularity,
            neighbor_for=self._neighbor_lookup(weights_user) if strategy in {"hybrid", "collaborative"} else None,
            weights=self.weights,
            group_weights=self.group_weights,
            mood=mood,
            mood_mode=mood_mode or "match",
            strategy=strategy,
            diversify=self._diversify_default() if diversify is None else diversify,
            limit=limit or self.recommendation_limit,
            artist_cap=self.artist_cap,
            diversity_lambda=self.diversity_lambda,
            reactions=reactions,
            catalog_kind=self._catalog_kind(),
        )
        return {
            "user_id": user_id,
            "items": [item.to_dict() for item in chosen],
            **meta,
            "dataset_origin": self.dataset_origin,
        }

    def _collab_for(self, strategy: str, user_id: str, weights_user: dict[str, float]):
        if strategy == "popularity" or strategy == "content":
            return None
        if strategy == "collaborative_svd":
            return self.svd.score_fold_in(weights_user, MIN_COLLAB_TRACKS)
        return self.item_item.score(weights_user, MIN_COLLAB_TRACKS)

    def _neighbor_lookup(self, weights_user: dict[str, float]):
        def lookup(track_id: str):
            found = self.item_item.best_neighbor(track_id, weights_user)
            if found is None:
                return None
            other_id, similarity = found
            other = self.tracks_by_id.get(other_id)
            if other is None:
                return None
            return {"track_id": other.id, "title": other.title, "artist": other.artist, "similarity": round(similarity, 4)}

        return lookup

    def _profiles(self, user_id: str) -> tuple[ExplicitProfile, InferredProfile, dict[str, str]]:
        stored = self.db.get_profile(user_id)
        if stored is None:
            raise EngineError(400, "Finish onboarding before asking for recommendations.")
        explicit = ExplicitProfile.from_dict(stored["explicit"])
        events = self.db.list_events(user_id)
        inferred = replay_events(events, self.tracks_by_id)
        return explicit, inferred, self.db.reactions(user_id)

    def _diversify_default(self) -> bool:
        return True

    def search(
        self,
        query: str,
        genre: str | None,
        language: str | None,
        mood: str | None,
        limit: int,
        user_id: str | None = None,
    ) -> dict:
        needle = query.casefold().strip()
        disliked = self._disliked_ids(user_id)
        warning = None
        if (
            self.settings.catalog_source == "itunes"
            and not self.settings.catalog_csv
            and len(needle) >= 3
            and len(self._filter_tracks(needle, genre, language, mood, limit, disliked)) < min(limit, 8)
        ):
            try:
                for track in search_itunes(query, self.settings.itunes_country, limit=15):
                    self._adopt(track, persist=True)
            except ItunesError:
                warning = "Apple Music search is unavailable. Showing songs already in the catalog."
        matches = [
            track.to_public_dict()
            for track in self._filter_tracks(needle, genre, language, mood, limit, disliked)
        ]
        return {"query": query, "count": len(matches), "tracks": matches, "warning": warning}

    def similar(self, track_id: str, limit: int) -> dict:
        track = self._track(track_id)
        source = track_blocks(track)
        ranked = []
        for other in self._rankable_tracks():
            if other.id == track.id:
                continue
            score = masked_weighted_cosine(source, track_blocks(other), self.group_weights)
            if score is None:
                continue
            shared_genres = [genre for genre in other.genres if genre in track.genres]
            shared_moods = [mood for mood in other.mood_tags if mood in track.mood_tags]
            has_audio = track.energy is not None or other.energy is not None or track.tempo is not None
            if shared_genres and shared_moods and has_audio:
                explanation = f"Shares {shared_genres[0]} and the {shared_moods[0]} tag, with close audio metadata."
            elif shared_genres and has_audio:
                explanation = f"Shares the {shared_genres[0]} genre and close audio metadata."
            elif shared_genres:
                explanation = f"Shares the {shared_genres[0]} genre."
            elif has_audio:
                explanation = "Close on the observed audio-feature dimensions."
            else:
                explanation = "Similar on the catalog metadata both songs include."
            ranked.append((score, other, explanation))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return {
            "track_id": track.id,
            "feature_source": track.feature_source,
            "method": "masked_weighted_cosine_on_catalog_features",
            "items": [
                {
                    "track": other.to_public_dict(),
                    "similarity": round(score, 6),
                    "explanations": [explanation],
                }
                for score, other, explanation in ranked[:limit]
            ],
        }

    def predict_mood(self, distribution: dict[str, float]) -> dict:
        try:
            return interpret_expression(distribution)
        except ValueError as exc:
            raise EngineError(400, str(exc)) from exc

    def listening_analytics(self, user_id: str) -> dict:
        user_id = self.require_user(user_id)
        events = self.db.list_events(user_id)
        by_genre: dict[str, dict] = {}
        by_language: dict[str, dict] = {}
        by_hour = [{"hour": hour, "plays": 0} for hour in range(24)]
        listens = completes = skips = likes = 0
        listen_ms = 0
        for event in events:
            track = self.tracks_by_id.get(event["track_id"])
            if event["event_type"] in {"play", "complete", "replay"}:
                listens += 1
                listen_ms += int(event["listen_ms"])
                hour = time.localtime(int(event["ts"])).tm_hour
                by_hour[hour]["plays"] += 1
            if event["event_type"] == "complete":
                completes += 1
            if event["event_type"] == "skip":
                skips += 1
            if event["event_type"] == "like":
                likes += 1
            if track is None:
                continue
            for genre in track.genres:
                bucket = by_genre.setdefault(genre, {"genre": genre, "plays": 0, "listen_ms": 0})
                if event["event_type"] in {"play", "complete", "replay", "like"}:
                    bucket["plays"] += 1
                    bucket["listen_ms"] += int(event["listen_ms"])
            language_bucket = by_language.setdefault(
                track.language,
                {"language": track.language, "label": LANGUAGE_LABELS.get(track.language, track.language), "plays": 0},
            )
            if event["event_type"] in {"play", "complete", "replay", "like"}:
                language_bucket["plays"] += 1
        play_like = listens + skips
        return {
            "user_id": user_id,
            "events": len(events),
            "listens": listens,
            "completes": completes,
            "skips": skips,
            "likes": likes,
            "listen_ms": listen_ms,
            "completion_rate": None if play_like == 0 else completes / play_like,
            "skip_rate": None if play_like == 0 else skips / play_like,
            "by_genre": sorted(by_genre.values(), key=lambda item: item["plays"], reverse=True),
            "by_language": sorted(by_language.values(), key=lambda item: item["plays"], reverse=True),
            "by_hour": by_hour,
            "note": "Computed from your events only. Synthetic demo listeners are not included.",
        }

    def config(self) -> dict:
        return {
            "weights": self.weights,
            "group_weights": self.group_weights,
            "diversity_lambda": self.diversity_lambda,
            "artist_cap": self.artist_cap,
            "limit": self.recommendation_limit,
            "weight_notes": {
                "content": "Weighted cosine between your profile vector and the track. Missing features are left out.",
                "collaborative": (
                    "Item-item score from the synthetic matrix. Dropped until you have 3 positive tracks."
                    if self.dataset_origin == "synthetic_demo"
                    else "Item-item score from saved listening. Dropped until you have 3 positive tracks."
                ),
                "preference": "Overlap with stated and learned genres, languages, artists, and any audio ranges the track actually has.",
                "mood": "Closeness to the session listening target. Dropped when no mood is selected or the track has no mood features.",
                "discovery": "Bonus for less familiar artists. Its effect scales with your exploration slider.",
            },
            "group_weight_notes": {
                "numeric": "Used only for tempo, energy, and the other audio values a track actually includes.",
                "genre": "Shared genre labels from the catalog.",
                "language": "Used only when the catalog states a language.",
                "mood": "Mood tags, only when the catalog includes them.",
            },
        }

    def update_config(self, payload: dict) -> dict:
        with self._lock:
            if "weights" in payload:
                for key, value in payload["weights"].items():
                    if key not in DEFAULT_WEIGHTS:
                        raise EngineError(400, f"Unknown weight: {key}")
                    self.weights[key] = float(value)
            if "group_weights" in payload:
                for key, value in payload["group_weights"].items():
                    if key not in DEFAULT_GROUP_WEIGHTS:
                        raise EngineError(400, f"Unknown group weight: {key}")
                    self.group_weights[key] = float(value)
            if "diversity_lambda" in payload:
                self.diversity_lambda = float(payload["diversity_lambda"])
            if "artist_cap" in payload:
                self.artist_cap = int(payload["artist_cap"])
            if "limit" in payload:
                self.recommendation_limit = int(payload["limit"])
            if sum(self.weights.values()) <= 0:
                raise EngineError(400, "At least one model weight must be positive.")
            self.db.set_kv(
                "rank_config",
                {
                    "weights": self.weights,
                    "group_weights": self.group_weights,
                    "diversity_lambda": self.diversity_lambda,
                    "artist_cap": self.artist_cap,
                    "limit": self.recommendation_limit,
                },
            )
        return self.config()

    def evaluate(self, k: int, diversify: bool, include_svd: bool) -> dict:
        strategies = ["popularity", "content", "collaborative", "hybrid"]
        if include_svd:
            strategies.append("collaborative_svd")
        result = evaluate_models(
            self.tracks,
            self.events,
            k=k,
            weights=self.weights,
            group_weights=self.group_weights,
            strategies=tuple(strategies),
            diversify=diversify,
            origin=self.dataset_origin,
        )
        self._last_evaluation = result
        return result

    def last_evaluation(self) -> dict:
        if self._last_evaluation is None:
            return {
                "available": False,
                "message": "No evaluation has been run in this session. Run one from Model Lab.",
            }
        return {"available": True, "result": self._last_evaluation}

    def cluster_view(self) -> dict:
        return self.clusters

    def analyze_track_audio(self, track_id: str) -> dict:
        track = self._track(track_id)
        path = self._audio_path(track_id)
        if path is None:
            raise EngineError(
                404,
                "No audio file is attached for this track. Place a wav, mp3, flac, or ogg file in the server audio directory using the track id as the file name.",
            )
        try:
            features = extract_audio_file(path)
        except RuntimeError as exc:
            raise EngineError(503, str(exc)) from exc
        except ValueError as exc:
            raise EngineError(400, str(exc)) from exc
        destination = self.settings.audio_features_dir / f"{track_id}.json"
        destination.write_text(json.dumps({"track_id": track.id, "features": features}, indent=2), encoding="utf-8")
        return {"track_id": track.id, "features": features}

    def _audio_path(self, track_id: str) -> Path | None:
        root = self.settings.audio_dir.resolve()
        for extension in AUDIO_EXTENSIONS:
            candidate = (root / f"{track_id}{extension}").resolve()
            if root not in candidate.parents and candidate != root:
                continue
            if candidate.is_file():
                return candidate
        return None

    def create_playlist(self, user_id: str, name: str) -> dict:
        user_id = self.require_user(user_id)
        playlist_id = self.db.create_playlist(user_id, name.strip(), _now())
        return {"id": playlist_id, "name": name.strip(), "track_ids": []}

    def playlists(self, user_id: str) -> dict:
        user_id = self.require_user(user_id)
        lists = []
        for playlist in self.db.list_playlists(user_id):
            lists.append(
                {
                    **playlist,
                    "tracks": [
                        self.tracks_by_id[track_id].to_public_dict()
                        for track_id in playlist["track_ids"]
                        if track_id in self.tracks_by_id
                    ],
                }
            )
        return {"playlists": lists}

    def delete_playlist(self, user_id: str, playlist_id: int) -> None:
        user_id = self.require_user(user_id)
        if not self.db.delete_playlist(playlist_id, user_id):
            raise EngineError(404, "Playlist not found.")

    def library(self, user_id: str) -> dict:
        user_id = self.require_user(user_id)
        reactions = self.db.reactions(user_id) if self.db.get_profile(user_id) else {}
        return {
            "tracks": [track.to_public_dict() for track in self.tracks],
            "liked": [self.tracks_by_id[track_id].to_public_dict() for track_id, reaction in reactions.items() if reaction == "like" and track_id in self.tracks_by_id],
            "disliked": [track_id for track_id, reaction in reactions.items() if reaction == "dislike"],
        }

    def import_provider_track(self, user_id: str, payload: dict) -> dict:
        self.require_user(user_id)
        if payload.get("provider") != "youtube":
            raise EngineError(400, "This catalog import accepts YouTube songs.")
        try:
            track = track_from_youtube(payload)
        except ValueError as exc:
            raise EngineError(400, str(exc)) from exc
        return self._adopt(track, persist=True).to_public_dict()

    def match_apple_track(self, user_id: str, title: str, artist: str) -> dict:
        self.require_user(user_id)
        if self.settings.catalog_source != "itunes" or self.settings.catalog_csv:
            raise EngineError(404, "Apple Music matching is available on the Apple Music catalog.")
        title = title.strip()
        artist = artist.strip()
        if not title or not artist:
            raise EngineError(400, "A song needs a title and an artist.")
        found: list[Track] = []
        seen: set[str] = set()
        try:
            for query in (f"{title} {artist}", title):
                for track in search_itunes(query, self.settings.itunes_country, limit=15):
                    if track.id in seen:
                        continue
                    seen.add(track.id)
                    found.append(track)
        except ItunesError as exc:
            raise EngineError(502, "Apple Music search is unavailable.") from exc
        chosen = pick_itunes_match(found, title, artist)
        if chosen is None:
            raise EngineError(404, "Apple Music has no matching song for that title and artist.")
        return self._adopt(chosen, persist=True).to_public_dict()

    def remove_playlist_track(self, user_id: str, playlist_id: int, track_id: str) -> None:
        user_id = self.require_user(user_id)
        if not self.db.remove_playlist_track(playlist_id, user_id, track_id):
            raise EngineError(404, "Playlist not found.")

    def _catalog_kind(self) -> str:
        if self.dataset_origin == "synthetic_demo":
            return "demo"
        if not self.tracks:
            return "metadata" if self.dataset_origin == "itunes_catalog" else "external"
        has_audio = any(track.energy is not None or track.tempo is not None or track.mood_tags for track in self.tracks)
        return "external" if has_audio else "metadata"

    def _rankable_tracks(self) -> list[Track]:
        if self.settings.catalog_source == "itunes" and not self.settings.catalog_csv:
            return [track for track in self.tracks if not is_browse_noise(track)]
        return list(self.tracks)

    def _disliked_ids(self, user_id: str | None) -> set[str]:
        if not user_id or user_id.startswith("synth-"):
            return set()
        return {track_id for track_id, reaction in self.db.reactions(user_id).items() if reaction == "dislike"}

    def _filter_tracks(
        self,
        needle: str,
        genre: str | None,
        language: str | None,
        mood: str | None,
        limit: int,
        disliked: set[str] | None = None,
    ) -> list[Track]:
        hidden = disliked or set()
        hide_noise = self.settings.catalog_source == "itunes" and not self.settings.catalog_csv
        matches: list[Track] = []
        for track in self.tracks:
            if track.id in hidden:
                continue
            if hide_noise and is_browse_noise(track):
                continue
            if genre and genre not in track.genres:
                continue
            if language and track.language != language:
                continue
            if mood and mood not in track.mood_tags:
                continue
            if needle:
                haystack = " ".join(
                    [
                        track.title,
                        track.artist,
                        track.album,
                        " ".join(track.genres),
                        " ".join(track.genre_labels),
                        " ".join(track.mood_tags),
                    ]
                ).casefold()
                if needle not in haystack:
                    continue
            matches.append(track)
            if len(matches) >= limit:
                break
        return matches

    def _reindex(self) -> None:
        self.tracks_by_id = {track.id: track for track in self.tracks}
        self._identity = {}
        for track in self.tracks:
            key = identity_key(track.title, track.artist)
            if key and key not in self._identity:
                self._identity[key] = track

    def _load_extras(self) -> None:
        for payload in self.db.list_catalog_extra():
            try:
                track = track_from_record(payload)
            except (KeyError, TypeError, ValueError):
                continue
            key = identity_key(track.title, track.artist)
            if track.id in self.tracks_by_id or (key and key in self._identity):
                continue
            self.tracks.append(track)
            self.tracks_by_id[track.id] = track
            if key:
                self._identity[key] = track

    def _adopt(self, track: Track, persist: bool) -> Track:
        key = identity_key(track.title, track.artist)
        with self._lock:
            if key and key in self._identity:
                return self._identity[key]
            current = self.tracks_by_id.get(track.id)
            if current is not None:
                return current
            self.tracks.append(track)
            self.tracks_by_id[track.id] = track
            if key:
                self._identity[key] = track
            self.popularity.setdefault(track.id, 0.0)
            if persist:
                self.db.save_catalog_extra(track.id, track_record(track))
        return track

    def _track(self, track_id: str) -> Track:
        track = self.tracks_by_id.get(track_id)
        if track is None:
            raise EngineError(404, "Track not found.")
        return track

    def replace_catalog_from_csv(self, path: Path) -> dict:
        try:
            tracks, report = load_catalog_csv(path, impute_numeric=False)
        except IngestError as exc:
            raise EngineError(400, str(exc)) from exc
        with self._lock:
            self.tracks = tracks
            self._reindex()
            self.dataset_origin = "external_catalog_synthetic_interactions_removed"
            self.events = []
            self.popularity = {track.id: 0.0 for track in tracks}
            self.item_item = ItemItemModel()
            self.svd = SVDModel()
            self.clusters = cluster_catalog(self.tracks, seed=self.settings.seed)
            self._last_evaluation = None
        report["warning"] = (
            "External catalog loaded. The synthetic interaction matrix was cleared because those "
            "events pointed at the demo tracks. Collaborative filtering stays off until an interaction file is provided."
        )
        return report


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
