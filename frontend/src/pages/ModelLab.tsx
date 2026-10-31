import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { TrackRow } from "../components/TrackRow";
import { api } from "../lib/api";
import type { Evaluation, RankConfig, RecommendationResponse } from "../types";

export function ModelLab() {
  const [config, setConfig] = useState<RankConfig | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [sample, setSample] = useState<RecommendationResponse | null>(null);
  const [strategy, setStrategy] = useState("hybrid");
  const [k, setK] = useState(10);
  const [diversify, setDiversify] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api
      .config()
      .then(setConfig)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  async function save(next: RankConfig) {
    setConfig(next);
    const saved = await api.saveConfig({
      weights: next.weights,
      group_weights: next.group_weights,
      diversity_lambda: next.diversity_lambda,
      artist_cap: next.artist_cap,
      limit: next.limit,
    });
    setConfig(saved);
  }

  async function run() {
    if (!config) return;
    setBusy(true);
    setError(null);
    try {
      const [result, preview] = await Promise.all([
        api.evaluate(k, diversify),
        api.recommendations({ limit: 5, strategy, diversify: true }),
      ]);
      setEvaluation(result);
      setSample(preview);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Evaluation failed.");
    } finally {
      setBusy(false);
    }
  }

  const chart =
    evaluation && !evaluation.suppressed
      ? evaluation.models.map((model) => ({
          name: model.label.replace(" filtering", "").replace(" baseline", "").replace(" ranker", ""),
          precision: model.metrics?.precision_at_k.mean ?? 0,
          recall: model.metrics?.recall_at_k.mean ?? 0,
          ndcg: model.metrics?.ndcg_at_k.mean ?? 0,
        }))
      : [];

  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.22em] text-mist">Model Lab</div>
      <h1 className="font-display mt-2 text-5xl">What the numbers actually are.</h1>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-mist">
        Evaluation uses a temporal holdout on the labeled synthetic listener set. The chart is that computation. It is not a claim about real listeners.
      </p>
      {evaluation && (
        <div className="mt-5 rounded-2xl border border-sand/30 bg-sand/10 px-4 py-3 text-sm leading-6 text-sand">{evaluation.warning}</div>
      )}
      {error && <p className="mt-4 text-sm text-rose-300">{error}</p>}
      {config && (
        <section className="mt-8 grid gap-8 lg:grid-cols-2">
          <div>
            <h2 className="text-lg">Hybrid weights</h2>
            {Object.entries(config.weights).map(([name, value]) => (
              <label key={name} className="mt-3 block">
                <div className="flex justify-between text-sm">
                  <span>{name}</span>
                  <span className="text-mist">{value.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={value}
                  onChange={(event) =>
                    void save({ ...config, weights: { ...config.weights, [name]: Number(event.target.value) } })
                  }
                  className="w-full"
                />
                <p className="text-[12px] text-mist">{config.weight_notes[name]}</p>
              </label>
            ))}
          </div>
          <div>
            <h2 className="text-lg">Feature group weights</h2>
            <p className="mt-1 text-xs text-mist">These scale blocks inside cosine similarity. They do not invent missing features.</p>
            {Object.entries(config.group_weights).map(([name, value]) => (
              <label key={name} className="mt-3 block">
                <div className="flex justify-between text-sm">
                  <span>{name}</span>
                  <span className="text-mist">{value.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={3}
                  step={0.05}
                  value={value}
                  onChange={(event) =>
                    void save({ ...config, group_weights: { ...config.group_weights, [name]: Number(event.target.value) } })
                  }
                  className="w-full"
                />
                <p className="text-[12px] text-mist">{config.group_weight_notes[name]}</p>
              </label>
            ))}
            <label className="mt-4 block text-sm">
              Diversity lambda {config.diversity_lambda.toFixed(2)}
              <input
                type="range"
                min={0.5}
                max={1}
                step={0.01}
                value={config.diversity_lambda}
                onChange={(event) => void save({ ...config, diversity_lambda: Number(event.target.value) })}
                className="mt-1 w-full"
              />
            </label>
          </div>
        </section>
      )}
      <section className="mt-10 flex flex-wrap items-end gap-3">
        <label className="text-sm text-mist">
          K
          <input
            type="number"
            min={1}
            max={20}
            value={k}
            onChange={(event) => setK(Number(event.target.value))}
            className="ml-2 w-16 rounded-lg border border-white/10 bg-transparent px-2 py-1 text-foam"
          />
        </label>
        <label className="text-sm text-mist">
          Sample strategy
          <select value={strategy} onChange={(event) => setStrategy(event.target.value)} className="ml-2 rounded-lg border border-white/10 bg-ink px-2 py-1 text-foam">
            <option value="hybrid">Hybrid</option>
            <option value="content">Content</option>
            <option value="collaborative">Collaborative</option>
            <option value="popularity">Popularity</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-mist">
          <input type="checkbox" checked={diversify} onChange={(event) => setDiversify(event.target.checked)} />
          Score diversity rerank in the metrics
        </label>
        <button className="rounded-full bg-foam px-4 py-2 text-sm text-ink disabled:opacity-40" onClick={() => void run()} disabled={busy || !config}>
          {busy ? "Running holdout" : "Run evaluation"}
        </button>
      </section>
      {evaluation && (
        <section className="mt-8">
          <div className="text-sm text-mist">
            {evaluation.dataset.n_users} synthetic users · {evaluation.dataset.n_tracks} tracks · {evaluation.dataset.n_interactions} interactions ·{" "}
            {evaluation.dataset.n_eval_users} users in the holdout
          </div>
          {!evaluation.suppressed && (
            <>
              <div className="mt-4 h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chart}>
                    <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                    <XAxis dataKey="name" tick={{ fill: "#9c978e", fontSize: 12 }} stroke="rgba(255,255,255,0.08)" />
                    <YAxis tick={{ fill: "#9c978e", fontSize: 12 }} stroke="rgba(255,255,255,0.08)" domain={[0, 1]} />
                    <Tooltip contentStyle={{ background: "#101012", border: "1px solid rgba(255,255,255,0.08)" }} />
                    <Legend />
                    <Bar dataKey="ndcg" fill="#e4b48a" radius={4} />
                    <Bar dataKey="precision" fill="#8fb9aa" radius={4} />
                    <Bar dataKey="recall" fill="#a9b7d4" radius={4} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-xs uppercase tracking-wider text-mist">
                    <tr>
                      <th className="py-2">Model</th>
                      <th>Precision</th>
                      <th>Recall</th>
                      <th>NDCG</th>
                      <th>Hit rate</th>
                      <th>Coverage</th>
                      <th>Diversity</th>
                      <th>Novelty</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evaluation.models.map((model) => (
                      <tr key={model.strategy} className="border-t border-white/8">
                        <td className="py-2">{model.label}</td>
                        <Cell value={model.metrics?.precision_at_k.mean} />
                        <Cell value={model.metrics?.recall_at_k.mean} />
                        <Cell value={model.metrics?.ndcg_at_k.mean} />
                        <Cell value={model.metrics?.hit_rate_at_k.mean} />
                        <Cell value={model.coverage} />
                        <Cell value={model.metrics?.diversity.mean} />
                        <Cell value={model.metrics?.novelty.mean} digits={2} />
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          <div className="mt-6 grid gap-3 md:grid-cols-2">
            {Object.entries(evaluation.metric_notes).map(([name, note]) => (
              <div key={name} className="rounded-2xl border border-white/8 px-4 py-3">
                <div className="text-sm text-foam">{name}</div>
                <p className="mt-1 text-xs leading-5 text-mist">{note}</p>
              </div>
            ))}
          </div>
        </section>
      )}
      {sample && (
        <section className="mt-10">
          <h2 className="text-lg">Sample from the {sample.strategy} strategy</h2>
          <p className="text-sm text-mist">{sample.ranking_mode.replaceAll("_", " ")}</p>
          <div className="mt-3">
            {sample.items.map((item) => (
              <TrackRow
                key={item.track.id}
                track={item.track}
                queue={sample.items.map((entry) => entry.track)}
                explanation={item.explanations.join(" ")}
                score={item.score}
                components={item.components}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function Cell({ value, digits = 3 }: { value: number | null | undefined; digits?: number }) {
  return <td>{value === null || value === undefined ? "—" : value.toFixed(digits)}</td>;
}
