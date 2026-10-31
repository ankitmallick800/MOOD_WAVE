import { useEffect, useState } from "react";

import { TrackRow } from "../components/TrackRow";
import { api } from "../lib/api";
import { isLibraryNoise } from "../lib/catalog";
import { usePlayer } from "../lib/store";
import type { Playlist, Track } from "../types";

export function Library() {
  const catalog = usePlayer((state) => state.catalog);
  const liked = usePlayer((state) => state.liked);
  const disliked = usePlayer((state) => state.disliked);
  const toggleDislike = usePlayer((state) => state.toggleDislike);
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [name, setName] = useState("");
  const [active, setActive] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [removed, setRemoved] = useState<string[]>([]);

  async function refresh() {
    const response = await api.playlists();
    setPlaylists(response.playlists);
  }

  useEffect(() => {
    void refresh().catch((reason: Error) => setError(reason.message));
  }, []);

  async function create() {
    if (!name.trim()) return;
    await api.createPlaylist(name.trim());
    setName("");
    await refresh();
  }

  async function dislike(track: Track) {
    setRemoved((current) => (current.includes(track.id) ? current : [...current, track.id]));
    setError(null);
    try {
      if (!disliked.includes(track.id)) await toggleDislike(track);
      const hits = playlists.filter((playlist) => playlist.tracks.some((item) => item.id === track.id));
      await Promise.all(hits.map((playlist) => api.removePlaylistTrack(playlist.id, track.id)));
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not remove that song.");
    }
  }

  const selected = playlists.find((playlist) => playlist.id === active);
  const likedTracks = catalog.filter((track) => liked.includes(track.id));
  const source = selected ? selected.tracks : [...playlists.flatMap((playlist) => playlist.tracks), ...likedTracks];
  const seen = new Set<string>();
  const tracks = source.filter((track) => {
    if (seen.has(track.id) || removed.includes(track.id) || disliked.includes(track.id) || isLibraryNoise(track)) return false;
    seen.add(track.id);
    return true;
  });

  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.22em] text-mist">Library</div>
      <h1 className="font-display mt-2 text-5xl">Saved in MOODWAVE.</h1>
      <p className="mt-3 max-w-2xl text-sm text-mist">Songs you like or save to a playlist show up here. Disliking a song removes it from this list.</p>
      <div className="mt-6 flex gap-2">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="New playlist"
          className="rounded-full border border-white/10 bg-transparent px-4 py-2 text-sm outline-none"
        />
        <button className="rounded-full bg-foam px-4 py-2 text-sm text-ink" onClick={() => void create()}>
          Create
        </button>
      </div>
      {error && <p className="mt-3 text-sm text-rose-300">{error}</p>}
      <div className="mt-4 flex flex-wrap gap-2">
        <button className={`rounded-full px-3 py-1 text-sm ${active === null ? "bg-white/10" : "text-mist"}`} onClick={() => setActive(null)}>
          All tracks
        </button>
        {playlists.map((playlist) => (
          <button
            key={playlist.id}
            className={`rounded-full px-3 py-1 text-sm ${active === playlist.id ? "bg-white/10" : "text-mist"}`}
            onClick={() => setActive(playlist.id)}
          >
            {playlist.name}
          </button>
        ))}
      </div>
      <div className="mt-4">
        {tracks.length === 0 && <p className="text-sm text-mist">Nothing saved here yet.</p>}
        {tracks.map((track) => (
          <div key={track.id}>
            <TrackRow track={track} queue={tracks} onDislike={(item) => void dislike(item)} />
            {playlists.length > 0 && !selected && (
              <div className="mb-2 ml-16 flex flex-wrap gap-2">
                {playlists
                  .filter((playlist) => !playlist.tracks.some((item) => item.id === track.id))
                  .map((playlist) => (
                    <button
                      key={playlist.id}
                      className="text-[11px] text-mist hover:text-sand"
                      onClick={() =>
                        void api
                          .feedback({
                            track_id: track.id,
                            event_type: "playlist_add",
                            playlist_id: playlist.id,
                            listen_ms: 0,
                            duration_ms: track.song_duration_ms || track.duration_ms,
                          })
                          .then(() => refresh())
                      }
                    >
                      Add to {playlist.name}
                    </button>
                  ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
