"""YouTube Music search for the playlist generator.

Uses ytmusicapi's unauthenticated search. Songs are saved in this app.
Playback is the official YouTube player when embedding is allowed, otherwise
a link to the video. Stream URLs are never requested.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from app.config import Settings

_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_IMAGE_SUFFIXES = ("ytimg.com", "googleusercontent.com", "ggpht.com")
_MIN_SECONDS = 75
_MAX_SECONDS = 420


class YTMusicError(Exception):
    pass


class YTMusicCatalog:
    def __init__(self, location: str = "IN") -> None:
        self.location = location
        self._yt = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "YTMusicCatalog":
        return cls(settings.ytmusic_location)

    def search_songs(self, query: str) -> list[dict]:
        try:
            rows = self._client().search(query, filter="songs", limit=20)
        except Exception as exc:
            raise YTMusicError("YouTube Music search failed.") from exc
        songs = []
        for row in rows or []:
            parsed = parse_song(row)
            if parsed:
                songs.append(parsed)
            if len(songs) == 10:
                break
        return songs

    def _client(self):
        if self._yt is None:
            from ytmusicapi import YTMusic

            self._yt = YTMusic(location=self.location, language="en")
        return self._yt


def parse_song(item: dict) -> dict | None:
    if not isinstance(item, dict) or item.get("resultType") not in (None, "song"):
        return None
    if item.get("isAvailable") is False:
        return None
    video_id = str(item.get("videoId") or "")
    if not _VIDEO_ID.match(video_id):
        return None
    seconds = _seconds(item)
    if seconds is None or not (_MIN_SECONDS <= seconds <= _MAX_SECONDS):
        return None
    artists = item.get("artists") or []
    names = [str(artist.get("name")).strip() for artist in artists if isinstance(artist, dict) and artist.get("name")]
    album = item.get("album") if isinstance(item.get("album"), dict) else {}
    return {
        "video_id": video_id,
        "title": str(item.get("title") or "Untitled").strip() or "Untitled",
        "artist": ", ".join(names) or "Unknown artist",
        "album": str(album.get("name") or "").strip(),
        "image": _image(item.get("thumbnails")),
        "watch_url": f"https://music.youtube.com/watch?v={video_id}",
        "duration_ms": seconds * 1000,
    }


def pick_songs(candidates: list[dict], limit: int, artist_cap: int = 3) -> list[dict]:
    chosen: list[dict] = []
    deferred: list[dict] = []
    counts: dict[str, int] = {}
    seen: set[str] = set()
    for track in candidates:
        if track["video_id"] in seen:
            continue
        if counts.get(track["artist"], 0) >= artist_cap:
            deferred.append(track)
            continue
        chosen.append(track)
        seen.add(track["video_id"])
        counts[track["artist"]] = counts.get(track["artist"], 0) + 1
        if len(chosen) == limit:
            return chosen
    for track in deferred:
        if track["video_id"] in seen:
            continue
        chosen.append(track)
        seen.add(track["video_id"])
        if len(chosen) == limit:
            break
    return chosen


def _seconds(item: dict) -> int | None:
    raw = item.get("duration_seconds")
    if isinstance(raw, int) and raw > 0:
        return raw
    text = str(item.get("duration") or "")
    parts = text.split(":")
    if not parts or any(not part.isdigit() for part in parts):
        return None
    total = 0
    for part in parts:
        total = total * 60 + int(part)
    return total or None


def _image(thumbnails: object) -> str | None:
    if not isinstance(thumbnails, list):
        return None
    for candidate in thumbnails:
        if not isinstance(candidate, dict):
            continue
        url = candidate.get("url")
        if not isinstance(url, str):
            continue
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if parsed.scheme == "https" and any(host == suffix or host.endswith("." + suffix) for suffix in _IMAGE_SUFFIXES):
            return url
    return None


def mark_embeds(tracks: list[dict], cache_path: Path | None = None) -> None:
    """Set embeddable and embed_url from YouTube's oEmbed endpoint.

    A failed check stays unknown. It is not treated as permission to embed.
    """
    cache = _embed_cache(cache_path)
    pending: list[str] = []
    for track in tracks:
        video_id = str(track.get("video_id") or "")
        if not _VIDEO_ID.match(video_id):
            track["embeddable"] = False
            track["embed_url"] = None
            continue
        cached = cache.get(video_id)
        if cached is None:
            pending.append(video_id)
            continue
        _apply_embed(track, video_id, cached)
    if pending:
        with ThreadPoolExecutor(max_workers=6) as pool:
            checked = list(pool.map(_embed_allowed, pending))
        for video_id, result in zip(pending, checked):
            if result is not None:
                cache[video_id] = result
            for track in tracks:
                if track.get("video_id") == video_id and "embeddable" not in track:
                    _apply_embed(track, video_id, result)
    if cache_path is not None and cache:
        _write_embed_cache(cache_path, cache)


def _apply_embed(track: dict, video_id: str, allowed: bool | None) -> None:
    track["embeddable"] = allowed
    track["embed_url"] = f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0" if allowed else None


def _embed_allowed(video_id: str) -> bool | None:
    query = urllib.parse.urlencode({"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"})
    request = urllib.request.Request(
        f"https://www.youtube.com/oembed?{query}",
        headers={"User-Agent": "Moodwave/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            return response.status == 200
    except urllib.error.HTTPError:
        return False
    except Exception:
        return None


def _embed_cache(path: Path | None) -> dict[str, bool]:
    if path is None or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    rows = payload.get("ids") if isinstance(payload, dict) else None
    if not isinstance(rows, dict):
        return {}
    now = time.time()
    fresh: dict[str, bool] = {}
    for video_id, row in rows.items():
        if not isinstance(row, dict) or not isinstance(row.get("ok"), bool):
            continue
        checked = row.get("at")
        if isinstance(checked, (int, float)) and now - float(checked) < 7 * 24 * 3600:
            fresh[str(video_id)] = bool(row["ok"])
    return fresh


def _write_embed_cache(path: Path, cache: dict[str, bool]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ids": {video_id: {"ok": allowed, "at": time.time()} for video_id, allowed in cache.items()}}
    path.write_text(json.dumps(payload), encoding="utf-8")
