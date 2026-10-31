import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { api } from "../lib/api";
import { titleCase } from "../lib/format";
import { usePlayer } from "../lib/store";
import type { Analytics } from "../types";

export function Taste() {
  const profile = usePlayer((state) => state.profile);
  const refreshProfile = usePlayer((state) => state.refreshProfile);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.analytics().then(setAnalytics).catch((reason: Error) => setError(reason.message));
  }, [profile?.inferred.n_events]);

  if (!profile) return null;
  const genres = Object.entries(profile.inferred.genre_affinity)
    .map(([genre, value]) => ({ genre: titleCase(genre), value: Number(value.toFixed(3)) }))
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, 8);

  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.22em] text-mist">My taste</div>
      <h1 className="font-display mt-2 text-5xl">Three separate signals.</h1>
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <Card title="Explicit" body="Chosen in onboarding. Editing it does not wipe listening history.">
          <p className="text-sm text-mist">Genres: {profile.explicit.genres.map(titleCase).join(", ")}</p>
          <p className="mt-1 text-sm text-mist">Languages: {profile.explicit.languages.join(", ")}</p>
          <p className="mt-1 text-sm text-mist">Artists: {profile.explicit.artists.join(", ") || "None selected"}</p>
          <p className="mt-1 text-sm text-mist">Purpose: {profile.explicit.purpose}</p>
          <p className="mt-1 text-sm text-mist">Discovery: {profile.explicit.discovery.toFixed(2)}</p>
          <Link to="/onboarding?edit=1" className="mt-3 inline-block text-sm text-sand">
            Edit explicit profile
          </Link>
        </Card>
        <Card title="Inferred" body={`Confidence ${profile.inferred.confidence.toFixed(2)} from ${profile.inferred.n_positive} positive events.`}>
          <p className="text-sm text-mist">Events replayed: {profile.inferred.n_events}</p>
          <p className="mt-1 text-sm text-mist">
            Energy {fmt(profile.inferred.energy)} · valence {fmt(profile.inferred.valence)} · acoustic {fmt(profile.inferred.acousticness)}
          </p>
          <button
            className="mt-3 text-sm text-sand"
            onClick={() =>
              void api.reset("inferred").then(() => refreshProfile())
            }
          >
            Reset inferred taste
          </button>
        </Card>
        <Card title="Session mood" body="Held in this browser tab. It changes ranking only while you pass it to the player.">
          <p className="text-sm text-mist">Set it in Mood Studio. It is not part of the saved profile.</p>
        </Card>
      </div>
      {genres.length > 0 && (
        <div className="mt-8 h-64">
          <div className="mb-2 text-sm text-mist">Inferred genre affinity, from −1 to 1</div>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={genres}>
              <XAxis dataKey="genre" tick={{ fill: "#9c978e", fontSize: 11 }} stroke="rgba(255,255,255,0.08)" />
              <YAxis domain={[-1, 1]} tick={{ fill: "#9c978e", fontSize: 11 }} stroke="rgba(255,255,255,0.08)" />
              <Tooltip contentStyle={{ background: "#101012", border: "1px solid rgba(255,255,255,0.08)" }} />
              <Bar dataKey="value" fill="#e4b48a" radius={4} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      {error && <p className="mt-4 text-sm text-rose-300">{error}</p>}
      {analytics && analytics.events === 0 && <p className="mt-6 text-sm text-mist">No listening events yet, so there is no listening chart.</p>}
      {analytics && analytics.by_genre.length > 0 && (
        <div className="mt-6">
          <h2 className="text-lg">Your listening, not the synthetic set</h2>
          <p className="text-sm text-mist">
            {analytics.listens} plays · completion {analytics.completion_rate === null ? "—" : `${Math.round(analytics.completion_rate * 100)}%`} · skips{" "}
            {analytics.skips}
          </p>
        </div>
      )}
      <ul className="mt-6 max-w-2xl space-y-1 text-xs text-mist">
        {profile.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </div>
  );
}

function Card({ title, body, children }: { title: string; body: string; children: ReactNode }) {
  return (
    <section className="rounded-3xl border border-white/8 bg-white/[0.02] p-4">
      <h2 className="text-lg text-foam">{title}</h2>
      <p className="mt-1 text-sm leading-5 text-mist">{body}</p>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function fmt(value: number | null): string {
  return value === null ? "not enough listening" : value.toFixed(2);
}
