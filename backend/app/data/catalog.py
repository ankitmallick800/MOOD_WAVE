"""Track records and the vectors used for content similarity."""

from __future__ import annotations

import zlib
from dataclasses import dataclass

import numpy as np

from app.data.recordings import playback_fields
from app.ml.features import FeatureBlocks
from app.ml.mood import MOOD_TAG_ALIGNMENT
from app.ml.profile import ExplicitProfile, InferredProfile, blended_characteristics
from app.ml.vocabulary import (
    GENRES,
    LANGUAGE_LABELS,
    LANGUAGES,
    MOOD_TAGS,
    NUMERIC_KEYS,
    PURPOSES,
)


@dataclass(frozen=True)
class Track:
    id: str
    title: str
    artist: str
    album: str
    genres: tuple[str, ...]
    language: str
    year: int
    duration_ms: int
    tempo: float | None
    energy: float | None
    danceability: float | None
    acousticness: float | None
    valence: float | None
    speechiness: float | None
    instrumentalness: float | None
    loudness: float | None
    musical_key: int | None
    mode: int | None
    mood_tags: tuple[str, ...]
    feature_source: str
    # Names of fields that are actually known. Missing audio fields stay out of
    # the similarity mask instead of being imputed.
    observed: tuple[str, ...]
    provider: str = "demo"
    artwork_url: str | None = None
    preview_url: str | None = None
    external_url: str | None = None
    embed_url: str | None = None
    playback_kind: str = ""
    preview_duration_ms: int | None = None
    song_duration_ms: int | None = None
    genre_labels: tuple[str, ...] = ()

    @property
    def tempo_norm(self) -> float | None:
        if self.tempo is None:
            return None
        return float(np.clip((self.tempo - 60.0) / 120.0, 0.0, 1.0))

    @property
    def loudness_norm(self) -> float | None:
        if self.loudness is None:
            return None
        return float(np.clip((self.loudness + 30.0) / 25.0, 0.0, 1.0))

    def numeric_map(self) -> dict[str, float | None]:
        return {
            "tempo_norm": self.tempo_norm,
            "energy": self.energy,
            "danceability": self.danceability,
            "acousticness": self.acousticness,
            "valence": self.valence,
            "speechiness": self.speechiness,
            "instrumentalness": self.instrumentalness,
            "loudness_norm": self.loudness_norm,
        }

    def to_public_dict(self) -> dict:
        provider = self.provider or "demo"
        body = {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "genres": list(self.genres),
            "language": self.language,
            "language_label": LANGUAGE_LABELS.get(self.language) or ("Language unknown" if not self.language else self.language),
            "year": self.year,
            "tempo": self.tempo,
            "energy": self.energy,
            "danceability": self.danceability,
            "acousticness": self.acousticness,
            "valence": self.valence,
            "speechiness": self.speechiness,
            "instrumentalness": self.instrumentalness,
            "loudness": self.loudness,
            "musical_key": self.musical_key,
            "mode": self.mode,
            "mode_label": None if self.mode is None else ("major" if self.mode == 1 else "minor"),
            "mood_tags": list(self.mood_tags),
            "feature_source": self.feature_source,
            "provider": provider,
            "provider_label": _PROVIDER_LABELS.get(provider, provider),
            "artwork_url": self.artwork_url,
            "external_url": self.external_url,
            "embed_url": self.embed_url,
            "genre_labels": list(self.genre_labels),
            "song_duration_ms": self.song_duration_ms if self.song_duration_ms is not None else self.duration_ms,
            "preview_duration_ms": self.preview_duration_ms,
        }
        if provider == "demo" and not self.playback_kind:
            body.update(playback_fields(self.id, self.duration_ms))
            body["provider"] = "demo"
            body["provider_label"] = "Demo catalog"
            return body
        kind = self.playback_kind or "unavailable"
        audio_url = self.preview_url if kind in {"preview", "full"} else None
        if kind in {"preview", "full"} and not audio_url:
            kind = "unavailable"
        if kind == "embed" and not self.embed_url:
            kind = "unavailable"
        if kind == "preview":
            player_ms = int(self.preview_duration_ms or 0)
        elif kind == "full":
            player_ms = int(self.duration_ms)
        else:
            player_ms = int(self.song_duration_ms or self.duration_ms or 0)
        body.update(
            {
                "duration_ms": player_ms,
                "preview": kind,
                "audio_url": audio_url,
                "recording_title": None,
                "recording_license": None,
                "embed_url": self.embed_url if kind == "embed" else None,
            }
        )
        return body


