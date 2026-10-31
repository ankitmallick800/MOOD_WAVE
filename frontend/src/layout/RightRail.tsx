import { RefreshCw, Trash2, X } from "lucide-react";
import { useState } from "react";

import { Lyrics } from "../components/Lyrics";
import { api } from "../lib/api";
import { Cover } from "../lib/cover";
import { playbackCaption, sourceLabel } from "../lib/playback";
import { usePlayer } from "../lib/store";

export function RightRail({ onClose }: { onClose?: () => void }) {
  const queue = usePlayer((state) => state.queue);
  const index = usePlayer((state) => state.index);
  const reasons = usePlayer((state) => state.reasons);
  const mood = usePlayer((state) => state.mood);
  const moodMode = usePlayer((state) => state.moodMode);
  const track = queue[index];
  const playTrack = usePlayer((state) => state.playTrack);
  const removeAt = usePlayer((state) => state.removeAt);
  const move = usePlayer((state) => state.move);
  const clearQueue = usePlayer((state) => state.clearQueue);
  const playing = usePlayer((state) => state.playing);
  const replaceQueue = usePlayer((state) => state.replaceQueue);
  const [drag, setDrag] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  async function regenerate() {
    setBusy(true);
    try {
      const response = await api.recommendations({
        limit: 20,
        strategy: "hybrid",
        mood: mood ?? undefined,
        mood_mode: mood ? moodMode : undefined,
      });
      const reasonsById: Record<string, string[]> = {};
      response.items.forEach((item) => {
        reasonsById[item.track.id] = item.explanations;
      });
      await replaceQueue(
        response.items.map((item) => item.track),
        reasonsById,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="flex h-full w-full flex-col border-l border-white/8 bg-panel/80">
      <div className="flex items-center justify-between px-5 pt-5">
        <div>
          <div className="text-[11px] uppercase tracking-[0.22em] text-mist">Now playing</div>
          <div className="font-display text-xl text-foam">Queue</div>
        </div>
        {onClose && (
          <button onClick={onClose} className="text-mist xl:hidden" aria-label="Close queue">
            <X size={16} />
          </button>
        )}
      </div>
      <div className="px-5 py-4">
        {track ? (
          <div>
            <div className="flex items-center gap-3">
              <Cover id={track.id} size={64} src={track.artwork_url} />
              <div className="min-w-0">
                <div className="truncate text-foam">{track.title}</div>
                <div className="truncate text-sm text-mist">
                  {track.artist}
                  {playbackCaption(track) ? ` · ${playbackCaption(track)}` : ""}
                </div>
                <div className="truncate text-xs text-mist/80">{sourceLabel(track)}</div>
              </div>
            </div>
            {playing && track.preview === "embed" && track.embed_url && (
              <iframe
                key={track.embed_url}
                title={`YouTube player for ${track.title}`}
                src={`${track.embed_url}${track.embed_url.includes("?") ? "&" : "?"}autoplay=1`}
                allow="autoplay; encrypted-media"
                className="mt-3 aspect-video w-full rounded-xl border border-white/10"
              />
            )}
            <div className="mt-4">
              <Lyrics track={track} />
            </div>
            {track.external_url && (
              <a className="mt-2 inline-block text-xs text-sand" href={track.external_url} target="_blank" rel="noreferrer">
                Open
              </a>
            )}
          </div>
        ) : (
          <p className="text-sm text-mist">Play a recommendation to fill the queue.</p>
        )}
      </div>
      <div className="flex items-center gap-2 px-5">
        <button className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-foam" onClick={() => void regenerate()} disabled={busy}>
          <RefreshCw size={12} className="mr-1 inline" />
          {busy ? "Ranking" : "Regenerate"}
        </button>
        <button className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-mist" onClick={clearQueue}>
          <Trash2 size={12} className="mr-1 inline" />
          Clear
        </button>
      </div>
      <div className="mt-3 min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        <div className="px-2 pb-2 text-[11px] uppercase tracking-[0.18em] text-mist">Up next</div>
        {queue.map((item, itemIndex) => (
          <div
            key={`${item.id}-${itemIndex}`}
            draggable
            onDragStart={() => setDrag(itemIndex)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={() => {
              if (drag !== null) move(drag, itemIndex);
              setDrag(null);
            }}
            className={`mb-1 flex items-center gap-2 rounded-lg px-2 py-1.5 ${itemIndex === index ? "bg-white/[0.05]" : "hover:bg-white/[0.03]"}`}
          >
            <button className="min-w-0 flex-1 text-left" onClick={() => void playTrack(item, queue, reasons[item.id])}>
              <div className="truncate text-sm text-foam">{item.title}</div>
              <div className="truncate text-xs text-mist">{item.artist}</div>
            </button>
            <button className="text-mist hover:text-foam" onClick={() => removeAt(itemIndex)} aria-label={`Remove ${item.title}`}>
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}
