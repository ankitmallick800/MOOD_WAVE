"""Feature blocks and masked, weighted cosine similarity.

Missing coordinates are masked out. They are not filled with zeros, because a
zero would look like evidence ("this track has no energy") rather than absence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.ml.vocabulary import FEATURE_GROUPS


@dataclass
class FeatureBlocks:
    blocks: dict[str, np.ndarray]
    masks: dict[str, np.ndarray]

    def group(self, name: str) -> tuple[np.ndarray, np.ndarray]:
        return self.blocks[name], self.masks[name]


def masked_weighted_cosine(
    left: FeatureBlocks,
    right: FeatureBlocks,
    group_weights: dict[str, float],
) -> float | None:
    """Cosine on the overlapping observed coordinates, with group weights.

    Each block is scaled by sqrt(weight) before the dot product, which is the
    usual way to turn feature weights into a weighted cosine. Returns None when
    the two vectors share no observed coordinates.
    """
    dot = 0.0
    left_sq = 0.0
    right_sq = 0.0
    used = 0
    for name in FEATURE_GROUPS:
        weight = float(group_weights.get(name, 1.0))
        if weight <= 0:
            continue
        lv, lm = left.group(name)
        rv, rm = right.group(name)
        mask = lm * rm
        if float(mask.sum()) <= 0:
            continue
        scale = math.sqrt(weight)
        a = lv * mask * scale
        b = rv * mask * scale
        dot += float(np.dot(a, b))
        left_sq += float(np.dot(a, a))
        right_sq += float(np.dot(b, b))
        used += 1
    if used == 0 or left_sq <= 1e-12 or right_sq <= 1e-12:
        return None
    value = dot / (math.sqrt(left_sq) * math.sqrt(right_sq))
    if value < 0:
        # Non-negative features should not go below zero. A negative result is
        # dissimilarity, which is evidence, so it becomes a low score rather
        # than "missing".
        return 0.0
    return float(min(1.0, value))


def plain_cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return float(np.clip(np.dot(a, b) / (na * nb), -1.0, 1.0))


def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)