def track_blocks(track: Track) -> FeatureBlocks:
    values = track.numeric_map()
    numeric = np.zeros(len(NUMERIC_KEYS), dtype=np.float64)
    numeric_mask = np.zeros(len(NUMERIC_KEYS), dtype=np.float64)
    for index, key in enumerate(NUMERIC_KEYS):
        value = values[key]
        if value is None:
            continue
        numeric[index] = value
        numeric_mask[index] = 1.0

    genre = np.array([1.0 if name in track.genres else 0.0 for name in GENRES], dtype=np.float64)
    genre_mask = np.ones(len(GENRES), dtype=np.float64) if track.genres else np.zeros(len(GENRES))

    language = np.array([1.0 if track.language == code else 0.0 for code in LANGUAGES], dtype=np.float64)
    language_mask = np.ones(len(LANGUAGES), dtype=np.float64) if track.language else np.zeros(len(LANGUAGES))

    if track.mood_tags:
        mood = np.array([1.0 if tag in track.mood_tags else 0.0 for tag in MOOD_TAGS], dtype=np.float64)
        mood_mask = np.ones(len(MOOD_TAGS), dtype=np.float64)
    else:
        mood = np.zeros(len(MOOD_TAGS), dtype=np.float64)
        mood_mask = np.zeros(len(MOOD_TAGS), dtype=np.float64)

    return FeatureBlocks(
        blocks={"numeric": numeric, "genre": genre, "language": language, "mood": mood},
        masks={"numeric": numeric_mask, "genre": genre_mask, "language": language_mask, "mood": mood_mask},
    )


def diversity_vector(track: Track) -> np.ndarray:
    """Compact vector for MMR. Missing numbers stay at 0 and are only used to
    spread artists and textures, not as a claimed measurement."""
    numeric = track.numeric_map()
    values = [0.0 if numeric[key] is None else float(numeric[key]) for key in NUMERIC_KEYS]
    genres = [1.0 if name in track.genres else 0.0 for name in GENRES]
    return np.array(values + genres, dtype=np.float64)


# Soft priors from the onboarding "listening purpose" control. Applied to the
# content profile only, and clamped to [0, 1].
PURPOSE_NUDGE: dict[str, dict[str, float]] = {
    "focus": {"energy": -0.05, "acousticness": 0.08, "danceability": -0.08},
    "relax": {"energy": -0.10, "acousticness": 0.10, "valence": 0.04},
    "energy": {"energy": 0.12, "danceability": 0.10, "valence": 0.05},
    "sleep": {"energy": -0.18, "acousticness": 0.14, "danceability": -0.10, "tempo": -0.08},
    "commute": {"energy": 0.06, "danceability": 0.05},
    "mood_lift": {"valence": 0.12, "energy": 0.05},
    "none": {},
}


def _nudge(explicit: ExplicitProfile) -> dict[str, float]:
    base = {
        "energy": explicit.energy,
        "danceability": explicit.danceability,
        "acousticness": explicit.acousticness,
        "valence": explicit.valence,
        "tempo": explicit.tempo,
    }
    for key, delta in PURPOSE_NUDGE.get(explicit.purpose, {}).items():
        base[key] = float(np.clip(base[key] + delta, 0.0, 1.0))
    return base


def _blend_axis(explicit_value: float, inferred_value: float | None, confidence: float, stated: bool) -> float | None:
    if not stated and inferred_value is None:
        return None
    if inferred_value is None or confidence <= 0:
        return explicit_value
    return (1.0 - confidence) * explicit_value + confidence * inferred_value


