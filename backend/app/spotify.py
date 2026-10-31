"""Spotify catalog search for playlist generation.

Uses the official Web API with client credentials. Playback is limited to the
30-second preview URL Spotify returns (`p.scdn.co`). Full audio is never
requested or stored. Spotify tracks are not fed into the ranker.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.services.engine import EngineError

_ID = re.compile(r"^[A-Za-z0-9]{10,32}$")
_PREVIEW_HOST = "p.scdn.co"
_IMAGE_HOST = "i.scdn.co"

MOOD_TERMS = {
    "happy": "happy",
    "sad": "sad",
    "angry": "intense",
    "calm": "calm acoustic",
    "focused": "focus",
    "energetic": "energetic",
    "romantic": "romantic",
    "nocturnal": "late night",
    "hopeful": "hopeful",
    "surprised": "upbeat",
}


class SpotifyError(Exception):
    pass


def _spotify_message(response: httpx.Response) -> str:
    text = (response.text or "").strip()
    try:
        error = response.json().get("error")
    except Exception:
        error = None
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    if isinstance(error, str) and error:
        return error
    if text and len(text) < 400:
        return text
    return "Spotify search failed."


class SpotifyClient:
    def __init__(self, client_id: str, client_secret: str, market: str = "IN") -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.market = market
        self._access_token = ""
        self._expiry = 0.0

    @classmethod
    def from_settings(cls, settings: Settings) -> "SpotifyClient":
        return cls(settings.spotify_client_id, settings.spotify_client_secret, settings.spotify_market)

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def search_tracks(self, query: str) -> list[dict]:
        if not self.configured:
            raise SpotifyError("Spotify credentials are not configured.")
        response = httpx.get(
            "https://api.spotify.com/v1/search",
            params={"q": query, "type": "track", "limit": 10, "market": self.market},
            headers={"Authorization": f"Bearer {self._token()}"},
            timeout=15,
        )
        if response.status_code == 401:
            self._access_token = ""
            raise SpotifyError("Spotify rejected the access token.")
        if response.status_code != 200:
            raise SpotifyError(_spotify_message(response))
        items = response.json().get("tracks", {}).get("items") or []
        tracks = []
        for item in items:
            parsed = parse_track(item)
            if parsed:
                tracks.append(parsed)
        return tracks

    def _token(self) -> str:
        now = time.time()
        if self._access_token and now < self._expiry:
            return self._access_token
        response = httpx.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            timeout=15,
        )
        if response.status_code != 200:
            raise SpotifyError("Spotify refused the app credentials.")
        body = response.json()
        token = body.get("access_token")
        if not token:
            raise SpotifyError("Spotify did not return an access token.")
        self._access_token = token
        self._expiry = now + max(30, int(body.get("expires_in", 3600)) - 60)
        return token


def parse_track(item: dict) -> dict | None:
    if not isinstance(item, dict) or item.get("type") != "track" or item.get("is_local"):
        return None
    spotify_id = str(item.get("id") or "")
    if not _ID.match(spotify_id):
        return None
    artists = item.get("artists") or []
    names = [str(artist.get("name")).strip() for artist in artists if isinstance(artist, dict) and artist.get("name")]
    album = item.get("album") if isinstance(item.get("album"), dict) else {}
    images = album.get("images") if isinstance(album.get("images"), list) else []
    image = None
    for candidate in images:
        if isinstance(candidate, dict) and _https_host(candidate.get("url"), _IMAGE_HOST):
            image = candidate["url"]
            break
    return {
        "spotify_id": spotify_id,
        "title": str(item.get("name") or "Untitled").strip() or "Untitled",
        "artist": ", ".join(names) or "Unknown artist",
        "album": str(album.get("name") or "").strip(),
        "image": image,
        "preview_url": _https_host(item.get("preview_url"), _PREVIEW_HOST),
        "spotify_url": f"https://open.spotify.com/track/{spotify_id}",
        "duration_ms": max(0, int(item.get("duration_ms") or 0)),
        "popularity": max(0, int(item.get("popularity") or 0)),
    }


def build_queries(prompt: str, mood: str | None, genres: list[str]) -> list[str]:
    text = " ".join(prompt.split())
    if len(text) > 120:
        text = text[:120].rsplit(" ", 1)[0] or text[:120]
    mood_term = MOOD_TERMS.get(mood or "", "")
    queries: list[str] = []
    if text:
        queries.append(text)
        if mood_term:
            queries.append(f"{text} {mood_term}")
    elif mood_term:
        queries.append(mood_term)
        for genre in genres[:2]:
            queries.append(f"{mood_term} {genre.replace('-', ' ')}")
    else:
        for genre in genres[:3]:
            queries.append(genre.replace("-", " "))
    unique: list[str] = []
    for query in queries:
        cleaned = query.strip()
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    return unique[:4]


def pick_tracks(candidates: list[dict], limit: int, artist_cap: int = 3) -> list[dict]:
    ordered = sorted(candidates, key=lambda track: (track.get("preview_url") is None, -int(track.get("popularity") or 0)))
    chosen: list[dict] = []
    deferred: list[dict] = []
    counts: dict[str, int] = {}
    seen: set[str] = set()
    for track in ordered:
        artist = track["artist"]
        if counts.get(artist, 0) >= artist_cap:
            deferred.append(track)
            continue
        chosen.append(track)
        seen.add(track["spotify_id"])
        counts[artist] = counts.get(artist, 0) + 1
        if len(chosen) == limit:
            return [_public_track(item) for item in chosen]
    for track in deferred:
        if track["spotify_id"] in seen:
            continue
        chosen.append(track)
        seen.add(track["spotify_id"])
        if len(chosen) == limit:
            break
    return [_public_track(item) for item in chosen]


def _public_track(track: dict) -> dict:
    return {key: track[key] for key in ("spotify_id", "title", "artist", "album", "image", "preview_url", "spotify_url", "duration_ms")}


def _https_host(value: object, host: str) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != host:
        return None
    return value


def missing_credentials() -> EngineError:
    return EngineError(
        503,
        "Set MOODWAVE_SPOTIFY_CLIENT_ID and MOODWAVE_SPOTIFY_CLIENT_SECRET from a Spotify app, then restart the API.",
    )
