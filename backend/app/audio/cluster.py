"""K-means clustering of catalog audio features, with a silhouette search.

The number of clusters is the k in 3..7 with the highest silhouette score.
A PCA projection is returned for the scatter plot. This uses whatever numeric
features the catalog marks as observed. It does not invent the ones that are missing.
"""

from __future__ import annotations

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from app.data.catalog import Track

CLUSTER_FEATURES = ("energy", "danceability", "acousticness", "valence", "tempo_norm")


def cluster_catalog(tracks: list[Track], seed: int = 42) -> dict:
    rows = []
    used_tracks: list[Track] = []
    for track in tracks:
        values = []
        missing = False
        for name in CLUSTER_FEATURES:
            value = track.tempo_norm if name == "tempo_norm" else getattr(track, name)
            if value is None:
                missing = True
                break
            values.append(float(value))
        if missing:
            continue
        rows.append(values)
        used_tracks.append(track)
    if len(used_tracks) < 8:
        return {
            "available": False,
            "reason": "Fewer than 8 tracks have the complete audio-feature set required for clustering.",
            "feature_source": _dominant_source(tracks),
            "features": list(CLUSTER_FEATURES),
        }

    matrix = np.array(rows, dtype=np.float64)
    scaler = StandardScaler()
    scaled = scaler.fit_transform(matrix)
    upper = min(7, len(used_tracks) - 1)
    diagnostics = []
    best: tuple | None = None
    for k in range(3, upper + 1):
        model = KMeans(n_clusters=k, random_state=seed, n_init=10)
        labels = model.fit_predict(scaled)
        if len(set(labels)) < 2:
            continue
        score = float(silhouette_score(scaled, labels))
        diagnostics.append({"k": k, "silhouette": score})
        if best is None or score > best[0]:
            best = (score, k, labels, model)
    if best is None:
        return {
            "available": False,
            "reason": "Silhouette search did not find a stable clustering.",
            "feature_source": _dominant_source(used_tracks),
            "features": list(CLUSTER_FEATURES),
        }
    score, k, labels, model = best
    pca = PCA(n_components=2, random_state=seed)
    projection = pca.fit_transform(scaled)
    clusters = []
    for cluster_id in range(k):
        members = [track for track, label in zip(used_tracks, labels) if int(label) == cluster_id]
        clusters.append(_summarize(cluster_id, members))
    points = []
    for index, track in enumerate(used_tracks):
        points.append(
            {
                "track_id": track.id,
                "title": track.title,
                "artist": track.artist,
                "x": float(projection[index, 0]),
                "y": float(projection[index, 1]),
                "cluster": int(labels[index]),
                "genres": list(track.genres),
                "energy": track.energy,
                "valence": track.valence,
            }
        )
    return {
        "available": True,
        "k": k,
        "silhouette": score,
        "diagnostics": diagnostics,
        "selection": "k with the highest silhouette coefficient on standardized features, searched from 3 to 7.",
        "method": "kmeans",
        "projection": "pca",
        "explained_variance_ratio": [float(value) for value in pca.explained_variance_ratio_],
        "features": list(CLUSTER_FEATURES),
        "feature_source": _dominant_source(used_tracks),
        "n_tracks": len(used_tracks),
        "clusters": clusters,
        "points": points,
        "inertia": float(model.inertia_),
    }


def _dominant_source(tracks: list[Track]) -> str:
    if not tracks:
        return "none"
    counts: dict[str, int] = {}
    for track in tracks:
        counts[track.feature_source] = counts.get(track.feature_source, 0) + 1
    return max(counts, key=counts.get)


def _summarize(cluster_id: int, members: list[Track]) -> dict:
    def mean(name: str) -> float | None:
        values = [getattr(track, name) for track in members if getattr(track, name) is not None]
        if not values:
            return None
        return float(np.mean(values))

    genre_counts: dict[str, int] = {}
    for track in members:
        for genre in track.genres:
            genre_counts[genre] = genre_counts.get(genre, 0) + 1
    top_genre = max(genre_counts, key=genre_counts.get) if genre_counts else "mixed"
    energy = mean("energy") or 0.5
    acoustic = mean("acousticness") or 0.5
    valence = mean("valence") or 0.5
    if energy < 0.35 and acoustic > 0.6:
        texture = "Quiet / acoustic"
    elif energy > 0.75:
        texture = "High energy"
    elif valence > 0.7:
        texture = "Bright"
    elif valence < 0.35:
        texture = "Low valence"
    else:
        texture = "Mid texture"
    return {
        "id": cluster_id,
        "size": len(members),
        "label": f"{texture} · mostly {top_genre}",
        "top_genre": top_genre,
        "mean_energy": mean("energy"),
        "mean_valence": mean("valence"),
        "mean_acousticness": mean("acousticness"),
        "mean_danceability": mean("danceability"),
        "mean_tempo": mean("tempo"),
    }
