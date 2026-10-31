import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import { usePlayer } from "../lib/store";
import type { Health } from "../types";

export function Settings() {
  const navigate = useNavigate();
  const setProfile = usePlayer((state) => state.setProfile);
  const clearQueue = usePlayer((state) => state.clearQueue);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.health().then(setHealth).catch((reason: Error) => setError(reason.message));
  }, []);

  async function resetAll() {
    await api.reset("all");
    clearQueue();
    setProfile(null);
    navigate("/onboarding");
  }

  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.22em] text-mist">Settings</div>
      <h1 className="font-display mt-2 text-5xl">What this build can and cannot do.</h1>
      {error && <p className="mt-4 text-sm text-rose-300">{error}</p>}
      {health && (
        <div className="mt-6 grid gap-3 md:grid-cols-2">
          <Info label="Catalog" value={health.demo_mode ? `${health.catalog_tracks} fictional tracks` : `${health.catalog_tracks} songs`} />
          <Info label="Feature source" value={health.feature_source.replaceAll("_", " ")} />
          <Info
            label="Synthetic listeners"
            value={health.demo_mode ? `${health.synthetic_users} users, ${health.synthetic_interactions} events` : "Not used for this catalog"}
          />
          <Info label="Audio analysis" value={health.models.audio_extraction.replaceAll("_", " ")} />
          <Info label="Vision" value="Browser expression model. No images are sent here." />
          <Info label="Collaborative model" value={health.models.collaborative.replaceAll("_", " ")} />
        </div>
      )}
      <ul className="mt-8 max-w-2xl list-disc space-y-2 pl-5 text-sm leading-6 text-mist">
        {health?.demo_mode ? (
          <li>This server is on the fictional demo catalog. Those tracks can play a separate public-domain recording. Set MOODWAVE_CATALOG_SOURCE=itunes for real song metadata.</li>
        ) : (
          <li>Recommendations use Apple Music metadata. A song plays its official preview when Apple provides one, and the player labels that preview. Tempo, energy, and mood stay unknown.</li>
        )}
        <li>The playlist page searches YouTube Music, then plays the matching Apple Music preview. If Apple has no match, the row links out. Nothing is downloaded, and a playlist saved here is not added to a YouTube Music or Spotify account.</li>
        <li>Lyrics, when LRCLIB has them, sit in a scrollable list beside the queue. They are the full text, not timed to the preview.</li>
        <li>Recommendations explain the scores the ranker computed. A language model does not write them.</li>
        <li>One like cannot replace onboarding. Inferred taste is an exponential moving average, blended by confidence.</li>
        <li>The collaborative model is not refit when you press a button. Model Lab runs a separate holdout.</li>
      </ul>
      <button className="mt-8 rounded-full border border-rose-300/40 px-4 py-2 text-sm text-rose-200" onClick={() => void resetAll()}>
        Reset profile, events, and queue
      </button>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/8 px-4 py-3">
      <div className="text-[11px] uppercase tracking-[0.16em] text-mist">{label}</div>
      <div className="mt-1 text-sm text-foam">{value}</div>
    </div>
  );
}
