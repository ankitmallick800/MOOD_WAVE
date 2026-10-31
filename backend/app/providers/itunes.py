"""iTunes Search API catalog.

The response supplies title, artist, album, artwork, a genre label, the song
length, an official preview URL, and a link to Apple Music. It does not supply
tempo, energy, danceability, valence, mood, or language. Those stay unknown.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from app.data.catalog import Track
from app.ml.vocabulary import GENRES

FEATURE_SOURCE = "itunes_metadata"
_CACHE_TTL_SECONDS = 7 * 24 * 3600
_PREVIEW_HOSTS = ("apple.com",)
_ARTWORK_HOSTS = ("mzstatic.com",)
_PAGE_HOSTS = ("apple.com",)
_GENRE_MAP: dict[str, tuple[str, ...]] = {
    "pop": ("pop",),
    "rock": ("rock",),
    "alternative": ("alt",),
    "indie": ("indie",),
    "indie pop": ("indie", "pop"),
    "indie rock": ("indie", "rock"),
    "indie folk": ("indie", "folk"),
    "hip-hop/rap": ("hip-hop",),
    "hip-hop": ("hip-hop",),
    "hip hop": ("hip-hop",),
    "rap": ("hip-hop",),
    "r&b/soul": ("r&b", "soul"),
    "r&b": ("r&b",),
    "soul": ("soul",),
    "electronic": ("electronic",),
    "dance": ("electronic",),
    "edm": ("electronic",),
    "jazz": ("jazz",),
    "classical": ("classical",),
    "singer/songwriter": ("singer-songwriter",),
    "folk": ("folk",),
    "ambient": ("ambient",),
    "metal": ("metal",),
    "k-pop": ("k-pop",),
    "latin": ("latin",),
    "latino": ("latin",),
    "bollywood": ("bollywood",),
    "french pop": ("french-pop",),
    "lo-fi": ("lo-fi",),
    "lofi": ("lo-fi",),
}
SEED_QUERIES: tuple[tuple[str, str], ...] = (
    ("indie pop", "US"),
    ("indie rock", "US"),
    ("indie folk", "US"),
    ("singer songwriter", "US"),
    ("pop", "US"),
    ("folk", "US"),
    ("jazz", "US"),
    ("ambient", "US"),
    ("electronic", "US"),
    ("hip hop", "US"),
    ("k-pop", "US"),
    ("latin pop", "US"),
    ("bollywood", "IN"),
    ("arijit singh", "IN"),
    ("bengali songs", "IN"),
    ("rabindra sangeet", "IN"),
)
_LIVE_CACHE: dict[str, tuple[float, list[Track]]] = {}


class ItunesError(Exception):
    pass


def identity_key(title: str, artist: str) -> str:
    return f"{_norm(artist)}|{_norm(title)}"


def bare_title(title: str) -> str:
    text = title.casefold()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    return " ".join(text.split())


_PLACEHOLDER_TITLES = {query for query, _country in SEED_QUERIES}
_DEMO_WORD = re.compile(r"\bdemo\b", re.IGNORECASE)


def is_browse_noise(track: Track) -> bool:
    """Fictional catalog rows, demo versions, and stock titles that repeat a seed search."""
    if track.provider == "demo" or track.provider == "youtube" or track.id.startswith("mw-") or track.id.startswith("yt:"):
        return True
    if _DEMO_WORD.search(track.title):
        return True
    return bare_title(track.title) in _PLACEHOLDER_TITLES


def pick_itunes_match(tracks: list[Track], title: str, artist: str) -> Track | None:
    """Choose the Apple song with the same title and artist. A title-only hit is not a match."""
    wanted = identity_key(title, artist)
    if wanted and not wanted.startswith("|") and not wanted.endswith("|"):
        for track in tracks:
            if identity_key(track.title, track.artist) == wanted:
                return track
    title_key = _norm(title)
    artist_tokens = _tokens(artist)
    if not title_key or not artist_tokens:
        return None
    best: Track | None = None
    best_overlap = 0
    for track in tracks:
        if _norm(track.title) != title_key:
            continue
        overlap = len(artist_tokens & _tokens(track.artist))
        if overlap > best_overlap:
            best = track
            best_overlap = overlap
    return best


def _tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.casefold()) if len(token) > 2}


def map_genre(label: str) -> tuple[str, ...]:
    mapped = _GENRE_MAP.get(label.strip().casefold(), ())
    return tuple(genre for genre in mapped if genre in GENRES)


def track_from_itunes(item: dict) -> Track | None:
    if not isinstance(item, dict) or item.get("kind") not in (None, "song"):
        return None
    track_id = item.get("trackId")
    if not isinstance(track_id, int):
        return None
    title = str(item.get("trackName") or "").strip()
    artist = str(item.get("artistName") or "").strip()
    if not title or not artist:
        return None
    raw_genre = str(item.get("primaryGenreName") or "").strip()
    genres = map_genre(raw_genre)
    preview = _https(item.get("previewUrl"), _PREVIEW_HOSTS)
    artwork = _artwork(_https(item.get("artworkUrl100"), _ARTWORK_HOSTS))
    external = _https(item.get("trackViewUrl"), _PAGE_HOSTS)
    song_ms = item.get("trackTimeMillis")
    song_ms = int(song_ms) if isinstance(song_ms, int) and song_ms > 0 else 0
    observed = ["genres"] if genres else []
    return Track(
        id=f"itunes:{track_id}",
        title=title,
        artist=artist,
        album=str(item.get("collectionName") or "").strip(),
        genres=genres,
        language="",
        year=_year(item.get("releaseDate")),
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
        feature_source=FEATURE_SOURCE,
        observed=tuple(observed),
        provider="itunes",
        artwork_url=artwork,
        preview_url=preview,
        external_url=external,
        embed_url=None,
        playback_kind="preview" if preview else "unavailable",
        preview_duration_ms=None,
        song_duration_ms=song_ms or None,
        genre_labels=(raw_genre,) if raw_genre else (),
    )


def ensure_itunes_catalog(path: Path, *, allow_network: bool = True, force: bool = False) -> tuple[list[Track], str | None]:
    cached = _read_cache(path)
    fresh = cached is not None and not force and (time.time() - float(cached["fetched_at"])) < _CACHE_TTL_SECONDS
    if fresh and cached is not None:
        return _tracks_from_items(cached["items"]), None
    if not allow_network:
        if cached is not None:
            return _tracks_from_items(cached["items"]), "Using the saved Apple Music catalog."
        return [], "The Apple Music catalog is not available."
    try:
        items = _fetch_seed()
    except ItunesError:
        if cached is not None:
            return _tracks_from_items(cached["items"]), "Apple Music search is unavailable. Showing the saved catalog."
        return [], "Apple Music search is unavailable and there is no saved catalog."
    if not items:
        if cached is not None:
            return _tracks_from_items(cached["items"]), "Apple Music returned no songs. Showing the saved catalog."
        return [], "Apple Music returned no songs."
    _write_cache(path, items)
    return _tracks_from_items(items), None


def search_itunes(term: str, country: str, limit: int = 15) -> list[Track]:
    key = f"{country}:{term.casefold().strip()}"
    cached = _LIVE_CACHE.get(key)
    if cached and time.time() - cached[0] < 600:
        return cached[1][:limit]
    rows = _request(term, country, max(limit, 15))
    tracks = []
    seen: set[str] = set()
    for row in rows:
        track = track_from_itunes(row)
        if track is None or track.id in seen:
            continue
        seen.add(track.id)
        tracks.append(track)
        if len(tracks) >= limit:
            break
    _LIVE_CACHE[key] = (time.time(), tracks)
    return tracks


def _fetch_seed() -> list[dict]:
    items: list[dict] = []
    seen: set[int] = set()
    failures = 0
    for index, (term, country) in enumerate(SEED_QUERIES):
        if index:
            time.sleep(3.1)
        try:
            rows = _request(term, country, 20)
        except ItunesError:
            failures += 1
            continue
        kept = 0
        for row in rows:
            track_id = row.get("trackId")
            if not isinstance(track_id, int) or track_id in seen:
                continue
            if track_from_itunes(row) is None:
                continue
            seen.add(track_id)
            items.append(row)
            kept += 1
            if kept == 8:
                break
        if len(items) >= 140:
            break
    if not items and failures:
        raise ItunesError("iTunes search failed.")
    return items


def _request(term: str, country: str, limit: int) -> list[dict]:
    code = country if len(country) == 2 and country.isalpha() else "US"
    query = urllib.parse.urlencode(
        {
            "term": term,
            "entity": "song",
            "media": "music",
            "limit": str(max(1, min(limit, 25))),
            "country": code.upper(),
        }
    )
    request = urllib.request.Request(
        f"https://itunes.apple.com/search?{query}",
        headers={"User-Agent": "Moodwave/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise ItunesError("iTunes search failed.") from exc
    results = payload.get("results") if isinstance(payload, dict) else None
    return [row for row in results if isinstance(row, dict)] if isinstance(results, list) else []


def _tracks_from_items(items: list[dict]) -> list[Track]:
    tracks: list[Track] = []
    seen_ids: set[str] = set()
    seen_songs: set[str] = set()
    for item in items:
        track = track_from_itunes(item)
        if track is None or track.id in seen_ids:
            continue
        key = identity_key(track.title, track.artist)
        if key in seen_songs:
            continue
        seen_ids.add(track.id)
        if key:
            seen_songs.add(key)
        tracks.append(track)
    return tracks


def _read_cache(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    items = payload.get("items") if isinstance(payload, dict) else None
    fetched = payload.get("fetched_at") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not isinstance(fetched, (int, float)):
        return None
    return {"fetched_at": float(fetched), "items": items}


def _write_cache(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"source": "itunes", "fetched_at": time.time(), "items": items}
    path.write_text(json.dumps(payload), encoding="utf-8")


def _https(value: object, suffixes: tuple[str, ...]) -> str | None:
    if not isinstance(value, str) or not value.startswith("https://"):
        return None
    host = (urllib.parse.urlparse(value).hostname or "").lower()
    if any(host == suffix or host.endswith("." + suffix) for suffix in suffixes):
        return value
    return None


def _artwork(url: str | None) -> str | None:
    if not url:
        return None
    return url.replace("100x100bb", "600x600bb")


def _year(value: object) -> int:
    text = str(value or "")
    if len(text) >= 4 and text[:4].isdigit():
        year = int(text[:4])
        if 1900 <= year <= 2100:
            return year
    return 0


def _norm(value: str) -> str:
    text = value.casefold()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    return re.sub(r"[^a-z0-9]+", "", text)


if __name__ == "__main__":
    from app.config import BACKEND_ROOT

    destination = BACKEND_ROOT / "data" / "itunes_catalog.json"
    loaded, warning = ensure_itunes_catalog(destination, allow_network=True, force=True)
    print(f"tracks={len(loaded)} warning={warning or 'none'} path={destination}")
