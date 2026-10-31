"""Explicit onboarding preferences and smoothed behavioral affinities.

A single event moves an affinity by a small EMA step. Ranking then blends
inferred values in with confidence n / (n + 8), so early listens cannot
replace the onboarding profile.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.ml.vocabulary import EVENT_STRENGTH, NUMERIC_KEYS


@dataclass
class ExplicitProfile:
    artists: list[str]
    genres: list[str]
    languages: list[str]
    purpose: str
    discovery: float
    energy: float
    danceability: float
    acousticness: float
    valence: float
    tempo: float

    def to_dict(self) -> dict:
        return {
            "artists": list(self.artists),
            "genres": list(self.genres),
            "languages": list(self.languages),
            "purpose": self.purpose,
            "discovery": self.discovery,
            "energy": self.energy,
            "danceability": self.danceability,
            "acousticness": self.acousticness,
            "valence": self.valence,
            "tempo": self.tempo,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExplicitProfile":
        return cls(
            artists=list(data.get("artists") or []),
            genres=list(data.get("genres") or []),
            languages=list(data.get("languages") or []),
            purpose=str(data.get("purpose") or "none"),
            discovery=float(data.get("discovery", 0.5)),
            energy=float(data.get("energy", 0.5)),
            danceability=float(data.get("danceability", 0.5)),
            acousticness=float(data.get("acousticness", 0.5)),
            valence=float(data.get("valence", 0.5)),
            tempo=float(data.get("tempo", 0.5)),
        )

    @classmethod
    def neutral(cls) -> "ExplicitProfile":
        """Used for synthetic eval users, who have no onboarding answers."""
        return cls(
            artists=[],
            genres=[],
            languages=[],
            purpose="none",
            discovery=0.5,
            energy=0.5,
            danceability=0.5,
            acousticness=0.5,
            valence=0.5,
            tempo=0.5,
        )


@dataclass
class InferredProfile:
    genre_affinity: dict[str, float] = field(default_factory=dict)
    language_affinity: dict[str, float] = field(default_factory=dict)
    artist_affinity: dict[str, float] = field(default_factory=dict)
    energy: float | None = None
    danceability: float | None = None
    acousticness: float | None = None
    valence: float | None = None
    tempo: float | None = None
    n_events: int = 0
    n_positive: int = 0
    plays_by_artist: dict[str, int] = field(default_factory=dict)
    plays_by_genre: dict[str, int] = field(default_factory=dict)
    plays_by_track: dict[str, int] = field(default_factory=dict)
    replays: int = 0
    completes: int = 0
    skips: int = 0

    @property
    def confidence(self) -> float:
        return self.n_positive / (self.n_positive + 8.0)

    def to_dict(self) -> dict:
        return {
            "genre_affinity": self.genre_affinity,
            "language_affinity": self.language_affinity,
            "artist_affinity": self.artist_affinity,
            "energy": self.energy,
            "danceability": self.danceability,
            "acousticness": self.acousticness,
            "valence": self.valence,
            "tempo": self.tempo,
            "n_events": self.n_events,
            "n_positive": self.n_positive,
            "confidence": self.confidence,
            "plays_by_artist": self.plays_by_artist,
            "plays_by_genre": self.plays_by_genre,
            "plays_by_track": self.plays_by_track,
            "replays": self.replays,
            "completes": self.completes,
            "skips": self.skips,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "InferredProfile":
        data = data or {}
        profile = cls(
            genre_affinity=dict(data.get("genre_affinity") or {}),
            language_affinity=dict(data.get("language_affinity") or {}),
            artist_affinity=dict(data.get("artist_affinity") or {}),
            energy=_optional_float(data.get("energy")),
            danceability=_optional_float(data.get("danceability")),
            acousticness=_optional_float(data.get("acousticness")),
            valence=_optional_float(data.get("valence")),
            tempo=_optional_float(data.get("tempo")),
            n_events=int(data.get("n_events") or 0),
            n_positive=int(data.get("n_positive") or 0),
            plays_by_artist={k: int(v) for k, v in (data.get("plays_by_artist") or {}).items()},
            plays_by_genre={k: int(v) for k, v in (data.get("plays_by_genre") or {}).items()},
            plays_by_track={k: int(v) for k, v in (data.get("plays_by_track") or {}).items()},
            replays=int(data.get("replays") or 0),
            completes=int(data.get("completes") or 0),
            skips=int(data.get("skips") or 0),
        )
        return profile

    @classmethod
    def empty(cls) -> "InferredProfile":
        return cls()


def _optional_float(value) -> float | None:
    if value is None:
        return None
    return float(value)


# Learning rates. Likes move the profile more than a passive play, and still
# only by a fraction of the gap to the target.
LEARNING_RATES: dict[str, float] = {
    "like": 0.20,
    "replay": 0.14,
    "playlist_add": 0.14,
    "complete": 0.10,
    "play": 0.05,
    "skip": 0.08,
    "dislike": 0.20,
}


def _event_target(event_type: str, listen_ratio: float) -> float:
    if event_type == "like":
        return 1.0
    if event_type == "replay":
        return 0.85
    if event_type == "playlist_add":
        return 0.75
    if event_type == "complete":
        return 0.70
    if event_type == "dislike":
        return -0.85
    if event_type == "skip":
        return -0.40
    # Partial plays are weak and depend on how much was heard.
    if listen_ratio >= 0.85:
        return 0.65
    if listen_ratio >= 0.5:
        return 0.40
    return 0.15


def _ema(previous: float, target: float, rate: float) -> float:
    updated = (1.0 - rate) * previous + rate * target
    return float(np.clip(updated, -1.0, 1.0))


def apply_event(profile: InferredProfile, track: Any, event_type: str, listen_ratio: float) -> None:
    """Update affinities in place. Callers replay events from oldest to newest."""
    ratio = float(np.clip(listen_ratio, 0.0, 1.0))
    target = _event_target(event_type, ratio)
    rate = LEARNING_RATES[event_type]
    profile.n_events += 1

    for genre in track.genres:
        profile.genre_affinity[genre] = _ema(profile.genre_affinity.get(genre, 0.0), target, rate)
    profile.language_affinity[track.language] = _ema(
        profile.language_affinity.get(track.language, 0.0), target, rate
    )
    profile.artist_affinity[track.artist] = _ema(
        profile.artist_affinity.get(track.artist, 0.0), target, rate
    )

    positive = target >= 0.35
    if positive:
        profile.n_positive += 1
        feature_values = {
            "energy": track.energy,
            "danceability": track.danceability,
            "acousticness": track.acousticness,
            "valence": track.valence,
            "tempo": track.tempo_norm,
        }
        for name, value in feature_values.items():
            if value is None:
                continue
            current = getattr(profile, name)
            # Start from an uninformative 0.5 so the first song nudges the
            # centroid instead of becoming the centroid.
            base = 0.5 if current is None else current
            setattr(profile, name, float(np.clip((1.0 - rate) * base + rate * value, 0.0, 1.0)))

    if event_type in {"play", "complete", "replay", "like", "playlist_add"}:
        profile.plays_by_artist[track.artist] = profile.plays_by_artist.get(track.artist, 0) + 1
        profile.plays_by_track[track.id] = profile.plays_by_track.get(track.id, 0) + 1
        for genre in track.genres:
            profile.plays_by_genre[genre] = profile.plays_by_genre.get(genre, 0) + 1
    if event_type == "replay":
        profile.replays += 1
    if event_type == "complete":
        profile.completes += 1
    if event_type == "skip":
        profile.skips += 1


def replay_events(events: list[dict], tracks_by_id: dict[str, Any]) -> InferredProfile:
    profile = InferredProfile.empty()
    ordered = sorted(events, key=lambda event: (int(event["ts"]), int(event.get("id") or 0)))
    for event in ordered:
        track = tracks_by_id.get(event["track_id"])
        if track is None:
            continue
        if event["event_type"] not in LEARNING_RATES:
            continue
        apply_event(profile, track, event["event_type"], float(event.get("listen_ratio") or 0.0))
    return profile


def interaction_weights(events: list[dict]) -> dict[str, float]:
    """Collapse the event log into per-track implicit weights."""
    totals: dict[str, float] = {}
    for event in events:
        event_type = event["event_type"]
        if event_type not in EVENT_STRENGTH:
            continue
        weight = EVENT_STRENGTH[event_type]
        if event_type == "play":
            weight *= max(float(event.get("listen_ratio") or 0.0), 0.15)
        totals[event["track_id"]] = totals.get(event["track_id"], 0.0) + weight
    return {track_id: float(np.clip(value, -3.0, 6.0)) for track_id, value in totals.items()}


def blended_characteristics(explicit: ExplicitProfile, inferred: InferredProfile) -> dict[str, float]:
    """Blend onboarding sliders with the behavioral centroid by confidence."""
    confidence = inferred.confidence
    explicit_values = {
        "energy": explicit.energy,
        "danceability": explicit.danceability,
        "acousticness": explicit.acousticness,
        "valence": explicit.valence,
        "tempo": explicit.tempo,
    }
    blended: dict[str, float] = {}
    for name, explicit_value in explicit_values.items():
        inferred_value = getattr(inferred, name)
        if inferred_value is None or confidence <= 0:
            blended[name] = explicit_value
        else:
            blended[name] = (1.0 - confidence) * explicit_value + confidence * inferred_value
    return blended


def numeric_names_for_profile() -> tuple[str, ...]:
    return NUMERIC_KEYS
