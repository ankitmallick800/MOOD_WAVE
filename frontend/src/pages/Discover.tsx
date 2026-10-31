import { useEffect, useState } from "react";
import { Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis, ResponsiveContainer } from "recharts";

import { TrackRow } from "../components/TrackRow";
import { api } from "../lib/api";
import { isBrowseNoise } from "../lib/catalog";
import { titleCase } from "../lib/format";
import { usePlayer } from "../lib/store";
import type { ClusterView, Track } from "../types";

export function Discover() {
  const catalog = usePlayer((state) => state.catalog);
  const disliked = usePlayer((state) => state.disliked);
  const [query, setQuery] = useState("");
  const [genre, setGenre] = useState("");
  const [language, setLanguage] = useState("");
  const [tracks, setTracks] = useState<Track[]>([]);
  const [clusters, setClusters] = useState<ClusterView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void api
        .search({ q: query, genre: genre || undefined, language: language || undefined, limit: 40 })
        .then((response) => {
          setTracks(response.tracks);
          setNotice(response.warning ?? null);
          setError(null);
        })
        .catch((reason: Error) => setError(reason.message));
    }, 180);
    return () => window.clearTimeout(handle);
  }, [query, genre, language]);

  useEffect(() => {
    void api.clusters().then(setClusters).catch((reason: Error) => setError(reason.message));
  }, []);

  const visible = tracks.filter((track) => !disliked.includes(track.id) && !isBrowseNoise(track));
  const genres = Array.from(new Set(catalog.filter((track) => !isBrowseNoise(track)).flatMap((track) => track.genres))).sort();
  const languages = Array.from(
    new Map(catalog.filter((track) => track.language).map((track) => [track.language, track.language_label])).entries(),
  );

  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.22em] text-mist">Discover</div>
      <h1 className="font-display mt-2 text-5xl">The catalog, then the clusters.</h1>
      <div className="mt-6 flex flex-wrap gap-2">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search title, artist, album"
          className="w-full max-w-sm rounded-full border border-white/10 bg-transparent px-4 py-2 text-sm outline-none"
        />
        <select value={genre} onChange={(event) => setGenre(event.target.value)} className="rounded-full border border-white/10 bg-ink px-3 py-2 text-sm">
          <option value="">All genres</option>
          {genres.map((item) => (
            <option key={item} value={item}>
              {titleCase(item)}
            </option>
          ))}
        </select>
        <select value={language} onChange={(event) => setLanguage(event.target.value)} className="rounded-full border border-white/10 bg-ink px-3 py-2 text-sm">
          <option value="">All languages</option>
          {languages.map(([code, label]) => (
            <option key={code} value={code}>
              {label}
            </option>
          ))}
        </select>
      </div>
      {error && <p className="mt-4 text-sm text-rose-300">{error}</p>}
      {notice && <p className="mt-4 text-sm text-mist">{notice}</p>}
      <div className="mt-4">
        {visible.map((track) => (
          <TrackRow key={track.id} track={track} queue={visible} />
        ))}
      </div>
      <section className="mt-10">
        <h2 className="text-lg">Clusters</h2>
        <p className="mt-1 max-w-2xl text-sm text-mist">
          {clusters?.available
            ? `${clusters.selection} Source: ${clusters.feature_source?.replaceAll("_", " ")}. K was chosen by silhouette.`
            : clusters?.reason || "Clustering needs songs with a complete audio-feature set. Those values are unknown for this catalog."}
        </p>
        {clusters?.available && clusters.points && (
          <div className="mt-4 h-80 rounded-2xl border border-white/8 bg-white/[0.02] p-3">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart>
                <XAxis type="number" dataKey="x" tick={{ fill: "#9c978e", fontSize: 11 }} stroke="rgba(255,255,255,0.08)" name="PC1" tickFormatter={(value: number) => value.toFixed(1)} tickCount={5} />
                <YAxis type="number" dataKey="y" tick={{ fill: "#9c978e", fontSize: 11 }} stroke="rgba(255,255,255,0.08)" name="PC2" tickFormatter={(value: number) => value.toFixed(1)} width={36} />
                <ZAxis range={[60, 60]} />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  content={({ payload }) => {
                    const point = payload?.[0]?.payload as ClusterView["points"] extends (infer P)[] | undefined ? P : undefined;
                    if (!point) return null;
                    return (
                      <div className="rounded-lg border border-white/10 bg-ink px-3 py-2 text-xs">
                        <div className="text-foam">{point.title}</div>
                        <div className="text-mist">{point.artist}</div>
                        <div className="text-mist">Cluster {point.cluster}</div>
                      </div>
                    );
                  }}
                />
                <Scatter data={clusters.points} fill="#e4b48a" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        )}
        <div className="mt-4 grid gap-2 md:grid-cols-2">
          {clusters?.clusters?.map((cluster) => (
            <div key={cluster.id} className="rounded-2xl border border-white/8 px-4 py-3">
              <div className="text-sm text-foam">{cluster.label}</div>
              <div className="mt-1 text-xs text-mist">
                {cluster.size} tracks · energy {cluster.mean_energy?.toFixed(2)} · valence {cluster.mean_valence?.toFixed(2)}
              </div>
            </div>
          ))}
        </div>
        {clusters?.diagnostics && (
          <p className="mt-3 text-xs text-mist">
            Silhouette by k: {clusters.diagnostics.map((item) => `k=${item.k} ${item.silhouette.toFixed(3)}`).join(" · ")}
          </p>
        )}
      </section>
    </div>
  );
}