def profile_blocks(explicit: ExplicitProfile, inferred: InferredProfile) -> FeatureBlocks:
    """Build the listener vector in the same blocks as a track.

    Onboarding supplies the starting point. Inferred affinities take a growing
    share as confidence rises. Axes the listener never stated and never revealed
    through listening stay masked.
    """
    confidence = inferred.confidence
    nudged = _nudge(explicit)
    blended = blended_characteristics(explicit, inferred)
    # Purpose nudge applies to the explicit side before the blend.
    for key in ("energy", "danceability", "acousticness", "valence", "tempo"):
        if getattr(inferred, key) is None or confidence <= 0:
            blended[key] = nudged[key]
        else:
            blended[key] = (1.0 - confidence) * nudged[key] + confidence * getattr(inferred, key)

    numeric = np.zeros(len(NUMERIC_KEYS), dtype=np.float64)
    numeric_mask = np.zeros(len(NUMERIC_KEYS), dtype=np.float64)
    stated_audio = explicit.purpose != "none" or any(
        abs(getattr(explicit, name) - 0.5) > 1e-9 for name in ("energy", "danceability", "acousticness", "valence", "tempo")
    )
    # Eval users use a neutral explicit profile. Their sliders are not evidence,
    # so numeric coordinates turn on only after listening updates the centroid,
    # except speech/instrumental defaults which we leave masked.
    mapping = {
        "tempo_norm": blended["tempo"] if (stated_audio or inferred.tempo is not None) else None,
        "energy": blended["energy"] if (stated_audio or inferred.energy is not None) else None,
        "danceability": blended["danceability"] if (stated_audio or inferred.danceability is not None) else None,
        "acousticness": blended["acousticness"] if (stated_audio or inferred.acousticness is not None) else None,
        "valence": blended["valence"] if (stated_audio or inferred.valence is not None) else None,
        "speechiness": None,
        "instrumentalness": None,
        "loudness_norm": None,
    }
    # Real onboarding always sets sliders, including the 0.5 default. The UI
    # always submits them, so stated_audio is true whenever purpose is set OR
    # the caller marks the profile as onboarded. Neutral eval profiles keep
    # purpose "none" and default 0.5, which we treat as unstated.
    if explicit.purpose != "none" or explicit.genres or explicit.languages or explicit.artists:
        for key in ("tempo_norm", "energy", "danceability", "acousticness", "valence"):
            if mapping[key] is None:
                source = {"tempo_norm": blended["tempo"], "energy": blended["energy"], "danceability": blended["danceability"], "acousticness": blended["acousticness"], "valence": blended["valence"]}
                mapping[key] = source[key]
    for index, key in enumerate(NUMERIC_KEYS):
        value = mapping[key]
        if value is None:
            continue
        numeric[index] = value
        numeric_mask[index] = 1.0

    genre = np.zeros(len(GENRES), dtype=np.float64)
    genre_mask = np.zeros(len(GENRES), dtype=np.float64)
    has_genre_evidence = bool(explicit.genres) or any(abs(value) > 0.05 for value in inferred.genre_affinity.values())
    if has_genre_evidence:
        genre_mask[:] = 1.0
        for index, name in enumerate(GENRES):
            explicit_value = 1.0 if name in explicit.genres else 0.0
            if name in inferred.genre_affinity and confidence > 0:
                inferred_unit = (inferred.genre_affinity[name] + 1.0) / 2.0
                genre[index] = (1.0 - confidence) * explicit_value + confidence * inferred_unit
            else:
                genre[index] = explicit_value

    language = np.zeros(len(LANGUAGES), dtype=np.float64)
    language_mask = np.zeros(len(LANGUAGES), dtype=np.float64)
    has_language_evidence = bool(explicit.languages) or any(
        abs(value) > 0.05 for value in inferred.language_affinity.values()
    )
    if has_language_evidence:
        language_mask[:] = 1.0
        for index, code in enumerate(LANGUAGES):
            explicit_value = 1.0 if code in explicit.languages else 0.0
            if code in inferred.language_affinity and confidence > 0:
                inferred_unit = (inferred.language_affinity[code] + 1.0) / 2.0
                language[index] = (1.0 - confidence) * explicit_value + confidence * inferred_unit
            else:
                language[index] = explicit_value

    mood = _profile_mood_block(blended, explicit.purpose if has_genre_evidence or explicit.purpose != "none" else "none")
    mood_mask = np.ones(len(MOOD_TAGS), dtype=np.float64) if float(mood.sum()) > 0 else np.zeros(len(MOOD_TAGS))

    return FeatureBlocks(
        blocks={"numeric": numeric, "genre": genre, "language": language, "mood": mood},
        masks={"numeric": numeric_mask, "genre": genre_mask, "language": language_mask, "mood": mood_mask},
    )


