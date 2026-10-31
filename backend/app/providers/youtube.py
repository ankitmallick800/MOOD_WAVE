"""Turn a YouTube Music search row into a catalog track.

Playback is the official embedded player when the caller already knows the
video can be embedded. Otherwise the track keeps the watch link and play is
disabled. No stream URL is stored.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.data.catalog import Track

_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_IMAGE_HOSTS = ("ytimg.com", "googleusercontent.com", "ggpht.com")


def track_from_youtube(payload: dict) -> Track:
    video_id = str(payload.get("provider_id") or "")
    if not _VIDEO_ID.match(video_id):
        raise ValueError("That YouTube video id cannot be saved.")
    title = str(payload.get("title") or "").strip()
    artist = str(payload.get("artist") or "").strip()
    if not title or not artist:
        raise ValueError("A song needs a title and an artist.")
    embeddable = payload.get("embeddable")
    embed_url = None
    kind = "unavailable"
    if embeddable is True:
        kind = "embed"
        embed_url = f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0"
    song_ms = payload.get("song_duration_ms")
    song_ms = int(song_ms) if isinstance(song_ms, int) and song_ms > 0 else 0
    external = _watch_url(payload.get("external_url"), video_id)
    return Track(
        id=f"yt:{video_id}",
        title=title,
        artist=artist,
        album=str(payload.get("album") or "").strip(),
        genres=(),
        language="",
        year=0,
        duration_ms=song_ms,
        tempo=None,
        energy=None,
        danceability=None,
        acousticness=None,
        valence=None,
        speechiness=None,
        instrumentalness=None,
        loudness=None,
        musical_key=None,
        mode=None,
        mood_tags=(),
        feature_source="youtube_metadata",
        observed=(),
        provider="youtube",
        artwork_url=_image(payload.get("artwork_url")),
        preview_url=None,
        external_url=external,
        embed_url=embed_url,
        playback_kind=kind,
        preview_duration_ms=None,
        song_duration_ms=song_ms or None,
        genre_labels=(),
    )


def _watch_url(value: object, video_id: str) -> str:
    fallback = f"https://music.youtube.com/watch?v={video_id}"
    if not isinstance(value, str) or not value.startswith("https://"):
        return fallback
    host = (urlparse(value).hostname or "").lower()
    if host in {"music.youtube.com", "www.youtube.com", "youtube.com", "youtu.be"}:
        return value
    return fallback


def _image(value: object) -> str | None:
    if not isinstance(value, str) or not value.startswith("https://"):
        return None
    host = (urlparse(value).hostname or "").lower()
    if any(host == suffix or host.endswith("." + suffix) for suffix in _IMAGE_HOSTS):
        return value
    return None
