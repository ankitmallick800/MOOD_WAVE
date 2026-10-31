# MOODWAVE

MOODWAVE recommends real songs from how you listen, then plays an official Apple Music preview or links to the song. Rankings and the short reasons under each song come from the scores in this app. A language model does not write them.

## Features

**For You.** The first section. Songs ranked for the listener who finished onboarding. The top cards are the first four of that list and start the queue. Each row shows the title, artist, why it was chosen, and the recommendation score. Details opens the separate score parts: content, preference, collaborative, mood, and discovery. A missing part is shown as a dash. It is not treated as zero.

**Discover.** Search the catalog by title, artist, or album. Filters narrow by genre when the catalog provided one. Recordings marked as a demo version, and stock results whose title is only a genre search phrase, are left out. Songs you have disliked are left out too. The cluster chart appears when enough songs have real audio features. With Apple Music metadata, those features are unknown, so the page says so.

**Mood Studio.** Pick a listening mood yourself, or start the camera and confirm the expression it reads. Match stays with that mood. Shift aims at a different one. The camera stays off until you start it. Frames stay in the browser. Nothing is uploaded or saved. If a song has no mood tags and no audio features, the ranker does not pretend it matched the mood.

**Playlist.** Search YouTube Music and build a list inside MOODWAVE. Play uses the matching Apple Music preview in the same player as the rest of the app. If Apple has no match, play stays off and the row links to the song. Saving a song here does not add it to a YouTube Music or Spotify account.

**My Library.** Songs you have liked or saved to a playlist in this app. Disliking a song removes it from that list.

**Liked Songs.** Songs you marked with the heart.

**My Taste.** The preferences from onboarding, plus what plays, likes, skips, and playlist adds have nudged since then.

**Model Lab.** Precision, recall, NDCG, hit rate, coverage, diversity, and novelty from a time-based holdout of listening saved in this app. When there is not enough listening to measure, the page says so.

**Settings.** Catalog size, which models are fit, and a reset for the profile, events, and queue.

**Player.** The bar at the bottom plays the current song, seeks when the source allows it, and keeps shuffle, repeat, volume, like, and skip. The queue on the right shows artwork, the source, and the lyrics.

**Lyrics.** Fetched from [LRCLIB](https://lrclib.net) for the current song. The full text sits in a scrollable box. Lines are not highlighted in time with the audio, because an Apple preview can begin at any point in the song.

**Onboarding.** The first visit asks for genres, languages, artists, and what you want music for. Those answers stay until you edit or reset them. Later listening adjusts a separate inferred profile slowly. One click does not replace what you entered.

## How a song gets its score

The ranker mixes the parts it actually has:

- Content similarity, from genres the catalog provided. Audio numbers are used only when a real feature source supplied them.
- Your preferences, from onboarding and from listening saved here.
- Collaborative signals, once enough listening exists for more than one listener. Until then this part is left out.
- Mood, when you set one and the song has mood information.
- A discovery bonus for artists you have not played.

Missing parts are dropped and the remaining weights are rescaled. A song with no shared genre does not outrank one that matches your genres just because the artist is new. The number at the end of a row is that combined score, from 0 to 1. The sentence under the title uses the same parts. It will not claim a tempo or an energy level the catalog did not provide.

## Playback

1. An official full track, when a source provides one this app is allowed to play.
2. The official Apple Music preview, labeled as a preview.
3. Play disabled, with a link to the song.

Playlist rows are found with YouTube Music and played from Apple Music. The YouTube player is not used on that page.

Songs are not downloaded, proxied, or scraped. A preview is not presented as the full song.

## Stack

| Part | Choice |
| --- | --- |
| Interface | React, TypeScript, Vite, Tailwind |
| API | FastAPI |
| Storage | SQLite for the profile, events, and playlists |
| Ranking | NumPy and scikit-learn. Masked cosine, item-item collaborative filtering, TruncatedSVD |
| Catalog | Apple Music Search API for metadata and preview URLs |
| Playlists | YouTube Music search |
| Lyrics | LRCLIB |
| Expressions | face-api.js in the browser |

## Requirements

- Python 3.12
- Node.js 20 or newer
- A network connection the first time the catalog is built, and whenever lyrics or YouTube search run

No API key is required for Apple Music search, YouTube Music search, or LRCLIB.

Spotify playlist search is optional. It needs a Spotify application client id and secret in `backend/.env`. Spotify may still refuse search unless the owner of that application has Premium. The playlist page uses YouTube Music either way.

## Setup

From the repository root:

```bash
uv venv --python 3.12 .venv
uv pip install -r backend/requirements.txt --python .venv/bin/python
cd frontend && npm install && node scripts/copy-models.mjs
```

`copy-models.mjs` copies the expression models into `frontend/public/models`.

Start the API:

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Start the interface, in a second terminal:

```bash
cd frontend && npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to port 8000.

The first launch requests a catalog from Apple Music and saves it under `backend/data`. Later launches reuse that file until it is a week old. If Apple is unreachable and a saved catalog exists, the app keeps serving the saved songs.

## Configuration

Copy `backend/.env.example` to `backend/.env` and edit it. The example file has no secrets. `backend/.env` is gitignored.

| Variable | Purpose |
| --- | --- |
| `MOODWAVE_DATA_DIR` | Where the catalog cache and database live. Default `backend/data` |
| `MOODWAVE_DB_PATH` | SQLite file. Default `backend/data/moodwave.db` |
| `MOODWAVE_HOST` | API host. Default `127.0.0.1` |
| `MOODWAVE_PORT` | API port. Default `8000` |
| `MOODWAVE_ITUNES_COUNTRY` | Apple Music storefront. Default `US` |
| `MOODWAVE_YTMUSIC_LOCATION` | YouTube Music region. Default `IN` |
| `MOODWAVE_YTMUSIC_EMBED_CHECK` | Ask YouTube oEmbed before embedding. Default on |
| `MOODWAVE_CATALOG_CSV` | Optional CSV that replaces the Apple Music catalog |
| `MOODWAVE_SPOTIFY_CLIENT_ID` | Optional. Your own Spotify application id |
| `MOODWAVE_SPOTIFY_CLIENT_SECRET` | Optional. Your own Spotify application secret |

Put Spotify credentials only in `backend/.env`.

## Layout

| Path | What it holds |
| --- | --- |
| `frontend/` | The player, pages, and browser expression code |
| `backend/app/api/` | HTTP routes |
| `backend/app/ml/` | Features, ranking, profiles, evaluation |
| `backend/app/providers/` | Apple Music, YouTube, and LRCLIB adapters |
| `backend/app/data/` | Catalog loading and the database |
| `backend/tests/` | Ranking, catalog, lyrics, and API tests |
| `docs/API.md` | Route reference |
| `docs/LIMITATIONS.md` | What the sources do not provide |

## Checks

```bash
cd backend && ../.venv/bin/python -m pytest
cd frontend && npx tsc --noEmit
```

Interactive API schema, with the server running: http://127.0.0.1:8000/docs

Written reference: [docs/API.md](docs/API.md). Source limits: [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Publishing notes

Generated files stay on your machine: the SQLite database, the Apple catalog cache, the YouTube embed cache, expression model weights, and anything under `frontend/public/audio`. They are listed in `.gitignore`.

This repository does not include a license file. Add one if you want other people to reuse the code.
