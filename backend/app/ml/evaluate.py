"""Temporal-holdout evaluation.

Training interactions are those before the 70th percentile timestamp. Test
relevance is likes, completes, replays, and playlist adds after the cutoff,
on tracks the listener did not already touch in training. Profiles are rebuilt
from training events only. Latent generator preferences are not passed in.

The demo matrix is synthetic. Metrics are pipeline diagnostics. They are not
an estimate of how the models would behave for real listeners.
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from app.data.catalog import Track, diversity_vector
from app.ml.collaborative import ItemItemModel, SVDModel, build_matrix, popularity_scores
from app.ml.hybrid import rank_tracks
from app.ml.metrics import (
    METRIC_NOTES,
    catalog_coverage,
    hit_rate_at_k,
    intra_list_diversity,
    macro_mean,
    macro_std,
    ndcg_at_k,
    novelty,
    precision_at_k,
    recall_at_k,
)
from app.ml.profile import ExplicitProfile, replay_events
from app.ml.vocabulary import DEFAULT_GROUP_WEIGHTS, DEFAULT_WEIGHTS, MIN_COLLAB_TRACKS

POSITIVE = {"like", "complete", "replay", "playlist_add"}
GRADES = {"like": 3.0, "replay": 2.5, "playlist_add": 2.0, "complete": 2.0}
STRATEGIES = ("popularity", "content", "collaborative", "hybrid")
MIN_EVAL_USERS = 8


def evaluate_models(
    tracks: list[Track],
    events: list[dict],
    k: int = 10,
    weights: dict[str, float] | None = None,
    group_weights: dict[str, float] | None = None,
    strategies: tuple[str, ...] = STRATEGIES,
    diversify: bool = False,
    origin: str = "synthetic_demo",
) -> dict:
    if not events:
        return _empty("No interactions are available to evaluate.")

    frame = pd.DataFrame(events)
    required = {"user_id", "track_id", "event_type", "ts"}
    if not required.issubset(frame.columns):
        return _empty("Interaction table is missing required columns.")
    frame["ts"] = pd.to_numeric(frame["ts"], errors="coerce")
    frame = frame.dropna(subset=["ts"])
    if frame.empty:
        return _empty("Interaction timestamps could not be parsed.")

    cutoff = float(frame["ts"].quantile(0.70))
    train_frame = frame[frame["ts"] < cutoff]
    test_frame = frame[frame["ts"] >= cutoff]
    train_events = train_frame.to_dict(orient="records")
    test_events = test_frame.to_dict(orient="records")

    item_ids = [track.id for track in sorted(tracks, key=lambda track: track.id)]
    tracks_by_id = {track.id: track for track in tracks}
    user_ids = sorted(frame["user_id"].unique())
    matrix = build_matrix(user_ids, item_ids, train_events)
    item_item = ItemItemModel()
    item_item.fit(item_ids, matrix)
    svd = SVDModel()
    svd.fit(user_ids, item_ids, matrix)
    pop = popularity_scores(item_ids, matrix)
    pop_mass = {item_id: float(max(matrix[:, index].clip(min=0).sum(), 0.0)) for index, item_id in enumerate(item_ids)}

    train_by_user: dict[str, list[dict]] = defaultdict(list)
    test_by_user: dict[str, list[dict]] = defaultdict(list)
    for event in train_events:
        train_by_user[event["user_id"]].append(event)
    for event in test_events:
        test_by_user[event["user_id"]].append(event)

    vectors = {track.id: diversity_vector(track) for track in tracks}
    per_strategy: dict[str, dict[str, list]] = {
        name: {metric: [] for metric in ("precision_at_k", "recall_at_k", "ndcg_at_k", "hit_rate_at_k", "diversity", "novelty")}
        for name in strategies
    }
    lists: dict[str, list[list[str]]] = {name: [] for name in strategies}
    scored_users = {name: 0 for name in strategies}

    for user_id in user_ids:
        train_user = train_by_user.get(user_id, [])
        positive_train = {event["track_id"] for event in train_user if event["event_type"] in POSITIVE or _listen_ratio(event) >= 0.5}
        seen_train = {event["track_id"] for event in train_user}
        if len(positive_train) < 4:
            continue
        grades: dict[str, float] = {}
        for event in test_by_user.get(user_id, []):
            if event["event_type"] not in POSITIVE:
                continue
            if event["track_id"] in seen_train:
                continue
            grades[event["track_id"]] = max(grades.get(event["track_id"], 0.0), GRADES[event["event_type"]])
        if len(grades) < 2:
            continue
        relevant = set(grades)
        inferred = replay_events(train_user, tracks_by_id)
        explicit = ExplicitProfile.neutral()
        from app.ml.profile import interaction_weights

        weights_user = interaction_weights(train_user)
        if "collaborative_svd" in strategies:
            collab_svd = svd.score_known_user(user_id)
        else:
            collab_svd = None
        collab = item_item.score(weights_user, MIN_COLLAB_TRACKS)

        for strategy in strategies:
            model_collab = collab_svd if strategy == "collaborative_svd" else collab
            if strategy in {"collaborative", "collaborative_svd"} and model_collab is None:
                continue
            ranked, _meta = rank_tracks(
                tracks,
                explicit,
                inferred,
                model_collab,
                pop,
                neighbor_for=None,
                weights=weights,
                group_weights=group_weights,
                strategy=strategy,
                diversify=diversify,
                limit=k,
                exclude_ids=seen_train,
            )
            recommended = [item.track.id for item in ranked]
            per_strategy[strategy]["precision_at_k"].append(precision_at_k(recommended, relevant, k))
            per_strategy[strategy]["recall_at_k"].append(recall_at_k(recommended, relevant, k))
            per_strategy[strategy]["ndcg_at_k"].append(ndcg_at_k(recommended, grades, k))
            per_strategy[strategy]["hit_rate_at_k"].append(hit_rate_at_k(recommended, relevant, k))
            per_strategy[strategy]["diversity"].append(intra_list_diversity(recommended, vectors))
            per_strategy[strategy]["novelty"].append(novelty(recommended, pop_mass))
            lists[strategy].append(recommended)
            scored_users[strategy] += 1

    usable = max(scored_users.values()) if scored_users else 0
    warning = _warning(origin, usable, len(user_ids), len(tracks), len(events))
    suppressed = usable < MIN_EVAL_USERS
    models = []
    for strategy in strategies:
        entry = {
            "strategy": strategy,
            "label": _label(strategy),
            "n_users": scored_users[strategy],
            "metrics": None
            if suppressed
            else {
                metric: {
                    "mean": macro_mean(values),
                    "std": macro_std(values),
                }
                for metric, values in per_strategy[strategy].items()
            },
            "coverage": None if suppressed else catalog_coverage(lists[strategy], len(tracks)),
        }
        models.append(entry)

    return {
        "suppressed": suppressed,
        "meaningful_as_real_world": False if origin.startswith("synthetic") else not suppressed,
        "warning": warning,
        "protocol": {
            "name": "temporal_holdout",
            "cutoff_quantile": 0.7,
            "cutoff_ts": cutoff,
            "candidate_policy": "exclude_items_seen_in_train",
            "relevance": "like, complete, replay, and playlist_add in the test window",
            "grades": GRADES,
            "profile": "Inferred from training events only. Generator taste vectors are not inputs.",
            "collaborative_fit": "Item similarities are fit on all training users, including the evaluated user. Test interactions are excluded.",
            "diversify": diversify,
            "k": k,
            "note": "Player-facing lists use diversity reranking. These metrics use score order unless diversify is set.",
        },
        "dataset": {
            "origin": origin,
            "label": "Generated interactions, not real listeners." if origin.startswith("synthetic") else "External interaction file.",
            "n_users": int(frame["user_id"].nunique()),
            "n_tracks": len(tracks),
            "n_interactions": int(len(frame)),
            "n_train_interactions": int(len(train_frame)),
            "n_test_interactions": int(len(test_frame)),
            "n_eval_users": usable,
        },
        "models": models,
        "metric_notes": METRIC_NOTES,
        "weights": weights or DEFAULT_WEIGHTS,
        "group_weights": group_weights or DEFAULT_GROUP_WEIGHTS,
    }


def _listen_ratio(event: dict) -> float:
    try:
        return float(event.get("listen_ratio") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _label(strategy: str) -> str:
    return {
        "popularity": "Popularity baseline",
        "content": "Content-based filtering",
        "collaborative": "Item-item collaborative filtering",
        "collaborative_svd": "TruncatedSVD collaborative filtering",
        "hybrid": "Hybrid ranker",
    }.get(strategy, strategy)


def _warning(origin: str, usable: int, n_users: int, n_tracks: int, n_events: int) -> str:
    if usable < MIN_EVAL_USERS:
        return (
            f"Only {usable} listeners meet the holdout rules (at least 4 positive training tracks "
            f"and 2 unseen relevant test tracks). Metrics are withheld. Dataset size is "
            f"{n_users} users, {n_tracks} tracks, {n_events} interactions. Figures are not filled in."
        )
    if origin.startswith("synthetic"):
        return (
            "These figures were computed on a synthetic interaction set generated from hidden taste "
            "vectors. They check that training, holdout, and metrics run. They are not evidence about "
            "real listeners, and the collaborative model has not learned patterns from real behavior. "
            "A higher hybrid score is expected when the generator itself is content-aligned."
        )
    return (
        "Metrics use a temporal holdout on the supplied interaction file. They describe this file "
        "under the protocol above, not a universal claim about the ranker."
    )


def _empty(reason: str) -> dict:
    return {
        "suppressed": True,
        "meaningful_as_real_world": False,
        "warning": reason,
        "protocol": {"name": "temporal_holdout"},
        "dataset": {"origin": "unknown", "n_users": 0, "n_tracks": 0, "n_interactions": 0, "n_eval_users": 0},
        "models": [],
        "metric_notes": METRIC_NOTES,
    }
