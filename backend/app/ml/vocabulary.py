"""Closed vocabularies shared by the catalog, profiles, and feature vectors.

Track mood tags describe catalog metadata. Listening moods are user-session
targets. They are not treated as measurements of anyone's emotional state.
"""

from __future__ import annotations

GENRES: tuple[str, ...] = (
    "indie",
    "pop",
    "rock",
    "alt",
    "jazz",
    "classical",
    "electronic",
    "hip-hop",
    "r&b",
    "folk",
    "ambient",
    "lo-fi",
    "metal",
    "soul",
    "bengali-modern",
    "bollywood",
    "k-pop",
    "latin",
    "french-pop",
    "singer-songwriter",
)

LANGUAGES: tuple[str, ...] = ("en", "bn", "hi", "es", "ko", "ja", "fr", "pt")

LANGUAGE_LABELS: dict[str, str] = {
    "en": "English",
    "bn": "Bengali",
    "hi": "Hindi",
    "es": "Spanish",
    "ko": "Korean",
    "ja": "Japanese",
    "fr": "French",
    "pt": "Portuguese",
}

# Editorial tags stored on tracks.
MOOD_TAGS: tuple[str, ...] = (
    "melancholic",
    "joyful",
    "calm",
    "energetic",
    "focused",
    "nocturnal",
    "romantic",
    "tense",
    "hopeful",
    "dreamy",
    "groovy",
    "aggressive",
)

# User-selected or camera-confirmed listening targets.
LISTENING_MOODS: tuple[str, ...] = (
    "happy",
    "sad",
    "angry",
    "calm",
    "focused",
    "energetic",
    "romantic",
    "nocturnal",
    "hopeful",
    "surprised",
)

PURPOSES: tuple[str, ...] = (
    "focus",
    "relax",
    "energy",
    "sleep",
    "commute",
    "mood_lift",
    "none",
)

PURPOSE_LABELS: dict[str, str] = {
    "focus": "Focus",
    "relax": "Relax",
    "energy": "Energy",
    "sleep": "Sleep",
    "commute": "Commute",
    "mood_lift": "Lift my mood",
    "none": "No specific purpose",
}

# Numeric feature order inside the content vector.
NUMERIC_KEYS: tuple[str, ...] = (
    "tempo_norm",
    "energy",
    "danceability",
    "acousticness",
    "valence",
    "speechiness",
    "instrumentalness",
    "loudness_norm",
)

FEATURE_GROUPS: tuple[str, ...] = ("numeric", "genre", "language", "mood")

DEFAULT_WEIGHTS: dict[str, float] = {
    "content": 0.34,
    "collaborative": 0.24,
    "preference": 0.22,
    "mood": 0.12,
    "discovery": 0.08,
}

# Group weights scale feature blocks inside weighted cosine (via sqrt).
# Raising "genre" makes shared genres move the angle more than raw audio numbers.
DEFAULT_GROUP_WEIGHTS: dict[str, float] = {
    "numeric": 1.0,
    "genre": 1.4,
    "language": 1.2,
    "mood": 0.85,
}

EVENT_TYPES: tuple[str, ...] = (
    "play",
    "complete",
    "skip",
    "like",
    "dislike",
    "playlist_add",
    "replay",
)

# Implicit strengths. Negative values are aversions, not missing data.
EVENT_STRENGTH: dict[str, float] = {
    "like": 3.0,
    "replay": 2.5,
    "playlist_add": 2.0,
    "complete": 2.0,
    "play": 1.0,
    "skip": -0.6,
    "dislike": -2.0,
}

MIN_COLLAB_TRACKS = 3
ARTIST_CAP_DEFAULT = 2
DIVERSITY_LAMBDA_DEFAULT = 0.78
RECOMMENDATION_LIMIT_DEFAULT = 20

LOCAL_USER_ID = "local-user"
