"""CSV catalog ingest.

Required columns:
track_id,title,artist,album,genres,language,year,duration_ms,tempo,energy,
danceability,acousticness,valence,speechiness,instrumentalness,loudness,
musical_key,mode,mood_tags

Numeric audio columns may be blank. Blank cells stay missing. They are not
filled with medians unless `impute_numeric` is explicitly requested, and
imputed cells are recorded on the track so they are not described as measured.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from app.data.catalog import Track, validate_track_vocab
from app.ml.vocabulary import GENRES, LANGUAGES, MOOD_TAGS

REQUIRED = (
    "track_id",
    "title",
    "artist",
    "album",
    "genres",
    "language",
    "year",
    "duration_ms",
    "tempo",
    "energy",
    "danceability",
    "acousticness",
    "valence",
    "speechiness",
    "instrumentalness",
    "loudness",
    "musical_key",
    "mode",
    "mood_tags",
)
NUMERIC = (
    "year",
    "duration_ms",
    "tempo",
    "energy",
    "danceability",
    "acousticness",
    "valence",
    "speechiness",
    "instrumentalness",
    "loudness",
    "musical_key",
    "mode",
)
AUDIO_FIELDS = (
    "tempo",
    "energy",
    "danceability",
    "acousticness",
    "valence",
    "speechiness",
    "instrumentalness",
    "loudness",
    "musical_key",
    "mode",
)


class IngestError(ValueError):
    pass


def load_catalog_csv(path: Path, impute_numeric: bool = False) -> tuple[list[Track], dict]:
    if not path.is_file():
        raise IngestError(f"Catalog file does not exist: {path.name}")
    frame = pd.read_csv(path)
    missing = [column for column in REQUIRED if column not in frame.columns]
    if missing:
        raise IngestError(f"Catalog is missing columns: {', '.join(missing)}")
    frame = frame.copy()
    before = len(frame)
    frame["track_id"] = frame["track_id"].astype(str).str.strip()
    frame["title_key"] = frame["title"].astype(str).str.strip().str.casefold()
    frame["artist_key"] = frame["artist"].astype(str).str.strip().str.casefold()
    duplicate_ids = int(frame["track_id"].duplicated().sum())
    duplicate_pairs = int(frame.duplicated(subset=["title_key", "artist_key"]).sum())
    frame = frame.drop_duplicates(subset=["track_id"], keep="first")
    frame = frame.drop_duplicates(subset=["title_key", "artist_key"], keep="first")

    for column in NUMERIC:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    imputed_columns: list[str] = []
    if impute_numeric:
        for column in AUDIO_FIELDS:
            if frame[column].isna().any() and frame[column].notna().any():
                frame[column] = frame[column].fillna(float(frame[column].median()))
                imputed_columns.append(column)

    tracks: list[Track] = []
    rejected: list[dict] = []
    for record in frame.to_dict(orient="records"):
        try:
            tracks.append(_row_to_track(record, set(imputed_columns)))
        except (IngestError, ValueError) as exc:
            rejected.append({"track_id": str(record.get("track_id")), "reason": str(exc)})

    report = {
        "rows_read": before,
        "tracks_accepted": len(tracks),
        "duplicates_removed": duplicate_ids + duplicate_pairs,
        "rejected": rejected,
        "imputed_columns": imputed_columns,
        "impute_numeric": impute_numeric,
    }
    if not tracks:
        raise IngestError("No valid tracks remained after validation.")
    return tracks, report


def _split_multi(value) -> tuple[str, ...]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ()
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ()
    parts = [part.strip().casefold() for part in text.split("|") if part.strip()]
    return tuple(parts)


def _optional(value) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if pd.isna(value):
        return None
    return float(value)


def _row_to_track(record: dict, imputed: set[str]) -> Track:
    track_id = str(record.get("track_id") or "").strip()
    title = str(record.get("title") or "").strip()
    artist = str(record.get("artist") or "").strip()
    if not track_id or not title or not artist or track_id.lower() == "nan":
        raise IngestError("track_id, title, and artist are required.")
    genres = _split_multi(record.get("genres"))
    moods = _split_multi(record.get("mood_tags"))
    language = str(record.get("language") or "").strip().lower()
    if not genres:
        raise IngestError("At least one genre is required.")
    unknown = [genre for genre in genres if genre not in GENRES]
    if unknown:
        raise IngestError(f"Unknown genres: {', '.join(unknown)}")
    if language not in LANGUAGES:
        raise IngestError(f"Unknown language: {language}")
    bad_moods = [mood for mood in moods if mood not in MOOD_TAGS]
    if bad_moods:
        raise IngestError(f"Unknown mood tags: {', '.join(bad_moods)}")
    audio_values = {name: _optional(record.get(name)) for name in AUDIO_FIELDS}
    known_audio = [name for name, value in audio_values.items() if value is not None]
    if len(known_audio) < 4:
        raise IngestError("At least four audio metadata fields are required.")
    observed = ["genres", "language", *known_audio]
    if moods:
        observed.append("mood_tags")
    source = "external_csv"
    if any(name in imputed and audio_values[name] is not None for name in AUDIO_FIELDS):
        source = "external_csv_with_imputed_fields"
    year = _optional(record.get("year"))
    duration = _optional(record.get("duration_ms"))
    if year is None or duration is None:
        raise IngestError("year and duration_ms are required.")
    track = Track(
        id=track_id,
        title=title,
        artist=artist,
        album=str(record.get("album") or "").strip(),
        genres=genres,
        language=language,
        year=int(year),
        duration_ms=int(duration),
        tempo=audio_values["tempo"],
        energy=audio_values["energy"],
        danceability=audio_values["danceability"],
        acousticness=audio_values["acousticness"],
        valence=audio_values["valence"],
        speechiness=audio_values["speechiness"],
        instrumentalness=audio_values["instrumentalness"],
        loudness=audio_values["loudness"],
        musical_key=None if audio_values["musical_key"] is None else int(audio_values["musical_key"]),
        mode=None if audio_values["mode"] is None else int(audio_values["mode"]),
        mood_tags=moods,
        feature_source=source,
        observed=tuple(observed),
    )
    validate_track_vocab(track)
    return track
