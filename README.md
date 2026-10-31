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
