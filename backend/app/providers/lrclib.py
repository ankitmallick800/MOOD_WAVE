"""Lyrics from the public LRCLIB API.

LRCLIB returns plain text and, when someone has timed them, LRC lines.
Nothing here is inferred. A miss stays a miss.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

_API = "https://lrclib.net/api"
_USER_AGENT = "Moodwave/1.0 (local music player)"
_HIT_TTL = 7 * 24 * 3600
_MISS_TTL = 6 * 3600
_STAMP = re.compile(r"\[(\d{1,2}):(\d{1,2}(?:\.\d+)?)\]")
_VERSION_TAGS = ("remix", "live", "karaoke", "acoustic", "instrumental", "slowed", "reverb", "cover")
_CACHE: dict[str, tuple[float, dict]] = {}


def clear_cache() -> None:
    _CACHE.clear()


def parse_synced(text: str) -> list[dict]:
    """Turn an LRC body into {at_ms, text} lines. Repeated stamps share one line."""
    parsed: list[dict] = []
    for raw in text.splitlines():
        stamps = list(_STAMP.finditer(raw))
        if not stamps:
            continue
        body = _STAMP.sub("", raw).strip()
        for stamp in stamps:
            minutes = int(stamp.group(1))
            seconds = float(stamp.group(2))
            parsed.append({"at_ms": int(round((minutes * 60 + seconds) * 1000)), "text": body})
    parsed.sort(key=lambda item: item["at_ms"])
    return parsed


def choose_record(records: list[dict], title: str, artist: str, duration_s: int) -> dict | None:
    """Pick a record whose title matches, and whose artist shares a real name."""
    wanted_title = _norm(title)
    wanted_artists = _tokens(artist)
    if not wanted_title:
        return None
    best: dict | None = None
    best_rank: tuple[int, float] | None = None
    for record in records:
        if not isinstance(record, dict):
            continue
        candidate_title = str(record.get("trackName") or "")
        if _norm(candidate_title) != wanted_title:
            continue
        if _version_tags(candidate_title) != _version_tags(title):
            continue
        names = _tokens(str(record.get("artistName") or ""))
        if wanted_artists and names and not (wanted_artists & names):
            continue
        synced = bool(str(record.get("syncedLyrics") or "").strip())
        plain = bool(str(record.get("plainLyrics") or "").strip())
        if not synced and not plain and not record.get("instrumental"):
            continue
        duration = record.get("duration")
        gap = abs(float(duration) - duration_s) if isinstance(duration, (int, float)) and duration_s else 0.0
        if duration_s and isinstance(duration, (int, float)) and gap > 45:
            continue
        rank = (0 if synced else 1, gap)
        if best_rank is None or rank < best_rank:
            best_rank = rank
            best = record
    return best


def lookup_lyrics(title: str, artist: str, album: str, duration_ms: int, opener=None) -> dict:
    """Return lyrics for one song. Network failures become an empty, labeled result."""
    duration_s = int(duration_ms // 1000) if duration_ms and duration_ms > 0 else 0
    key = f"{_norm(title)}|{_norm(artist)}|{duration_s}"
    cached = _CACHE.get(key)
    now = time.time()
    if cached and cached[0] > now:
        return cached[1]
    opener = opener or urllib.request.urlopen
    try:
        record = _fetch(title, artist, album, duration_s, opener)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeError, OSError):
        return _empty("Lyrics could not be loaded.")
    if record is None:
        result = _empty("No lyrics on LRCLIB for this song.")
        _CACHE[key] = (now + _MISS_TTL, result)
        return result
    result = _pack(record)
    _CACHE[key] = (now + _HIT_TTL, result)
    return result


def _fetch(title: str, artist: str, album: str, duration_s: int, opener) -> dict | None:
    found = _request("/search", {"track_name": title, "artist_name": artist}, opener)
    if isinstance(found, list):
        chosen = choose_record([item for item in found if isinstance(item, dict)], title, artist, duration_s)
        if chosen is not None:
            return chosen
    exact = _request(
        "/get",
        {"track_name": title, "artist_name": artist, "album_name": album, "duration": str(duration_s or "")},
        opener,
    )
    if isinstance(exact, dict):
        return choose_record([exact], title, artist, duration_s)
    return None


def _request(path: str, params: dict[str, str], opener):
    query = urllib.parse.urlencode({key: value for key, value in params.items() if value})
    request = urllib.request.Request(
        f"{_API}{path}?{query}",
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    delay = 0.6
    for attempt in range(3):
        try:
            with opener(request, timeout=6) as response:
                body = response.read(1_000_000)
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code in {429, 503} and attempt < 2:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    else:
        return None
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _pack(record: dict) -> dict:
    synced = str(record.get("syncedLyrics") or "").strip()
    plain = str(record.get("plainLyrics") or "").strip()
    lines = parse_synced(synced) if synced else []
    instrumental = bool(record.get("instrumental")) and not lines and not plain
    return {
        "found": True,
        "source": "LRCLIB",
        "instrumental": instrumental,
        "synced": bool(lines),
        "lines": lines,
        "plain": plain or "\n".join(line["text"] for line in lines if line["text"]),
        "message": "LRCLIB lists this recording as instrumental." if instrumental else None,
    }


def _empty(message: str) -> dict:
    return {
        "found": False,
        "source": "LRCLIB",
        "instrumental": False,
        "synced": False,
        "lines": [],
        "plain": "",
        "message": message,
    }


def _norm(value: str) -> str:
    cleaned = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", value.casefold())
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return " ".join(cleaned.split())


def _tokens(value: str) -> set[str]:
    return {token for token in _norm(value).split() if len(token) > 2}


def _version_tags(value: str) -> set[str]:
    folded = value.casefold()
    return {tag for tag in _VERSION_TAGS if tag in folded}
