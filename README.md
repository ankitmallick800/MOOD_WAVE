<img width="1848" height="982" alt="image" src="https://github.com/user-attachments/assets/719aeef4-33bf-4cc3-8a94-66757abfeda9" />


# MOODWAVE

MOODWAVE recommends real songs from how you listen, then plays a music preview of the song. Rankings and the short reasons under each song come from the scores in this app. A language model does not write them.

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

**Lyrics.** Fetched from [LRCLIB](https://lrclib.net) for the current song.

**Onboarding.** The first visit asks for genres, languages, artists, and what you want music for. Those answers stay until you edit or reset them. Later listening adjusts a separate inferred profile slowly.

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
uv pip install -r backend/requirements.txt -r backend/requirements-audio.txt --python .venv/bin/python
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
| `MOODWAVE_CORS_ORIGINS` | Extra browser origins, comma-separated. GitHub Pages is already allowed |
| `VITE_API_BASE` | Frontend build setting. The deployed API origin, with no trailing slash |
| `VITE_BASE` | Frontend build setting. `/MOOD_WAVE/` on GitHub Pages, `/` locally |

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

## Deploy

The API runs on Vercel. The site runs on GitHub Pages at `https://ankitmallick800.github.io/MOOD_WAVE/`.

### API on Vercel

`vercel.json` publishes the FastAPI service in `backend/`. In the Vercel import, keep the root directory at `./` and deploy that file. The project name on the import screen can stay `mood_wave`.

After the first deployment, open the production URL Vercel shows and visit `/api/health`. `catalog_tracks` should be greater than zero.

The hosted API reads `backend/.env.example` for the Apple Music catalog, the storefront, and the YouTube Music region. Leave the Vercel environment-variable form empty unless you want to override one of those. A Spotify client id and secret, if you use them, go in that form. `backend/.env` stays on your machine.

Likes, playlists, and listening on Vercel are stored under `/tmp`. A fresh instance loads the Apple catalog shipped in `backend/app/data/itunes_seed.json`. Likes, playlists, and listening from the previous instance are cleared.

### Site on GitHub Pages

1. In the GitHub repository, open Settings → Secrets and variables → Actions → Variables. Add `VITE_API_BASE` with the Vercel production origin, such as `https://your-project.vercel.app`, and no slash at the end.
2. Open Settings → Pages and set the source to GitHub Actions.
3. Push `master`. `.github/workflows/pages.yml` builds the frontend with base path `/MOOD_WAVE/`, copies the expression models, and publishes the site.

The page calls `VITE_API_BASE` for every API request. The API allows `https://ankitmallick800.github.io`. Add another host with `MOODWAVE_CORS_ORIGINS` on Vercel.

Local development stays the same. Start the API and `npm run dev`. Vite proxies `/api`, and the base path stays `/`.

## Publishing notes

Generated files stay on your machine: the SQLite database, the Apple catalog cache, the YouTube embed cache, expression model weights, and anything under `frontend/public/audio`. They are listed in `.gitignore`. The Apple seed used by Vercel is `backend/app/data/itunes_seed.json`, and that file is part of the repository.

This repository does not include a license file. Add one if you want other people to reuse the code.
