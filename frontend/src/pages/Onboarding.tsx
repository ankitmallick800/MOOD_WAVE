import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "../lib/api";
import { usePlayer } from "../lib/store";
import type { Facets } from "../types";

const STEPS = ["Languages", "Genres", "Artists", "Purpose", "Sound"];

export function Onboarding() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const editing = params.get("edit") === "1";
  const profile = usePlayer((state) => state.profile);
  const setProfile = usePlayer((state) => state.setProfile);
  const [facets, setFacets] = useState<Facets | null>(null);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [languages, setLanguages] = useState<string[]>(profile?.explicit.languages ?? []);
  const [genres, setGenres] = useState<string[]>(profile?.explicit.genres ?? []);
  const [artists, setArtists] = useState<string[]>(profile?.explicit.artists ?? []);
  const [purpose, setPurpose] = useState(profile?.explicit.purpose ?? "relax");
  const [discovery, setDiscovery] = useState(profile?.explicit.discovery ?? 0.45);
  const [energy, setEnergy] = useState(profile?.explicit.energy ?? 0.5);
  const [danceability, setDanceability] = useState(profile?.explicit.danceability ?? 0.45);
  const [acousticness, setAcousticness] = useState(profile?.explicit.acousticness ?? 0.55);
  const [valence, setValence] = useState(profile?.explicit.valence ?? 0.55);
  const [tempo, setTempo] = useState(profile?.explicit.tempo ?? 0.45);

  useEffect(() => {
    void api.facets().then(setFacets).catch((reason: Error) => setError(reason.message));
  }, []);

  function toggle(list: string[], value: string, setList: (next: string[]) => void) {
    setList(list.includes(value) ? list.filter((item) => item !== value) : [...list, value]);
  }

  async function save() {
    setError(null);
    try {
      const taste = await api.onboard({
        artists,
        genres,
        languages,
        purpose,
        discovery,
        energy,
        danceability,
        acousticness,
        valence,
        tempo,
        reset_inferred: false,
      });
      setProfile(taste);
      navigate("/");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save the profile.");
    }
  }

  const canNext =
    (step === 0 && languages.length > 0) ||
    (step === 1 && genres.length > 0) ||
    step === 2 ||
    step === 3 ||
    step === 4;

  return (
    <div className="mx-auto flex min-h-full max-w-3xl flex-col px-6 py-12">
      <div className="text-[11px] uppercase tracking-[0.22em] text-mist">{editing ? "Edit taste" : "Welcome"}</div>
      <h1 className="font-display mt-3 text-5xl text-foam">Tell Moodwave what to start from.</h1>
      <p className="mt-4 max-w-xl text-mist">
        These answers are the explicit profile. Listening will nudge a separate inferred profile slowly. Nothing here is a personality label.
      </p>
      <div className="mt-8 flex gap-2">
        {STEPS.map((label, index) => (
          <div key={label} className={`h-1 flex-1 rounded-full ${index <= step ? "bg-sand" : "bg-white/10"}`} />
        ))}
      </div>
      <div className="mt-8">
        {step === 0 && facets && (
          <Choice
            title="Preferred languages"
            options={facets.languages.map((language) => ({ id: language.code, label: language.label }))}
            selected={languages}
            onToggle={(id) => toggle(languages, id, setLanguages)}
          />
        )}
        {step === 1 && facets && (
          <Choice
            title="Preferred genres"
            options={facets.genres.map((genre) => ({ id: genre, label: genre }))}
            selected={genres}
            onToggle={(id) => toggle(genres, id, setGenres)}
          />
        )}
        {step === 2 && facets && (
          <Choice
            title="Artists you already like"
            hint="Optional. Unknown artists are left out of the score, not treated as a dislike."
            options={facets.artists.map((artist) => ({ id: artist.name, label: artist.name }))}
            selected={artists}
            onToggle={(id) => toggle(artists, id, setArtists)}
          />
        )}
        {step === 3 && facets && (
          <Choice
            title="What are you listening for?"
            options={facets.purposes.map((item) => ({ id: item.id, label: item.label }))}
            selected={[purpose]}
            onToggle={(id) => setPurpose(id)}
          />
        )}
        {step === 4 && (
          <div className="space-y-5">
            <Slider label="Familiarity to discovery" value={discovery} onChange={setDiscovery} low="Familiar" high="Explore" />
            <Slider label="Energy" value={energy} onChange={setEnergy} />
            <Slider label="Danceability" value={danceability} onChange={setDanceability} />
            <Slider label="Acousticness" value={acousticness} onChange={setAcousticness} />
            <Slider label="Valence" value={valence} onChange={setValence} low="Darker" high="Brighter" />
            <Slider label="Tempo" value={tempo} onChange={setTempo} low="Slower" high="Faster" />
          </div>
        )}
      </div>
      {error && <p className="mt-4 text-sm text-rose-300">{error}</p>}
      <div className="mt-10 flex gap-3">
        {step > 0 && (
          <button className="rounded-full border border-white/10 px-5 py-2 text-sm" onClick={() => setStep((value) => value - 1)}>
            Back
          </button>
        )}
        {step < 4 && (
          <button
            className="rounded-full bg-foam px-5 py-2 text-sm text-ink disabled:opacity-40"
            disabled={!canNext}
            onClick={() => setStep((value) => value + 1)}
          >
            Continue
          </button>
        )}
        {step === 4 && (
          <button className="rounded-full bg-sand px-5 py-2 text-sm text-ink" onClick={() => void save()}>
            Save profile
          </button>
        )}
      </div>
    </div>
  );
}

function Choice({
  title,
  hint,
  options,
  selected,
  onToggle,
}: {
  title: string;
  hint?: string;
  options: { id: string; label: string }[];
  selected: string[];
  onToggle: (id: string) => void;
}) {
  return (
    <div>
      <h2 className="text-lg text-foam">{title}</h2>
      {hint && <p className="mt-1 text-sm text-mist">{hint}</p>}
      <div className="mt-4 flex flex-wrap gap-2">
        {options.map((option) => {
          const on = selected.includes(option.id);
          return (
            <button
              key={option.id}
              onClick={() => onToggle(option.id)}
              className={`rounded-full border px-3 py-1.5 text-sm ${on ? "border-sand bg-sand/15 text-sand" : "border-white/10 text-mist hover:text-foam"}`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Slider({
  label,
  value,
  onChange,
  low = "Low",
  high = "High",
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  low?: string;
  high?: string;
}) {
  return (
    <label className="block">
      <div className="mb-2 flex justify-between text-sm">
        <span>{label}</span>
        <span className="text-mist">{value.toFixed(2)}</span>
      </div>
      <input type="range" min={0} max={1} step={0.01} value={value} onChange={(event) => onChange(Number(event.target.value))} className="w-full" />
      <div className="mt-1 flex justify-between text-[11px] text-mist">
        <span>{low}</span>
        <span>{high}</span>
      </div>
    </label>
  );
}
