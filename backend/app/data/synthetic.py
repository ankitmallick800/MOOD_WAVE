"""Synthetic listeners for collaborative filtering and offline evaluation.

Interactions are sampled from hidden taste vectors so the ranking code has a
signal to recover. The taste vectors are discarded and are not written to disk.
Nothing in this module is real listening.
"""

from __future__ import annotations

import numpy as np

from app.data.catalog import Track

POSITIVE_EVENTS = ("like", "complete", "replay", "playlist_add")
ORIGIN = "synthetic"


def generate_interactions(tracks: list[Track], seed: int = 42, n_users: int = 42) -> list[dict]:
    rng = np.random.default_rng(seed)
    ordered = sorted(tracks, key=lambda track: track.id)
    genres = sorted({genre for track in ordered for genre in track.genres})
    languages = sorted({track.language for track in ordered})
    hit_indexes = [
        index
        for index, track in enumerate(ordered)
        if "pop" in track.genres or "k-pop" in track.genres or "latin" in track.genres
    ][:8]

    events: list[dict] = []
    base_ts = 1_700_000_000
    for user_number in range(n_users):
        user_id = f"synth-{user_number + 1:03d}"
        n_genres = int(rng.integers(1, 4))
        genre_draw = rng.choice(len(genres), size=n_genres, replace=False)
        taste_genres = {genres[int(index)] for index in genre_draw}
        n_languages = 1 if rng.random() < 0.72 else 2
        language_draw = rng.choice(len(languages), size=n_languages, replace=False)
        taste_languages = {languages[int(index)] for index in language_draw}
        energy = float(rng.uniform(0.22, 0.82))
        valence = float(rng.uniform(0.2, 0.84))

        scores = np.array([_latent_score(track, taste_genres, taste_languages, energy, valence) for track in ordered])
        probabilities = np.clip(scores, 0.02, None) ** 2
        probabilities = probabilities / probabilities.sum()

        chosen: list[int] = []
        available = probabilities.copy()
        for _ in range(22):
            total = float(available.sum())
            if total <= 0:
                break
            pick = int(rng.choice(len(ordered), p=available / total))
            chosen.append(pick)
            available[pick] = 0.0

        # A slice of users also play a few widely shared tracks, so a popularity
        # baseline has something to rank that is not identical to personal taste.
        if user_number % 2 == 0 and hit_indexes:
            for slot in range(2):
                hit = int(hit_indexes[int(rng.integers(0, len(hit_indexes)))])
                if hit not in chosen:
                    chosen[-(slot + 1)] = hit

        for step, track_index in enumerate(chosen):
            track = ordered[track_index]
            score = float(scores[track_index])
            event_type, listen_ratio = _event_for_score(score, rng)
            events.append(
                {
                    "user_id": user_id,
                    "track_id": track.id,
                    "event_type": event_type,
                    "ts": base_ts + step * 200_000 + user_number * 13,
                    "listen_ratio": listen_ratio,
                    "origin": ORIGIN,
                }
            )
    events.sort(key=lambda event: (event["ts"], event["user_id"], event["track_id"]))
    return events


def _latent_score(
    track: Track,
    taste_genres: set[str],
    taste_languages: set[str],
    energy: float,
    valence: float,
) -> float:
    genre_hit = 1.0 if any(genre in taste_genres for genre in track.genres) else 0.0
    language_hit = 1.0 if track.language in taste_languages else 0.12
    energy_gap = 0.0 if track.energy is None else abs(track.energy - energy)
    valence_gap = 0.0 if track.valence is None else abs(track.valence - valence)
    audio = 1.0 - (energy_gap + valence_gap) / 2.0
    return float(0.46 * genre_hit + 0.24 * language_hit + 0.30 * audio)


def _event_for_score(score: float, rng: np.random.Generator) -> tuple[str, float]:
    roll = float(rng.random())
    if score >= 0.72:
        if roll < 0.46:
            return "like", 0.96
        if roll < 0.72:
            return "complete", 1.0
        if roll < 0.84:
            return "replay", 0.92
        if roll < 0.92:
            return "playlist_add", 0.88
        return "play", 0.7
    if score >= 0.48:
        if roll < 0.28:
            return "complete", 1.0
        if roll < 0.40:
            return "like", 0.9
        if roll < 0.78:
            return "play", 0.58
        return "skip", 0.18
    if roll < 0.62:
        return "skip", 0.1
    if roll < 0.78:
        return "play", 0.32
    return "dislike", 0.16
