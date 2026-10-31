# Dataset

## Demo catalog

`backend/app/data/demo_catalog.py` is the source of the runnable catalog. On startup the server writes `backend/data/demo_catalog.json` so you can inspect the rows. The synthetic events are regenerated from seed 42 and written to `backend/data/synthetic_interactions.json`.

Both files are labeled. Do not cite them as listener research.

## CSV catalog

Required header:

```text
track_id,title,artist,album,genres,language,year,duration_ms,tempo,energy,danceability,acousticness,valence,speechiness,instrumentalness,loudness,musical_key,mode,mood_tags
```

- Genres and mood tags are pipe-separated, for example `indie|folk`.
- Languages must be one of `en`, `bn`, `hi`, `es`, `ko`, `ja`, `fr`, `pt`.
- Genres and mood tags must use the vocabularies in `backend/app/ml/vocabulary.py`.
- Blank audio cells stay missing. Similarity masks those coordinates out. They are not treated as zero.
- Pass `impute_numeric=True` only from the Python ingest API if you explicitly want median fill. Imputed tracks are marked `external_csv_with_imputed_fields`. The default server path does not impute.
- Duplicate `track_id` values and duplicate title-artist pairs are dropped. The report lists rejected rows.

Point the server at a file:

```bash
export MOODWAVE_CATALOG_CSV=/absolute/path/catalog.csv
```

Without an interaction file, collaborative filtering stays off and recommendations use content, preference, mood, and discovery. That is the cold-start path, and the health check says so.

## Interaction file

JSON object:

```json
{
  "origin": "external",
  "events": [
    {
      "user_id": "u-1",
      "track_id": "track-1",
      "event_type": "like",
      "ts": 1700000000,
      "listen_ratio": 0.95
    }
  ]
}
```

`event_type` is one of `play`, `complete`, `skip`, `like`, `dislike`, `playlist_add`, `replay`.

Set `origin` to `synthetic` only when the file was generated, so evaluation keeps the synthetic warning. Any other origin is treated as an external file. The metrics still describe that file under the temporal-holdout protocol. They are not a universal score for the ranker.

```bash
export MOODWAVE_INTERACTIONS_JSON=/absolute/path/interactions.json
```

The live listener id is `local-user`. Do not put that id in the training file if you want the holdout to stay separate from the person using the app. User ids starting with `synth-` are rejected by the live API so the demo matrix cannot be overwritten from the browser.

## Audio files

To analyze one track:

```text
backend/data/audio/{track_id}.wav
```

`POST /api/tracks/{track_id}/analyze` reads only that directory. It does not accept a path. Features are written under `backend/data/audio_features/`.

## Million Song Dataset

A compatible extract is a CSV in the schema above. MSD does not include danceability or valence. Leave those cells blank rather than filling them. Mood tags are optional. The ranker will mask what is absent.

This project does not download MSD. The file is large and the license is yours to check before you use it.
