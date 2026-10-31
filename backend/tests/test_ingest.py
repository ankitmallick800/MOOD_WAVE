from pathlib import Path

import pytest

from app.data.ingest import IngestError, load_catalog_csv

HEADER = (
    "track_id,title,artist,album,genres,language,year,duration_ms,tempo,energy,"
    "danceability,acousticness,valence,speechiness,instrumentalness,loudness,"
    "musical_key,mode,mood_tags\n"
)


def test_ingest_rejects_unknown_genre_and_drops_duplicates(tmp_path: Path):
    path = tmp_path / "catalog.csv"
    path.write_text(
        HEADER
        + "t1,Song,Artist,Album,indie|folk,en,2020,180000,100,0.4,0.4,0.6,0.5,0.05,0.2,-12,2,1,calm\n"
        + "t1,Song,Artist,Album,indie|folk,en,2020,180000,100,0.4,0.4,0.6,0.5,0.05,0.2,-12,2,1,calm\n"
        + "t2,Other,Artist,Album,not-a-genre,en,2020,180000,100,0.4,0.4,0.6,0.5,0.05,0.2,-12,2,1,calm\n"
        + "t3,Blank,Artist,Album,jazz,en,2020,180000,,0.4,0.4,0.6,0.5,0.05,0.2,-12,2,1,nocturnal\n",
        encoding="utf-8",
    )
    tracks, report = load_catalog_csv(path, impute_numeric=False)
    ids = [track.id for track in tracks]
    assert ids == ["t1", "t3"]
    assert report["tracks_accepted"] == 2
    assert any(item["track_id"] == "t2" for item in report["rejected"])
    blank = next(track for track in tracks if track.id == "t3")
    assert blank.tempo is None
    assert "tempo" not in blank.observed
    assert blank.feature_source == "external_csv"


def test_ingest_requires_columns(tmp_path: Path):
    path = tmp_path / "bad.csv"
    path.write_text("track_id,title\n1,Song\n", encoding="utf-8")
    with pytest.raises(IngestError):
        load_catalog_csv(path)
