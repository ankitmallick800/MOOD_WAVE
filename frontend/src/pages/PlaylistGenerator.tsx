import { useEffect, useRef, useState } from "react";

import { ApiError, api } from "../lib/api";
import { canPlay } from "../lib/playback";
import { formatTime } from "../lib/format";
import { usePlayer } from "../lib/store";
import type { Playlist, Track, YtMusicPlaylist, YtMusicTrack } from "../types";

const MOODS = ["calm", "happy", "sad", "energetic", "focused", "romantic", "nocturnal", "hopeful"] as const;

export function PlaylistGenerator() {
  const playTrack = usePlayer((state) => state.playTrack);
  const enqueue = usePlayer((state) => state.enqueue);
  const setQueue = usePlayer((state) => state.setQueue);
  const refreshProfile = usePlayer((state) => state.refreshProfile);
  const currentId = usePlayer((state) => state.queue[state.index]?.id);
  const [location, setLocation] = useState("IN");
  const [name, setName] = useState("Evening");
  const [prompt, setPrompt] = useState("");
  const [mood, setMood] = useState<string | null>("calm");
  const [useProfile, setUseProfile] = useState(true);
  const [playlists, setPlaylists] = useState<YtMusicPlaylist[]>([]);
  const [libraryLists, setLibraryLists] = useState<Playlist[]>([]);
  const [active, setActive] = useState<YtMusicPlaylist | null>(null);
  const [matches, setMatches] = useState<Record<string, Track | null>>({});
  const [busyId, setBusyId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const matchesRef = useRef(matches);
  matchesRef.current = matches;

  async function refresh() {
    const [status, saved, library] = await Promise.all([api.ytmusicStatus(), api.ytmusicPlaylists(), api.playlists()]);
    setLocation(status.location);
    setPlaylists(saved.playlists);
    setLibraryLists(library.playlists);
    return saved.playlists;
  }

  useEffect(() => {
    void refresh().catch((reason: Error) => setError(reason.message));
  }, []);

  async function generate() {
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const created = await api.generateYtMusicPlaylist({
        name: name.trim(),
        prompt: prompt.trim(),
        mood,
        limit: 12,
        use_profile: useProfile,
      });
      const saved = await refresh();
      const match = saved.find((playlist) => playlist.id === created.id);
      setActive(match ? { ...match, notes: created.notes, queries: created.queries } : created);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "YouTube Music search failed.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    await api.deleteYtMusicPlaylist(id);
    if (active?.id === id) setActive(null);
    await refresh();
  }

  async function appleTrack(track: YtMusicTrack): Promise<Track | null> {
    if (Object.prototype.hasOwnProperty.call(matchesRef.current, track.video_id)) {
      return matchesRef.current[track.video_id];
    }
    try {
      const match = await api.matchApple({ title: track.title, artist: track.artist });
      const next = { ...matchesRef.current, [track.video_id]: match };
      matchesRef.current = next;
      setMatches(next);
      return match;
    } catch (reason) {
      if (reason instanceof ApiError && (reason.status === 404 || reason.status === 502)) {
        const next = { ...matchesRef.current, [track.video_id]: null };
        matchesRef.current = next;
        setMatches(next);
        return null;
      }
      throw reason;
    }
  }

  async function playableQueue(rows: YtMusicTrack[], first: Track, firstVideoId: string): Promise<Track[]> {
    const queue: Track[] = [];
    for (const row of rows) {
      const match = row.video_id === firstVideoId ? first : await appleTrack(row);
      if (match && canPlay(match) && !queue.some((item) => item.id === match.id)) queue.push(match);
    }
    return queue.length ? queue : [first];
  }

  async function playRow(track: YtMusicTrack, rows: YtMusicTrack[]) {
    setError(null);
    setBusyId(track.video_id);
    try {
      const match = await appleTrack(track);
      if (!match || !canPlay(match)) {
        setNotice(null);
        setError(`Apple Music has no preview for “${track.title}”. Open the song instead.`);
        return;
      }
      await playTrack(match, [match]);
      void refreshProfile();
      const queue = await playableQueue(rows, match, track.video_id);
      if (usePlayer.getState().queue[usePlayer.getState().index]?.id === match.id) setQueue(queue);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not play that song.");
    } finally {
      setBusyId(null);
    }
  }

  async function queueTrack(track: YtMusicTrack) {
    setError(null);
    setBusyId(track.video_id);
    try {
      const match = await appleTrack(track);
      if (!match || !canPlay(match)) {
        setError(`Apple Music has no preview for “${track.title}”. It was not added to the queue.`);
        return;
      }
      await refreshProfile();
      enqueue(match);
      setNotice(`“${match.title}” is in the queue. It plays from Apple Music.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not queue that song.");
    } finally {
      setBusyId(null);
    }
  }

  async function saveTrack(playlistId: number, track: YtMusicTrack) {
    setError(null);
    setBusyId(track.video_id);
    try {
      const match = await appleTrack(track);
      if (!match) {
        setError(`Apple Music has no match for “${track.title}”, so it was not saved.`);
        return;
      }
      await api.feedback({
        track_id: match.id,
        event_type: "playlist_add",
        playlist_id: playlistId,
        listen_ms: 0,
        duration_ms: match.song_duration_ms || match.duration_ms,
      });
      await refreshProfile();
      const playlist = libraryLists.find((item) => item.id === playlistId);
      setNotice(`Saved “${match.title}” to ${playlist?.name || "your playlist"} in MOODWAVE.`);
      await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save that song.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.22em] text-mist">YouTube Music</div>
      <h1 className="font-display mt-2 text-5xl text-foam">Playlist generator</h1>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-mist">
        Search YouTube Music, then play the matching Apple Music preview in the player below. If Apple has no match, play stays off and the row keeps a link. Nothing is downloaded. A list saved here is not added to a YouTube Music account. Catalog region is {location}.
      </p>
      {error && <p className="mt-4 text-sm text-rose-300">{error}</p>}
      {notice && <p className="mt-4 text-sm text-sand">{notice}</p>}
      <div className="mt-8 grid gap-3 md:grid-cols-[1.2fr_1fr_auto]">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Playlist name"
          aria-label="Playlist name"
          className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-foam outline-none"
        />
        <input
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Artist, genre, or scene"
          aria-label="Playlist description"
          className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-foam outline-none"
        />
        <button
          className="rounded-full bg-foam px-5 py-3 text-sm text-ink disabled:opacity-40"
          disabled={busy || !name.trim()}
          onClick={() => void generate()}
        >
          {busy ? "Searching" : "Create playlist"}
        </button>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {MOODS.map((item) => (
          <button
            key={item}
            className={`rounded-full px-3 py-1 text-xs ${mood === item ? "bg-white/10 text-foam" : "text-mist"}`}
            onClick={() => setMood(mood === item ? null : item)}
          >
            {item}
          </button>
        ))}
        <label className="ml-2 flex items-center gap-2 text-xs text-mist">
          <input type="checkbox" checked={useProfile} onChange={(event) => setUseProfile(event.target.checked)} />
          Include my genres
        </label>
      </div>
      {playlists.length > 0 && (
        <div className="mt-8 flex flex-wrap gap-2">
          {playlists.map((playlist) => (
            <button
              key={playlist.id}
              className={`rounded-full px-3 py-1 text-sm ${active?.id === playlist.id ? "bg-white/10 text-foam" : "text-mist"}`}
              onClick={() => setActive(playlist)}
            >
              {playlist.name}
            </button>
          ))}
        </div>
      )}
      {active && (
        <section className="mt-8">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg text-foam">{active.name}</h2>
              <p className="text-xs text-mist">{active.prompt || "Mood and genres only"}</p>
            </div>
            <button className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-mist" onClick={() => void remove(active.id)}>
              Delete
            </button>
          </div>
          {active.notes?.map((note) => (
            <p key={note} className="mt-3 max-w-2xl text-xs leading-5 text-mist">
              {note}
            </p>
          ))}
          <div className="mt-4">
            {active.tracks.map((track, index) => {
              const match = Object.prototype.hasOwnProperty.call(matches, track.video_id) ? matches[track.video_id] : undefined;
              const playable = Boolean(match && canPlay(match));
              const blocked = match === null || (match !== undefined && !playable);
              const activeRow = Boolean(match && currentId === match.id);
              const link = match?.external_url || track.watch_url;
              return (
                <div
                  key={track.video_id}
                  className={`grid grid-cols-[auto_1fr_auto] items-center gap-4 rounded-xl px-3 py-2.5 ${activeRow ? "bg-white/[0.05]" : "hover:bg-white/[0.035]"}`}
                >
                  <button
                    className="grid h-12 w-12 place-items-center overflow-hidden rounded-md bg-white/5 text-xs text-mist disabled:opacity-40"
                    aria-label={blocked ? `${track.title} has no Apple preview` : `Play ${track.title}`}
                    disabled={blocked || busyId === track.video_id}
                    onClick={() => void playRow(track, active.tracks)}
                  >
                    {track.image ? <img src={track.image} alt="" className="h-full w-full object-cover" /> : index + 1}
                  </button>
                  <div className="min-w-0">
                    <div className="truncate text-[15px] text-foam">{match?.title || track.title}</div>
                    <div className="truncate text-sm text-mist">
                      {match?.artist || track.artist}
                      <span className="px-1.5 text-white/20">/</span>
                      {busyId === track.video_id ? "Finding Apple Music" : blocked ? "No Apple preview" : match ? "Apple preview" : "Apple Music"}
                      <span className="px-1.5 text-white/20">/</span>
                      {formatTime(match?.song_duration_ms || track.duration_ms)}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <button className="text-xs text-mist hover:text-foam" onClick={() => void queueTrack(track)}>
                      Queue
                    </button>
                    {libraryLists.length > 0 ? (
                      <select
                        aria-label={`Save ${track.title} to a MOODWAVE playlist`}
                        className="max-w-36 rounded-full border border-white/10 bg-ink px-2 py-1 text-xs text-mist"
                        value=""
                        onChange={(event) => {
                          const playlistId = Number(event.target.value);
                          if (playlistId) void saveTrack(playlistId, track);
                        }}
                      >
                        <option value="">Save</option>
                        {libraryLists.map((playlist) => (
                          <option key={playlist.id} value={playlist.id}>
                            {playlist.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="text-[11px] text-mist">Make a playlist in My Library</span>
                    )}
                    <a className="text-xs text-sand" href={link} target="_blank" rel="noreferrer">
                      Open
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
