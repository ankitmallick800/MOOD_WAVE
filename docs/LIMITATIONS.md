# Limits

These are properties of the sources MOODWAVE uses.

- Apple Music search supplies the title, artist, album, artwork, a genre label, the song length, a preview URL, and a link to the song. It does not supply tempo, energy, danceability, valence, mood, or language. Those fields stay empty. The ranker does not fill them in.
- A genre enters the similarity vector only when Apple's label matches a genre this app already knows, such as Pop or Indie Pop. Other labels are kept as text.
- Catalog playback is the official preview when Apple includes one. The player labels it as a preview. If there is no preview, play is disabled and the row links to the song.
- The playlist page searches YouTube Music for the song list. Playback looks up the same title and artist on Apple Music and uses that official preview. If Apple has no match, play stays off and the row links out. The app does not download or proxy the audio, and it does not play the YouTube player on that page.
- A playlist saved in MOODWAVE stays in this app's database. It is not added to a YouTube Music or Spotify account.
- If a YouTube result has the same title and artist as a catalog song, the catalog id is reused.
- Collaborative filtering stays off until listening saved in this app is enough to score. Model Lab says so instead of printing empty metrics.
- Listening events live in SQLite and are replayed to rebuild the inferred profile. A click does not retrain the factorization.
- Facial expressions are an optional listening signal. Fearful and disgusted are not mapped to a playlist mood. Low confidence produces no suggestion. Images are not stored or uploaded. Mood match is withheld when a song has no mood tags and no audio features.
- Lyrics come from LRCLIB when a title and artist match. They are shown in full and can be scrolled. They are not aligned to an Apple preview, because that preview can start anywhere in the song.
- Librosa runs only when an audio file for that track is placed in the server audio directory. The extractor does not fill danceability or valence. The hosted API on Vercel does not install librosa.
- On Vercel, the profile, likes, playlists, and listening events live in temporary disk. They reset when Vercel starts a fresh instance. The Apple song list is loaded again from the catalog file shipped in the repository.
