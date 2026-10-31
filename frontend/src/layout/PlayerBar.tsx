import { Heart, Pause, Play, Repeat, Repeat1, Shuffle, SkipBack, SkipForward, Volume2, VolumeX } from "lucide-react";

import { Cover } from "../lib/cover";
import { formatTime } from "../lib/format";
import { canPlay, playbackCaption, sourceLabel } from "../lib/playback";
import { usePlayer } from "../lib/store";

export function PlayerBar() {
  const queue = usePlayer((state) => state.queue);
  const index = usePlayer((state) => state.index);
  const playing = usePlayer((state) => state.playing);
  const position = usePlayer((state) => state.positionMs);
  const volume = usePlayer((state) => state.volume);
  const shuffle = usePlayer((state) => state.shuffle);
  const repeat = usePlayer((state) => state.repeat);
  const liked = usePlayer((state) => state.liked);
  const track = queue[index];
  const toggle = usePlayer((state) => state.toggle);
  const next = usePlayer((state) => state.next);
  const prev = usePlayer((state) => state.prev);
  const seek = usePlayer((state) => state.seek);
  const setVolume = usePlayer((state) => state.setVolume);
  const toggleShuffle = usePlayer((state) => state.toggleShuffle);
  const cycleRepeat = usePlayer((state) => state.cycleRepeat);
  const toggleLike = usePlayer((state) => state.toggleLike);
  const playbackNote = usePlayer((state) => state.playbackNote);
  const playable = track ? canPlay(track) : false;
  const seekable = Boolean(track && track.preview !== "embed" && track.preview !== "unavailable" && (track.duration_ms || 0) > 0);

  return (
    <footer className="grid h-[92px] grid-cols-[minmax(180px,1fr)_minmax(280px,1.4fr)_minmax(160px,1fr)] items-center gap-4 border-t border-white/8 bg-[#0c0c0e]/95 px-4 backdrop-blur">
      <div className="flex min-w-0 items-center gap-3">
        {track ? (
          <>
            <Cover id={track.id} size={58} src={track.artwork_url} />
            <div className="min-w-0">
              <div className="truncate text-sm text-foam">{track.title}</div>
              <div className="truncate text-xs text-mist">
                {track.artist}
                {playbackCaption(track) ? ` · ${playbackCaption(track)}` : ""}
                {` · ${sourceLabel(track)}`}
              </div>
            </div>
            {track.external_url && (
              <a className="text-[11px] text-sand" href={track.external_url} target="_blank" rel="noreferrer">
                Open
              </a>
            )}
            <button className={`ml-1 ${liked.includes(track.id) ? "text-sand" : "text-mist"}`} onClick={() => void toggleLike(track)} aria-label="Like current track">
              <Heart size={16} fill={liked.includes(track.id) ? "currentColor" : "none"} />
            </button>
          </>
        ) : (
          <div className="text-sm text-mist">Nothing queued</div>
        )}
      </div>
      <div className="flex flex-col items-center gap-1.5">
        <div className="flex items-center gap-4">
          <button className={shuffle ? "text-sand" : "text-mist hover:text-foam"} onClick={toggleShuffle} aria-label="Shuffle">
            <Shuffle size={16} />
          </button>
          <button className="text-foam" onClick={() => void prev()} aria-label="Previous">
            <SkipBack size={18} fill="currentColor" />
          </button>
          <button
            className="grid h-10 w-10 place-items-center rounded-full bg-foam text-ink disabled:opacity-40"
            onClick={() => void toggle()}
            disabled={Boolean(track) && !playable}
            title={track && !playable ? playbackNote || "No playable audio for this song" : undefined}
            aria-label={playing ? "Pause" : "Play"}
          >
            {playing ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" className="ml-0.5" />}
          </button>
          <button className="text-foam" onClick={() => void next("skip")} aria-label="Next">
            <SkipForward size={18} fill="currentColor" />
          </button>
          <button className={repeat === "off" ? "text-mist hover:text-foam" : "text-sand"} onClick={cycleRepeat} aria-label="Repeat">
            {repeat === "one" ? <Repeat1 size={16} /> : <Repeat size={16} />}
          </button>
        </div>
        <div className="flex w-full max-w-xl items-center gap-2">
          <span className="w-10 text-right text-[11px] text-mist">{formatTime(position)}</span>
          <input
            type="range"
            min={0}
            max={track?.duration_ms ?? 0}
            value={Math.min(position, track?.duration_ms ?? 0)}
            onChange={(event) => void seek(Number(event.target.value))}
            aria-label="Seek"
            disabled={!seekable}
            className="w-full disabled:opacity-40"
          />
          <span className="w-10 text-[11px] text-mist">{formatTime(track?.duration_ms ?? 0)}</span>
        </div>
      </div>
      <div className="flex items-center justify-end gap-2">
        <button className="text-mist" onClick={() => setVolume(volume === 0 ? 0.8 : 0)} aria-label="Mute">
          {volume === 0 ? <VolumeX size={16} /> : <Volume2 size={16} />}
        </button>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={volume}
          onChange={(event) => setVolume(Number(event.target.value))}
          aria-label="Volume"
          className="w-24"
        />
      </div>
    </footer>
  );
}
