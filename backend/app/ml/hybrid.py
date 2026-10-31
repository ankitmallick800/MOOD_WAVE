"""Hybrid ranking: calibrated components, renormalized weights, diversity.

When a component is missing, its weight is dropped and the remaining weights
are scaled to sum to 1. A missing collaborative score is not treated as zero
evidence against the track.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.data.catalog import (
    Track,
    discovery_score,
    diversity_vector,
    language_factor,
    preference_match,
    profile_blocks,
    track_blocks,
)
from app.ml.explain import explain_recommendation
from app.ml.features import masked_weighted_cosine, plain_cosine
from app.ml.mood import mood_compatibility, resolve_target
from app.ml.profile import ExplicitProfile, InferredProfile
from app.ml.vocabulary import (
    ARTIST_CAP_DEFAULT,
    DEFAULT_GROUP_WEIGHTS,
    DEFAULT_WEIGHTS,
    DIVERSITY_LAMBDA_DEFAULT,
)


@dataclass
class ScoredTrack:
    track: Track
    score: float
    components: dict[str, float | None]
    weights_used: dict[str, float]
    explanations: list[str]
    neighbor: dict | None = None
    language_factor: float = 1.0
    vector: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(1))

    def to_dict(self) -> dict:
        return {
            "track": self.track.to_public_dict(),
            "score": round(self.score, 6),
            "components": {key: None if value is None else round(value, 6) for key, value in self.components.items()},
            "weights_used": {key: round(value, 6) for key, value in self.weights_used.items()},
            "explanations": self.explanations,
            "neighbor": self.neighbor,
            "language_factor": round(self.language_factor, 6),
        }


def _hold_discovery(
    score: float,
    visible: dict[str, float | None],
    effective_weights: dict[str, float],
    allowed: set[str],
) -> float:
    """Keep a new-artist bonus from replacing a missing genre match.

    combine() drops unknown components and rescales what remains. On a metadata
    catalog that turns every unmapped song by a new artist into a perfect score,
    ahead of a song that actually shares a genre. Discovery keeps only the share
    of the weight it was given.
    """
    if any(visible.get(name) is not None for name in ("content", "collaborative", "preference", "mood")):
        return score
    discovery = visible.get("discovery")
    if discovery is None:
        return score
    present = sum(float(effective_weights.get(name, 0.0)) for name in allowed)
    if present <= 0:
        return score
    return float(discovery) * float(effective_weights.get("discovery", 0.0)) / present


def combine(components: dict[str, float | None], weights: dict[str, float]) -> tuple[float, dict[str, float]]:
    active = {
        name: float(weights.get(name, 0.0))
        for name, value in components.items()
        if value is not None and float(weights.get(name, 0.0)) > 0
    }
    total = sum(active.values())
    if total <= 0:
        return 0.0, {}
    used = {name: weight / total for name, weight in active.items()}
    score = sum(used[name] * float(components[name]) for name in used)
    return float(score), used


def rank_tracks(
    tracks: list[Track],
    explicit: ExplicitProfile,
    inferred: InferredProfile,
    collab_scores: dict[str, float] | None,
    pop_scores: dict[str, float],
    neighbor_for,
    weights: dict[str, float] | None = None,
    group_weights: dict[str, float] | None = None,
    mood: str | None = None,
    mood_mode: str | None = None,
    strategy: str = "hybrid",
    diversify: bool = True,
    limit: int = 20,
    artist_cap: int = ARTIST_CAP_DEFAULT,
    diversity_lambda: float = DIVERSITY_LAMBDA_DEFAULT,
    reactions: dict[str, str] | None = None,
    exclude_ids: set[str] | None = None,
    catalog_kind: str = "demo",
) -> tuple[list[ScoredTrack], dict]:
    """Return ranked tracks and a small meta dict. `neighbor_for(track_id)` may be None."""
    weights = dict(DEFAULT_WEIGHTS if weights is None else weights)
    group_weights = dict(DEFAULT_GROUP_WEIGHTS if group_weights is None else group_weights)
    reactions = reactions or {}
    exclude_ids = exclude_ids or set()
    listener_blocks = profile_blocks(explicit, inferred)
    track_vectors = {track.id: track_blocks(track) for track in tracks}

    source_mood = None
    target_mood = None
    if mood:
        source_mood, target_mood = resolve_target(mood, mood_mode or "match")

    # Exploration preference scales the discovery weight. At 0 the bonus almost
    # drops out; at 1 it keeps the configured weight. The score stays "how new".
    effective_weights = dict(weights)
    effective_weights["discovery"] = weights.get("discovery", 0.0) * (0.15 + 0.85 * explicit.discovery)

    if strategy == "popularity":
        allowed = {"popularity"}
    elif strategy == "content":
        allowed = {"content"}
    elif strategy in {"collaborative", "collaborative_svd"}:
        allowed = {"collaborative"}
    else:
        allowed = {"content", "collaborative", "preference", "mood", "discovery"}

    scored: list[ScoredTrack] = []
    for track in tracks:
        if track.id in exclude_ids:
            continue
        components = _components(
            track,
            listener_blocks,
            track_vectors[track.id],
            explicit,
            inferred,
            collab_scores,
            pop_scores,
            group_weights,
            target_mood,
            strategy,
        )
        visible = {name: components.get(name) for name in ("content", "collaborative", "preference", "mood", "discovery")}
        if strategy == "popularity":
            score = float(pop_scores.get(track.id, 0.0))
            used = {"popularity": 1.0}
        else:
            requested = {name: effective_weights.get(name, 0.0) for name in allowed}
            score, used = combine({name: visible.get(name) for name in allowed}, requested)
            if strategy in {"collaborative", "collaborative_svd"} and visible.get("collaborative") is None:
                continue
            if catalog_kind == "metadata" and strategy == "hybrid":
                score = _hold_discovery(score, visible, effective_weights, allowed)
        lang = language_factor(track, explicit, inferred) if strategy in {"hybrid", "content"} else 1.0
        score *= lang
        if reactions.get(track.id) == "dislike":
            score *= 0.2
        neighbor = None
        if neighbor_for is not None and strategy in {"hybrid", "collaborative"}:
            neighbor = neighbor_for(track.id)
        explanations = explain_recommendation(
            track,
            visible,
            used,
            explicit,
            inferred,
            mood,
            mood_mode,
            source_mood,
            target_mood,
            neighbor,
            strategy if strategy != "hybrid" else "hybrid",
            audience="synthetic" if catalog_kind == "demo" else "catalog",
        )
        scored.append(
            ScoredTrack(
                track=track,
                score=float(score),
                components=visible,
                weights_used=used,
                explanations=explanations,
                neighbor=neighbor,
                language_factor=lang,
                vector=diversity_vector(track),
            )
        )

    scored.sort(key=lambda item: item.score, reverse=True)
    if diversify and strategy != "popularity":
        chosen = _diversify(scored, diversity_lambda, artist_cap, limit)
    else:
        chosen = scored[:limit]

    cold_start = collab_scores is None
    if strategy == "hybrid" and cold_start:
        ranking_mode = "cold_start_content"
    elif strategy == "hybrid":
        ranking_mode = "hybrid"
    else:
        ranking_mode = strategy

    meta = {
        "strategy": strategy,
        "ranking_mode": ranking_mode,
        "mood": mood,
        "mood_mode": mood_mode,
        "source_mood": source_mood,
        "target_mood": target_mood,
        "weights_requested": weights,
        "weights_effective": effective_weights,
        "group_weights": group_weights,
        "diversified": bool(diversify and strategy != "popularity"),
        "cold_start": cold_start and strategy == "hybrid",
        "notes": _notes(strategy, cold_start, mood, target_mood, catalog_kind),
    }
    return chosen, meta


def _components(
    track: Track,
    listener_blocks,
    blocks,
    explicit: ExplicitProfile,
    inferred: InferredProfile,
    collab_scores: dict[str, float] | None,
    pop_scores: dict[str, float],
    group_weights: dict[str, float],
    target_mood: str | None,
    strategy: str,
) -> dict[str, float | None]:
    if strategy == "popularity":
        return {"content": None, "collaborative": None, "preference": None, "mood": None, "discovery": None}
    content = masked_weighted_cosine(listener_blocks, blocks, group_weights)
    collab = None if not collab_scores else collab_scores.get(track.id)
    preference = preference_match(track, explicit, inferred)
    if target_mood is None or strategy not in {"hybrid"}:
        mood_score = None
    else:
        mood_score = mood_compatibility(track.numeric_map(), track.mood_tags, target_mood)
    discovery = discovery_score(track, explicit, inferred, pop_scores.get(track.id, 0.0))
    if strategy == "content":
        return {"content": content, "collaborative": None, "preference": None, "mood": None, "discovery": None}
    if strategy in {"collaborative", "collaborative_svd"}:
        return {"content": None, "collaborative": collab, "preference": None, "mood": None, "discovery": None}
    return {
        "content": content,
        "collaborative": collab,
        "preference": preference,
        "mood": mood_score,
        "discovery": discovery,
    }


def _diversify(scored: list[ScoredTrack], lam: float, artist_cap: int, limit: int) -> list[ScoredTrack]:
    pool = list(scored)
    selected: list[ScoredTrack] = []
    counts: dict[str, int] = {}
    cap = max(1, artist_cap)
    while pool and len(selected) < limit:
        best_index = None
        best_value = -1e9
        for index, candidate in enumerate(pool):
            if counts.get(candidate.track.artist, 0) >= cap:
                continue
            if not selected:
                value = candidate.score
            else:
                max_sim = max(plain_cosine(candidate.vector, chosen.vector) for chosen in selected)
                value = lam * candidate.score - (1.0 - lam) * max(0.0, max_sim)
            if value > best_value:
                best_value = value
                best_index = index
        if best_index is None:
            cap += 1
            if cap > 12:
                break
            continue
        chosen = pool.pop(best_index)
        selected.append(chosen)
        counts[chosen.track.artist] = counts.get(chosen.track.artist, 0) + 1
    return selected


def _notes(
    strategy: str,
    cold_start: bool,
    mood: str | None,
    target_mood: str | None,
    catalog_kind: str = "demo",
) -> list[str]:
    if catalog_kind == "metadata":
        notes = [
            
        ]
    elif catalog_kind == "demo":
        notes = [
            "Demo catalog audio features are editorial metadata, not measurements extracted from recordings.",
        ]
        if strategy in {"hybrid", "collaborative", "collaborative_svd", "popularity"}:
            notes.append("Collaborative and popularity scores use the labeled synthetic listener set, not real users.")
    else:
        notes = ["Ranking uses the features present on the loaded catalog."]
    if strategy == "hybrid" and cold_start:
        notes.append(
            "Fewer than 3 positively weighted tracks, so collaborative filtering is withheld and its weight is redistributed."
        )
    if mood and target_mood:
        notes.append("The session mood is a temporary listening target. It is not written into the saved taste profile.")
        if catalog_kind == "metadata":
            notes.append("Mood match is withheld when a song has no mood tags and no audio features.")
    return notes
