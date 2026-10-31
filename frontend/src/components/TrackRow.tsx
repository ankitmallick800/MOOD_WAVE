import { Heart, ListPlus, Pause, Play, ThumbsDown } from "lucide-react";

import { Cover } from "../lib/cover";
import { canPlay, lengthLabel } from "../lib/playback";
import { usePlayer } from "../lib/store";
import type { ScoreComponents, Track } from "../types";

export function TrackRow({
  track,
  queue,
  explanation,
  reasons,
  score,
  components,
  index,
  onDislike,
}: {
  track: Track;
  queue?: Track[];
  explanation?: string;
  reasons?: Record<string, string[]>;
  score?: number;
  components?: ScoreComponents;
  index?: number;
  onDislike?: (track: Track) => void;
}) {
  const currentId = usePlayer((state) => state.queue[state.index]?.id);
  const playing = usePlayer((state) => state.playing);
  const liked = usePlayer((state) => state.liked.includes(track.id));
  const disliked = usePlayer((state) => state.disliked.includes(track.id));
  const playTrack = usePlayer((state) => state.playTrack);
  const enqueue = usePlayer((state) => state.enqueue);
  const toggle = usePlayer((state) => state.toggle);
  const playable = canPlay(track);
  const toggleLike = usePlayer((state) => state.toggleLike);
  const toggleDislike = usePlayer((state) => state.toggleDislike);
  const active = currentId === track.id;

  return (
    <div className={`group grid grid-cols-[auto_1fr_auto] items-center gap-4 rounded-xl px-3 py-2.5 transition ${active ? "bg-white/[0.05]" : "hover:bg-white/[0.035]"}`}>
      <button
        className="relative disabled:cursor-not-allowed"
        disabled={!playable}
        title={playable ? undefined : "No playable audio for this song"}
        onClick={() => (active ? void toggle() : void playTrack(track, queue, reasons ?? (explanation ? [explanation] : undefined)))}
        aria-label={playable ? (active && playing ? `Pause ${track.title}` : `Play ${track.title}`) : `${track.title} cannot be played here`}
      >
        <Cover id={track.id} size={52} src={track.artwork_url} />
        <span className="absolute inset-0 grid place-items-center rounded-md bg-black/35 opacity-0 transition group-hover:opacity-100">
          {active && playing ? <Pause size={16} /> : <Play size={16} fill="currentColor" />}
        </span>
      </button>
      <div className="min-w-0">
        <div className="flex items-baseline gap-3">
          {index !== undefined && <span className="w-5 text-xs text-mist">{index + 1}</span>}
          <div className="min-w-0">
            <div className="truncate text-[15px] text-foam">{track.title}</div>
            <div className="truncate text-sm text-mist">{track.artist}</div>
          </div>
        </div>
        {explanation && <p className="mt-1 line-clamp-2 text-[13px] leading-5 text-sand/90">{explanation}</p>}
        {components && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {Object.entries(components).map(([name, value]) => (
              <span key={name} className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-mist">
                {name} {value === null ? "—" : value.toFixed(2)}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="flex items-center gap-1.5">
        {score !== undefined && (
          <span className="w-10 text-right text-xs text-sand" title="Recommendation score">
            {score.toFixed(2)}
          </span>
        )}
        <span className="w-14 text-right text-xs text-mist">{lengthLabel(track)}</span>
        <button className="rounded-full p-2 text-mist hover:text-foam" onClick={() => enqueue(track)} aria-label={`Add ${track.title} to the queue`}>
          <ListPlus size={15} />
        </button>
        <button className={`rounded-full p-2 ${liked ? "text-sand" : "text-mist hover:text-foam"}`} onClick={() => void toggleLike(track)} aria-label="Like">
          <Heart size={16} fill={liked ? "currentColor" : "none"} />
        </button>
        <button
          className={`rounded-full p-2 ${disliked ? "text-rose-300" : "text-mist hover:text-foam"}`}
          onClick={() => void (onDislike ? onDislike(track) : toggleDislike(track))}
          aria-label="Dislike"
        >
          <ThumbsDown size={15} />
        </button>
      </div>
    </div>
  );
}
