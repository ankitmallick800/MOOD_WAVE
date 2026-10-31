"""Request bodies. Response shapes are produced by the engine and documented in docs/API.md."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OnboardingIn(BaseModel):
    user_id: str = "local-user"
    artists: list[str] = Field(default_factory=list)
    genres: list[str] = Field(min_length=1)
    languages: list[str] = Field(min_length=1)
    purpose: str
    discovery: float = Field(ge=0, le=1)
    energy: float = Field(ge=0, le=1)
    danceability: float = Field(ge=0, le=1)
    acousticness: float = Field(ge=0, le=1)
    valence: float = Field(ge=0, le=1)
    tempo: float = Field(ge=0, le=1)
    reset_inferred: bool = False


class FeedbackIn(BaseModel):
    user_id: str = "local-user"
    track_id: str
    event_type: str
    listen_ms: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    playlist_id: int | None = None


class ReactionIn(BaseModel):
    user_id: str = "local-user"
    track_id: str
    reaction: str


class ResetIn(BaseModel):
    user_id: str = "local-user"
    scope: str = "inferred"


class MoodPredictIn(BaseModel):
    distribution: dict[str, float]


class MoodRecommendationsIn(BaseModel):
    user_id: str = "local-user"
    mood: str
    mode: str = "match"
    source: str = "manual"
    confidence: float | None = Field(default=None, ge=0, le=1)
    confirmed: bool = False
    limit: int = Field(default=20, ge=1, le=50)


class EvaluateIn(BaseModel):
    k: int = Field(default=10, ge=1, le=30)
    diversify: bool = False
    include_svd: bool = False


class ConfigIn(BaseModel):
    weights: dict[str, float] | None = None
    group_weights: dict[str, float] | None = None
    diversity_lambda: float | None = Field(default=None, ge=0, le=1)
    artist_cap: int | None = Field(default=None, ge=1, le=6)
    limit: int | None = Field(default=None, ge=1, le=50)


class PlaylistIn(BaseModel):
    user_id: str = "local-user"
    name: str = Field(min_length=1, max_length=80)


class AppleMatchIn(BaseModel):
    user_id: str = "local-user"
    title: str = Field(min_length=1, max_length=200)
    artist: str = Field(min_length=1, max_length=200)


class CatalogImportIn(BaseModel):
    user_id: str = "local-user"
    provider: str
    provider_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    artist: str = Field(min_length=1, max_length=200)
    album: str = Field(default="", max_length=200)
    artwork_url: str | None = None
    external_url: str | None = None
    song_duration_ms: int | None = Field(default=None, ge=0, le=2_000_000)
    embeddable: bool | None = None


class SpotifyPlaylistIn(BaseModel):
    user_id: str = "local-user"
    name: str = Field(min_length=1, max_length=80)
    prompt: str = Field(default="", max_length=160)
    mood: str | None = None
    limit: int = Field(default=12, ge=5, le=20)
    use_profile: bool = True
