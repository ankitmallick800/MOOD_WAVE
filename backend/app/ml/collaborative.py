"""Item-item cosine collaborative filtering and a TruncatedSVD alternative.

Both models consume an implicit user-item matrix. Scores are calibrated with a
logistic transform fit on training users, so they sit on a 0-1 scale before
they are mixed with content scores. A listener with fewer than the minimum
number of positive tracks gets no collaborative score. Missing is not zero.
"""

from __future__ import annotations

import numpy as np
from sklearn.decomposition import TruncatedSVD

from app.ml.features import sigmoid


class ItemItemModel:
    def __init__(self) -> None:
        self.item_ids: list[str] = []
        self.index: dict[str, int] = {}
        self.similarity: np.ndarray | None = None
        self.mean = 0.0
        self.std = 1.0
        self.fitted = False

    def fit(self, item_ids: list[str], matrix: np.ndarray) -> None:
        """Fit item similarities. `matrix` is users × items and may be negative."""
        self.item_ids = list(item_ids)
        self.index = {item_id: index for index, item_id in enumerate(item_ids)}
        items_by_users = matrix.T.astype(np.float64)
        norms = np.linalg.norm(items_by_users, axis=1)
        safe = norms.copy()
        safe[safe < 1e-12] = 1.0
        normalized = items_by_users / safe[:, None]
        normalized[norms < 1e-12] = 0.0
        similarity = normalized @ normalized.T
        np.fill_diagonal(similarity, 0.0)
        self.similarity = similarity
        samples: list[np.ndarray] = []
        for row in matrix:
            if int(np.sum(row > 0)) < 3:
                continue
            raw = self._raw(row)
            samples.append(raw[np.isfinite(raw)])
        if samples:
            stacked = np.concatenate(samples)
            self.mean = float(np.mean(stacked))
            self.std = float(np.std(stacked) + 1e-6)
        self.fitted = True

    def _raw(self, weights: np.ndarray) -> np.ndarray:
        assert self.similarity is not None
        positive = np.clip(weights, 0.0, None)
        negative = np.clip(-weights, 0.0, None)
        positive_mass = float(positive.sum())
        if positive_mass <= 1e-9:
            return np.full(len(self.item_ids), np.nan)
        scores = (self.similarity @ positive) / positive_mass
        negative_mass = float(negative.sum())
        if negative_mass > 1e-9:
            scores = scores - 0.35 * ((self.similarity @ negative) / negative_mass)
        return scores

    def score(self, weights_by_item: dict[str, float], min_positive: int) -> dict[str, float] | None:
        if not self.fitted or self.similarity is None:
            return None
        weights = np.zeros(len(self.item_ids), dtype=np.float64)
        positive_tracks = 0
        for track_id, value in weights_by_item.items():
            index = self.index.get(track_id)
            if index is None:
                continue
            weights[index] = value
            if value > 0:
                positive_tracks += 1
        if positive_tracks < min_positive:
            return None
        raw = self._raw(weights)
        calibrated: dict[str, float] = {}
        scale = self.std if self.std > 1e-6 else 1.0
        for index, track_id in enumerate(self.item_ids):
            if not np.isfinite(raw[index]):
                continue
            calibrated[track_id] = sigmoid((float(raw[index]) - self.mean) / scale)
        return calibrated

    def best_neighbor(self, track_id: str, weights_by_item: dict[str, float]) -> tuple[str, float] | None:
        if self.similarity is None or track_id not in self.index:
            return None
        row = self.index[track_id]
        best_id = None
        best_similarity = 0.05
        for other_id, weight in weights_by_item.items():
            if weight <= 0 or other_id == track_id or other_id not in self.index:
                continue
            value = float(self.similarity[row, self.index[other_id]])
            if value > best_similarity:
                best_similarity = value
                best_id = other_id
        if best_id is None:
            return None
        return best_id, best_similarity


