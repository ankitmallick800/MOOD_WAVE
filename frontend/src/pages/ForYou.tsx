import { useEffect, useState } from "react";

import { TrackRow } from "../components/TrackRow";
import { api } from "../lib/api";
import { Cover } from "../lib/cover";
import { greeting, stageLabel } from "../lib/format";
import { canPlay } from "../lib/playback";
import { usePlayer } from "../lib/store";
import type { RecommendationResponse } from "../types";

export function ForYou() {
  const profile = usePlayer((state) => state.profile);
  const mood = usePlayer((state) => state.mood);
  const moodMode = usePlayer((state) => state.moodMode);
  const playTrack = usePlayer((state) => state.playTrack);
  const [showScores, setShowScores] = useState(false);
  const [data, setData] = useState<RecommendationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void api
      .recommendations({
        limit: 20,
        strategy: "hybrid",
        mood: mood ?? undefined,
        mood_mode: mood ? moodMode : undefined,
      })
      .then((response) => {
        if (!cancelled) setData(response);
      })
      .catch((reason: Error) => {
        if (!cancelled) setError(reason.message);
      });
    return () => {
      cancelled = true;
    };
  }, [profile?.inferred.n_events, profile?.inferred.confidence, profile?.explicit.genres.join("|"), mood, moodMode]);

  const items = data?.items ?? [];
  const queue = items.map((item) => item.track);
  const reasons = Object.fromEntries(items.map((item) => [item.track.id, item.explanations]));

  return (
    <div>
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.22em] text-mist">{greeting()}</div>
          <h1 className="font-display mt-2 text-5xl text-foam">For You</h1>
        </div>
        <button className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-mist" onClick={() => setShowScores((value) => !value)}>
          {showScores ? "Hide details" : "Details"}
        </button>
      </div>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-mist">{stageLabel(profile?.stage)}</p>
      {mood && (
        <p className="mt-2 text-sm text-sand">
          Session mood {mood}, {moodMode} mode. This is not saved into your taste profile.
        </p>
      )}
      {error && <p className="mt-4 text-sm text-rose-300">{error}</p>}
      <div className="mt-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {items.slice(0, 4).map((item) => (
          <button
            key={item.track.id}
            onClick={() => {
              if (canPlay(item.track)) void playTrack(item.track, queue, reasons);
            }}
            disabled={!canPlay(item.track)}
            className="rounded-2xl border border-white/8 bg-white/[0.02] p-3 text-left transition hover:bg-white/[0.04]"
          >
            <Cover id={item.track.id} fluid src={item.track.artwork_url} />
            <div className="mt-3 truncate text-sm text-foam">{item.track.title}</div>
            <div className="truncate text-xs text-mist">{item.track.artist}</div>
            <div className="mt-1 line-clamp-2 text-[11px] leading-4 text-sand/90">{item.explanations[0]}</div>
            <div className="mt-1 text-[11px] text-sand">{item.score.toFixed(2)}</div>
          </button>
        ))}
      </div>
      <section className="mt-10">
        <h2 className="text-lg text-foam">Ranked for you</h2>
        <div className="mt-3">
          {items.map((item, index) => (
            <TrackRow
              key={item.track.id}
              track={item.track}
              queue={queue}
              index={index}
              explanation={item.explanations.join(" ")}
              reasons={reasons}
              score={item.score}
              components={showScores ? item.components : undefined}
            />
          ))}
        </div>
      </section>
      {data && (
        <ul className="mt-6 max-w-2xl space-y-1 text-xs leading-5 text-mist">
          {data.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