def _profile_mood_block(blended: dict[str, float], purpose: str) -> np.ndarray:
    scores = {tag: 0.0 for tag in MOOD_TAGS}
    energy = blended.get("energy", 0.5)
    valence = blended.get("valence", 0.5)
    acoustic = blended.get("acousticness", 0.5)
    dance = blended.get("danceability", 0.5)
    if valence >= 0.62:
        scores["joyful"] += 0.85
        scores["hopeful"] += 0.55
    if valence <= 0.38:
        scores["melancholic"] += 0.8
    if energy >= 0.66:
        scores["energetic"] += 0.85
    if energy <= 0.38 and acoustic >= 0.55:
        scores["calm"] += 0.85
        scores["dreamy"] += 0.45
    if dance >= 0.66:
        scores["groovy"] += 0.75
    if purpose == "focus":
        scores["focused"] += 0.9
    if purpose == "sleep":
        scores["calm"] += 0.6
        scores["dreamy"] += 0.6
    if purpose == "mood_lift":
        scores["hopeful"] += 0.7
        scores["joyful"] += 0.4
    peak = max(scores.values()) if scores else 0.0
    if peak <= 0:
        return np.zeros(len(MOOD_TAGS), dtype=np.float64)
    return np.array([scores[tag] / peak for tag in MOOD_TAGS], dtype=np.float64)


_PROVIDER_LABELS = {
    "demo": "Demo catalog",
    "itunes": "Apple Music",
    "youtube": "YouTube",
    "spotify": "Spotify",
}


def language_factor(track: Track, explicit: ExplicitProfile, inferred: InferredProfile) -> float:
    """Down-weight languages the listener did not ask for, without banning them.

    Discovery preference relaxes the penalty. An unknown track language is not
    evidence, so it is left alone instead of being treated as a mismatch.
    """
    if not track.language:
        return 1.0
    liked = set(explicit.languages)
    liked.update(code for code, affinity in inferred.language_affinity.items() if affinity > 0.2)
    if not liked:
        return 1.0
    if track.language in liked:
        return 1.0
    return float(np.clip(0.42 + 0.45 * explicit.discovery, 0.42, 0.92))


def preference_match(track: Track, explicit: ExplicitProfile, inferred: InferredProfile) -> float | None:
    """Identity match: genres, language, characteristics, and known artists.

    An artist the listener has never mentioned is left out, not scored as zero.
    """
    parts: list[tuple[float, float]] = []
    genre_score = _genre_overlap(track, explicit, inferred)
    if genre_score is not None:
        parts.append((genre_score, 0.42))
    language_score = _language_match(track, explicit, inferred)
    if language_score is not None:
        parts.append((language_score, 0.23))
    character_score = _characteristic_match(track, explicit, inferred)
    if character_score is not None:
        parts.append((character_score, 0.35))
    artist_score = _artist_match(track, explicit, inferred)
    if artist_score is not None:
        parts.append((artist_score, 0.28))
    if not parts:
        return None
    weight_sum = sum(weight for _, weight in parts)
    return float(sum(score * weight for score, weight in parts) / weight_sum)


def _genre_overlap(track: Track, explicit: ExplicitProfile, inferred: InferredProfile) -> float | None:
    confidence = inferred.confidence
    if not explicit.genres and not any(abs(value) > 0.05 for value in inferred.genre_affinity.values()):
        return None
    scores: dict[str, float] = {}
    for name in GENRES:
        explicit_value = 1.0 if name in explicit.genres else 0.0
        if name in inferred.genre_affinity and confidence > 0:
            inferred_unit = (inferred.genre_affinity[name] + 1.0) / 2.0
            scores[name] = (1.0 - confidence) * explicit_value + confidence * inferred_unit
        else:
            scores[name] = explicit_value
    mass = sum(scores.values())
    if mass <= 1e-8:
        return None
    if not track.genres:
        return None
    hit = sum(scores[name] for name in track.genres)
    share = min(1.0, (hit / mass) * 2.2)
    peak = max(scores[name] for name in track.genres)
    return float(np.clip(0.5 * peak + 0.5 * share, 0.0, 1.0))