class SVDModel:
    """TruncatedSVD factors with a ridge fold-in for listeners outside the fit."""

    def __init__(self, n_components: int = 12) -> None:
        self.n_components = n_components
        self.item_ids: list[str] = []
        self.index: dict[str, int] = {}
        self.user_ids: list[str] = []
        self.user_index: dict[str, int] = {}
        self.item_factors: np.ndarray | None = None
        self.user_factors: np.ndarray | None = None
        self.mean = 0.0
        self.std = 1.0
        self.fitted = False

    def fit(self, user_ids: list[str], item_ids: list[str], matrix: np.ndarray) -> None:
        components = max(2, min(self.n_components, matrix.shape[0] - 1, matrix.shape[1] - 1))
        svd = TruncatedSVD(n_components=components, random_state=42)
        user_factors = svd.fit_transform(matrix)
        item_factors = svd.components_.T
        self.user_ids = list(user_ids)
        self.user_index = {user_id: index for index, user_id in enumerate(user_ids)}
        self.item_ids = list(item_ids)
        self.index = {item_id: index for index, item_id in enumerate(item_ids)}
        self.user_factors = user_factors
        self.item_factors = item_factors
        samples: list[np.ndarray] = []
        for factors in user_factors:
            samples.append(factors @ item_factors.T)
        stacked = np.concatenate(samples)
        self.mean = float(np.mean(stacked))
        self.std = float(np.std(stacked) + 1e-6)
        self.fitted = True

    def _calibrate(self, raw: np.ndarray) -> dict[str, float]:
        scale = self.std if self.std > 1e-6 else 1.0
        return {
            track_id: sigmoid((float(raw[index]) - self.mean) / scale)
            for index, track_id in enumerate(self.item_ids)
        }

    def score_known_user(self, user_id: str) -> dict[str, float] | None:
        if not self.fitted or self.user_factors is None or self.item_factors is None:
            return None
        index = self.user_index.get(user_id)
        if index is None:
            return None
        raw = self.user_factors[index] @ self.item_factors.T
        return self._calibrate(raw)

    def score_fold_in(self, weights_by_item: dict[str, float], min_positive: int) -> dict[str, float] | None:
        if not self.fitted or self.item_factors is None:
            return None
        weights = np.zeros(len(self.item_ids), dtype=np.float64)
        positive_tracks = 0
        for track_id, value in weights_by_item.items():
            index = self.index.get(track_id)
            if index is None:
                continue
            weights[index] = value
            if value > 0:
                positive_tracks += 1
        if positive_tracks < min_positive:
            return None
        gram = self.item_factors.T @ self.item_factors
        ridge = gram + np.eye(gram.shape[0])
        factors = np.linalg.solve(ridge, self.item_factors.T @ weights)
        raw = factors @ self.item_factors.T
        return self._calibrate(raw)


def popularity_scores(item_ids: list[str], matrix: np.ndarray) -> dict[str, float]:
    """Log-scaled positive mass. This is synthetic play mass in demo mode."""
    positive = np.clip(matrix, 0.0, None).sum(axis=0)
    logged = np.log1p(positive)
    peak = float(logged.max()) if len(logged) else 0.0
    if peak <= 1e-12:
        return {item_id: 0.0 for item_id in item_ids}
    return {item_id: float(logged[index] / peak) for index, item_id in enumerate(item_ids)}


def build_matrix(user_ids: list[str], item_ids: list[str], events: list[dict]) -> np.ndarray:
    from app.ml.profile import interaction_weights

    user_index = {user_id: index for index, user_id in enumerate(user_ids)}
    item_index = {item_id: index for index, item_id in enumerate(item_ids)}
    by_user: dict[str, list[dict]] = {user_id: [] for user_id in user_ids}
    for event in events:
        if event["user_id"] in by_user:
            by_user[event["user_id"]].append(event)
    matrix = np.zeros((len(user_ids), len(item_ids)), dtype=np.float64)
    for user_id, user_events in by_user.items():
        for track_id, weight in interaction_weights(user_events).items():
            item = item_index.get(track_id)
            if item is None:
                continue
            matrix[user_index[user_id], item] = weight
    return matrix
