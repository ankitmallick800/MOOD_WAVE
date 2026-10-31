"""Listening-mood targets and expression-to-mood mapping.

Targets are playlist-shaping feature centers. They are not diagnoses.
"""

from __future__ import annotations

import math

EXPRESSIONS: tuple[str, ...] = (
    "happy",
    "sad",
    "angry",
    "neutral",
    "surprised",
    "fearful",
    "disgusted",
)

# Only expressions with a stable, conservative listening mapping are suggested.
# Fearful and disgusted stay unmapped so the user has to choose.
EXPRESSION_TO_MOOD: dict[str, str | None] = {
    "happy": "happy",
    "sad": "sad",
    "angry": "angry",
    "neutral": "calm",
    "surprised": "surprised",
    "fearful": None,
    "disgusted": None,
}

CONFIDENCE_THRESHOLD = 0.55

# Feature centers in the same normalized space as catalog audio metadata.
MOOD_TARGETS: dict[str, dict[str, float]] = {
    "happy": {"energy": 0.72, "valence": 0.84, "danceability": 0.70, "acousticness": 0.25, "tempo_norm": 0.55},
    "sad": {"energy": 0.28, "valence": 0.22, "danceability": 0.32, "acousticness": 0.76, "tempo_norm": 0.30},
    "angry": {"energy": 0.88, "valence": 0.26, "danceability": 0.46, "acousticness": 0.10, "tempo_norm": 0.74},
    "calm": {"energy": 0.22, "valence": 0.52, "danceability": 0.26, "acousticness": 0.84, "tempo_norm": 0.26},
    "focused": {"energy": 0.38, "valence": 0.48, "danceability": 0.30, "acousticness": 0.58, "tempo_norm": 0.40},
    "energetic": {"energy": 0.88, "valence": 0.68, "danceability": 0.80, "acousticness": 0.12, "tempo_norm": 0.76},
    "romantic": {"energy": 0.42, "valence": 0.64, "danceability": 0.48, "acousticness": 0.58, "tempo_norm": 0.40},
    "nocturnal": {"energy": 0.36, "valence": 0.36, "danceability": 0.44, "acousticness": 0.46, "tempo_norm": 0.38},
    "hopeful": {"energy": 0.58, "valence": 0.76, "danceability": 0.54, "acousticness": 0.42, "tempo_norm": 0.52},
    "surprised": {"energy": 0.74, "valence": 0.60, "danceability": 0.64, "acousticness": 0.22, "tempo_norm": 0.66},
}

# Shift mode moves away from the current mood toward a listening outcome.
SHIFT_TARGETS: dict[str, str] = {
    "sad": "hopeful",
    "angry": "calm",
    "calm": "hopeful",
    "happy": "energetic",
    "surprised": "calm",
    "energetic": "happy",
    "focused": "calm",
    "nocturnal": "calm",
    "romantic": "happy",
    "hopeful": "happy",
}

MOOD_TAG_ALIGNMENT: dict[str, tuple[str, ...]] = {
    "happy": ("joyful", "groovy", "hopeful"),
    "sad": ("melancholic", "nocturnal"),
    "angry": ("aggressive", "tense", "energetic"),
    "calm": ("calm", "dreamy", "focused"),
    "focused": ("focused", "calm"),
    "energetic": ("energetic", "groovy", "joyful"),
    "romantic": ("romantic", "hopeful"),
    "nocturnal": ("nocturnal", "dreamy", "melancholic"),
    "hopeful": ("hopeful", "joyful", "calm"),
    "surprised": ("energetic", "joyful"),
}

_MOOD_DIMS = ("energy", "valence", "danceability", "acousticness", "tempo_norm")


def resolve_target(mood: str, mode: str) -> tuple[str, str]:
    """Return (source_mood, target_mood). Match keeps the source."""
    source = mood
    if mode == "shift":
        return source, SHIFT_TARGETS.get(mood, "hopeful")
    return source, source


def mood_compatibility(track_values: dict[str, float | None], mood_tags: tuple[str, ...], target_mood: str) -> float | None:
    """Gaussian closeness to the target center, plus editorial tag overlap.

    Dimensions the track does not have are skipped and the remaining distances
    are renormalized. If nothing is observed, the score is missing.
    """
    target = MOOD_TARGETS[target_mood]
    distances: list[float] = []
    for dim in _MOOD_DIMS:
        actual = track_values.get(dim)
        if actual is None:
            continue
        distances.append(abs(float(actual) - target[dim]))
    if not distances:
        kernel = None
    else:
        dist = sum(distances) / len(distances)
        kernel = math.exp(-(dist ** 2) / (2 * 0.18 ** 2))
    aligned = MOOD_TAG_ALIGNMENT.get(target_mood, ())
    if mood_tags and aligned:
        tag_score = len(set(mood_tags) & set(aligned)) / len(set(mood_tags))
    else:
        tag_score = None
    if kernel is None and tag_score is None:
        return None
    if kernel is None:
        return float(tag_score)
    if tag_score is None:
        return float(kernel)
    return float(0.78 * kernel + 0.22 * tag_score)


def interpret_expression(distribution: dict[str, float]) -> dict:
    """Turn a client-smoothed expression distribution into a suggested mood.

    The server never sees an image. Low confidence, or an expression without a
    listening mapping, produces no suggestion.
    """
    cleaned: dict[str, float] = {}
    for key, value in distribution.items():
        if key not in EXPRESSIONS:
            continue
        cleaned[key] = max(0.0, float(value))
    total = sum(cleaned.values())
    if total <= 0:
        raise ValueError("Expression distribution is empty.")
    cleaned = {key: value / total for key, value in cleaned.items()}
    top = max(cleaned, key=cleaned.get)
    confidence = cleaned[top]
    mapped = EXPRESSION_TO_MOOD.get(top)
    uncertain = confidence < CONFIDENCE_THRESHOLD or mapped is None
    if mapped is None:
        reason = (
            f"The top expression is {top}, which this app does not map to a "
            "listening mood. Choose one manually."
        )
    elif uncertain:
        reason = (
            f"Confidence {confidence:.0%} is below {CONFIDENCE_THRESHOLD:.0%}. "
            "The frame is too uncertain to suggest a mood."
        )
    else:
        reason = (
            f"Highest smoothed score is {top} ({confidence:.0%}). "
            "This is a temporary listening signal, not a read of how you feel."
        )
    return {
        "expression": top,
        "confidence": confidence,
        "uncertain": uncertain,
        "suggested_mood": None if uncertain else mapped,
        "distribution": cleaned,
        "mapping_available": mapped is not None,
        "reason": reason,
        "disclaimer": (
            "Expression estimates are uncertain and temporary. They are not an "
            "assessment of emotional state. Confirm or override the mood before "
            "recommendations change. Face images are not uploaded or stored."
        ),
        "images_stored": False,
    }
