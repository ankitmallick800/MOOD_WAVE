"""Offline ranking metrics.

Precision, recall, and hit rate use binary relevance. NDCG uses graded
relevance. Coverage, diversity, and novelty describe the lists themselves.
"""

from __future__ import annotations

import math
from itertools import combinations

import numpy as np

from app.ml.features import plain_cosine


def precision_at_k(recommended: list[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    picked = recommended[:k]
    if not picked:
        return 0.0
    hits = sum(1 for item in picked if item in relevant)
    return hits / len(picked)


def recall_at_k(recommended: list[str], relevant: set[str], k: int) -> float:
    if not relevant or k <= 0:
        return 0.0
    picked = recommended[:k]
    hits = sum(1 for item in picked if item in relevant)
    return hits / len(relevant)


def hit_rate_at_k(recommended: list[str], relevant: set[str], k: int) -> float:
    if not relevant or k <= 0:
        return 0.0
    return 1.0 if any(item in relevant for item in recommended[:k]) else 0.0


def _dcg(grades: list[float]) -> float:
    total = 0.0
    for index, grade in enumerate(grades):
        total += grade / math.log2(index + 2)
    return total


def ndcg_at_k(recommended: list[str], grades: dict[str, float], k: int) -> float | None:
    if k <= 0 or not grades:
        return None
    ideal = sorted(grades.values(), reverse=True)[:k]
    idcg = _dcg(ideal)
    if idcg <= 1e-12:
        return None
    picked = [_grade(grades, item) for item in recommended[:k]]
    return _dcg(picked) / idcg


def _grade(grades: dict[str, float], item: str) -> float:
    return float(grades.get(item, 0.0))


def catalog_coverage(lists: list[list[str]], catalog_size: int) -> float | None:
    if catalog_size <= 0 or not lists:
        return None
    unique = {item for items in lists for item in items}
    return len(unique) / catalog_size


def intra_list_diversity(recommended: list[str], vectors: dict[str, np.ndarray]) -> float | None:
    present = [item for item in recommended if item in vectors]
    if len(present) < 2:
        return None
    distances = []
    for left, right in combinations(present, 2):
        distances.append(1.0 - plain_cosine(vectors[left], vectors[right]))
    return float(np.mean(distances))


def novelty(recommended: list[str], popularity: dict[str, float]) -> float | None:
    """Mean self-information. Higher means the list is less concentrated on hits."""
    if not recommended:
        return None
    # popularity here is a non-negative mass proxy, not a probability.
    masses = {key: max(float(value), 0.0) for key, value in popularity.items()}
    total = sum(masses.values())
    if total <= 0:
        return None
    scores = []
    for item in recommended:
        probability = max(masses.get(item, 0.0) / total, 1e-6)
        scores.append(-math.log2(probability))
    return float(np.mean(scores))


def macro_mean(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return float(np.mean(clean))


def macro_std(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if len(clean) < 2:
        return None
    return float(np.std(clean))


METRIC_NOTES: dict[str, str] = {
    "precision_at_k": "Share of the top K that appears in the held-out relevant set. A short K punishes broad but relevant lists.",
    "recall_at_k": "Share of held-out relevant tracks that landed in the top K. Low recall can mean the list is too short, not that the model is random.",
    "ndcg_at_k": "Graded ranking quality against the ideal order. Likes count more than completes. It rewards putting stronger items higher.",
    "hit_rate_at_k": "Fraction of listeners for whom at least one held-out relevant track appears in the top K. It ignores how many relevant tracks were found.",
    "coverage": "Distinct recommended tracks divided by catalog size, across the evaluated listeners. High coverage means the model is not collapsing onto a handful of tracks.",
    "diversity": "Average pairwise distance inside each list, using catalog feature vectors. It is a property of the list, not of listener satisfaction.",
    "novelty": "Mean self-information of the recommended tracks under the training popularity distribution. Higher means less concentrated on frequent tracks.",
}
