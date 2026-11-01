# API

Base URL locally is `http://127.0.0.1:8000`. A hosted page sends requests to `VITE_API_BASE`. Errors use `{ "error", "detail" }`. The live user id is `local-user`. Ids that start with `synth-` are rejected. Opening `/` returns the service name and the health path.

| Method | Path | Role |
| --- | --- | --- |
| GET | `/api/health` | Catalog size, model status, demo flag |
| GET | `/api/catalog/facets` | Genres, languages, artists, purposes |
| POST | `/api/onboarding/profile` | Save explicit preferences |
| GET | `/api/user/taste` | Explicit profile, inferred profile, confidence, stage |
| POST | `/api/user/reset` | `scope`: `inferred` or `all` |
| POST | `/api/user/reactions` | `like`, `dislike`, or `none` |
| GET | `/api/recommendations` | Ranked tracks, components, explanations |
| POST | `/api/recommendations/feedback` | Play, complete, skip, like, dislike, replay, playlist add |
| GET | `/api/tracks/search` | `q`, `genre`, `language`, `mood`, optional `user_id`. May include `warning`. On the Apple catalog, demo versions, stock titles, and disliked songs are left out |
| GET | `/api/tracks/{track_id}` | One track |
| GET | `/api/tracks/{track_id}/lyrics` | Lyrics from LRCLIB, timed when the listing has them |
| GET | `/api/tracks/{track_id}/similar` | Masked weighted cosine |
| POST | `/api/tracks/{track_id}/analyze` | Librosa, only if a file is attached |
| POST | `/api/mood/predict` | Expression distribution in, suggestion out. No image. |
| POST | `/api/mood/recommendations` | Match or shift. Camera source must set `confirmed: true` |
| GET | `/api/analytics/listening` | The live user's events only |
| GET | `/api/ml/config` | Weights and what they change |
| POST | `/api/ml/config` | Update weights |
| GET | `/api/ml/evaluation` | Last run, or a message that none has been run |
| POST | `/api/ml/evaluate` | Temporal holdout |
| GET | `/api/ml/clusters` | K-means, silhouette curve, PCA points |
| GET | `/api/library` | Catalog plus likes |
| GET | `/api/playlists` | Playlists |
| POST | `/api/playlists` | Create |
| DELETE | `/api/playlists/{id}` | Delete |
| DELETE | `/api/playlists/{id}/tracks/{track_id}` | Remove one song from a playlist |
| GET | `/api/spotify/status` | Whether Spotify app credentials are set |
| POST | `/api/spotify/playlists/generate` | Search Spotify and save a playlist |
| GET | `/api/spotify/playlists` | Saved Spotify playlists |
| DELETE | `/api/spotify/playlists/{id}` | Delete a Spotify playlist |
| GET | `/api/ytmusic/status` | YouTube Music search availability |
| POST | `/api/ytmusic/playlists/generate` | Search YouTube Music and save a playlist |
| GET | `/api/ytmusic/playlists` | Saved YouTube Music playlists |
| DELETE | `/api/ytmusic/playlists/{id}` | Delete a YouTube Music playlist |
| POST | `/api/catalog/import` | Save a YouTube song into the local catalog |
| POST | `/api/catalog/apple-match` | Find the Apple Music song for a title and artist |

`GET /api/recommendations` query parameters: `user_id`, `limit`, `strategy` (`hybrid`, `content`, `collaborative`, `collaborative_svd`, `popularity`), `mood`, `mood_mode` (`match` or `shift`), `diversify`.

A recommendation item contains `score`, `components`, `weights_used`, and `explanations`. A component is `null` when that signal is missing. Its weight is dropped and the others are renormalized. Null is not scored as zero. On the Apple Music catalog, a song with no genre or preference match keeps discovery at its configured share, so a new artist does not outrank a genre match.

Apple Music playback is the official preview. The player labels that preview with the duration reported by the audio file. Playlist search uses YouTube Music, then plays the matching Apple Music preview. If Apple has no match, play is disabled and the row links to the song. A playlist saved here stays in MOODWAVE.

`POST /api/mood/predict` body:

```json
{ "distribution": { "happy": 0.8, "neutral": 0.2 } }
```

The browser smooths frames first. The server applies a 0.55 confidence threshold and refuses to map fearful or disgusted expressions onto a listening mood.