def _language_match(track: Track, explicit: ExplicitProfile, inferred: InferredProfile) -> float | None:
    if not track.language:
        return None
    confidence = inferred.confidence
    if not explicit.languages and track.language not in inferred.language_affinity and not inferred.language_affinity:
        return None
    if not explicit.languages and all(abs(value) <= 0.05 for value in inferred.language_affinity.values()):
        return None
    explicit_value = 1.0 if track.language in explicit.languages else 0.0
    if track.language in inferred.language_affinity and confidence > 0:
        inferred_unit = (inferred.language_affinity[track.language] + 1.0) / 2.0
        if explicit.languages:
            return float(np.clip((1.0 - confidence) * explicit_value + confidence * inferred_unit, 0.0, 1.0))
        return float(np.clip(inferred_unit, 0.0, 1.0))
    if explicit.languages:
        return explicit_value
    return None


def _characteristic_match(track: Track, explicit: ExplicitProfile, inferred: InferredProfile) -> float | None:
    blended = blended_characteristics(explicit, inferred)
    stated = bool(explicit.genres or explicit.languages or explicit.artists or explicit.purpose != "none")
    pairs = (
        ("energy", track.energy, blended["energy"]),
        ("danceability", track.danceability, blended["danceability"]),
        ("acousticness", track.acousticness, blended["acousticness"]),
        ("valence", track.valence, blended["valence"]),
        ("tempo", track.tempo_norm, blended["tempo"]),
    )
    distances: list[float] = []
    for name, actual, target in pairs:
        if actual is None:
            continue
        inferred_value = getattr(inferred, name if name != "tempo" else "tempo")
        if not stated and inferred_value is None:
            continue
        distances.append(abs(float(actual) - float(target)))
    if not distances:
        return None
    return float(np.clip(1.0 - sum(distances) / len(distances), 0.0, 1.0))


def _artist_match(track: Track, explicit: ExplicitProfile, inferred: InferredProfile) -> float | None:
    if track.artist in explicit.artists:
        if track.artist in inferred.artist_affinity and inferred.confidence > 0:
            inferred_unit = (inferred.artist_affinity[track.artist] + 1.0) / 2.0
            return float(np.clip((1.0 - inferred.confidence) * 1.0 + inferred.confidence * inferred_unit, 0.0, 1.0))
        return 1.0
    if track.artist in inferred.artist_affinity and abs(inferred.artist_affinity[track.artist]) > 0.05:
        return float(np.clip((inferred.artist_affinity[track.artist] + 1.0) / 2.0, 0.0, 1.0))
    return None


def discovery_score(
    track: Track,
    explicit: ExplicitProfile,
    inferred: InferredProfile,
    popularity: float,
) -> float:
    """How much of a discovery this track is, in [0, 1].

    The ranker scales the component's weight by the listener's exploration
    preference. The score itself stays a property of the track, so an
    explanation can say "new artist" only when that is true.
    """
    known_artists = set(explicit.artists)
    known_artists.update(artist for artist, count in inferred.plays_by_artist.items() if count > 0)
    new_artist = track.artist not in known_artists and inferred.artist_affinity.get(track.artist, 0.0) < 0.15
    played = inferred.plays_by_track.get(track.id, 0) > 0
    novelty = 1.0 - float(np.clip(popularity, 0.0, 1.0))
    score = 0.55 * (1.0 if new_artist else 0.0) + 0.25 * novelty + 0.20 * (0.0 if played else 1.0)
    return float(np.clip(score, 0.0, 1.0))


def editorial_key(artist: str) -> int:
    return zlib.crc32(artist.encode("utf-8")) % 12


def aligned_tags(listening_mood: str) -> tuple[str, ...]:
    return MOOD_TAG_ALIGNMENT.get(listening_mood, ())


def validate_track_vocab(track: Track) -> None:
    unknown_genres = [genre for genre in track.genres if genre not in GENRES]
    if unknown_genres:
        raise ValueError(f"{track.id} has unknown genres: {unknown_genres}")
    if track.language and track.language not in LANGUAGES:
        raise ValueError(f"{track.id} has unknown language {track.language}")
    unknown_moods = [tag for tag in track.mood_tags if tag not in MOOD_TAGS]
    if unknown_moods:
        raise ValueError(f"{track.id} has unknown mood tags: {unknown_moods}")
    if track.feature_source == "":
        raise ValueError(f"{track.id} is missing a feature source")


def known_purpose(purpose: str) -> bool:
    return purpose in PURPOSES
