import { Camera, CameraOff } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { TrackRow } from "../components/TrackRow";
import { api } from "../lib/api";
import { usePlayer } from "../lib/store";
import { loadExpressionModels, readExpression, smoothDistribution, topExpression } from "../lib/vision";
import type { Recommendation } from "../types";

const MOODS = ["happy", "sad", "angry", "calm", "focused", "energetic", "romantic", "nocturnal", "hopeful", "surprised"];

export function MoodStudio() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const smoothRef = useRef<Record<string, number>>({});
  const stableRef = useRef({ label: "", frames: 0 });
  const stopRef = useRef(false);
  const setMood = usePlayer((state) => state.setMood);
  const moodMode = usePlayer((state) => state.moodMode);
  const [cameraOn, setCameraOn] = useState(false);
  const [reading, setReading] = useState("Camera off");
  const [face, setFace] = useState(false);
  const [distribution, setDistribution] = useState<Record<string, number> | null>(null);
  const [serverNote, setServerNote] = useState<string | null>(null);
  const [suggested, setSuggested] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>("calm");
  const [mode, setMode] = useState<"match" | "shift">(moodMode);
  const [items, setItems] = useState<Recommendation[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    return () => {
      stopRef.current = true;
      stopCamera();
    };
  }, []);

  function stopCamera() {
    stopRef.current = true;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraOn(false);
    setFace(false);
    setReading("Camera off");
  }

  async function startCamera() {
    setError(null);
    stopRef.current = false;
    try {
      await loadExpressionModels();
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 640 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraOn(true);
      void loop();
    } catch {
      stopCamera();
      setError("Camera permission or the expression model failed. The manual selector still ranks music.");
    }
  }

  async function loop() {
    let last = 0;
    const tick = async (now: number) => {
      if (stopRef.current || !videoRef.current) return;
      if (now - last > 160) {
        last = now;
        const raw = await readExpression(videoRef.current);
        if (!raw) {
          setFace(false);
          setReading("No face in frame");
        } else {
          setFace(true);
          const smoothed = smoothDistribution(smoothRef.current, raw);
          smoothRef.current = smoothed;
          setDistribution(smoothed);
          const top = topExpression(smoothed);
          if (top.label === stableRef.current.label && top.confidence >= 0.6) stableRef.current.frames += 1;
          else stableRef.current = { label: top.label, frames: top.confidence >= 0.6 ? 1 : 0 };
          if (stableRef.current.frames >= 8) {
            setReading(`${top.label} · ${Math.round(top.confidence * 100)}% smoothed`);
          } else {
            setReading("Waiting for a stable reading");
          }
        }
      }
      if (!stopRef.current) requestAnimationFrame((time) => void tick(time));
    };
    requestAnimationFrame((time) => void tick(time));
  }

  async function checkReading() {
    if (!distribution || stableRef.current.frames < 8) {
      setServerNote("Hold still until the reading stays steady, then check it.");
      return;
    }
    const result = await api.predictMood(distribution);
    setServerNote(result.reason);
    setSuggested(result.suggested_mood);
    if (result.suggested_mood) setSelected(result.suggested_mood);
  }

  async function recommend(source: "manual" | "camera") {
    setBusy(true);
    setError(null);
    try {
      const response = await api.moodRecommendations({
        mood: selected,
        mode,
        source,
        confirmed: true,
        confidence: distribution ? topExpression(distribution).confidence : undefined,
        limit: 12,
      });
      setItems(response.items);
      setMood(selected, mode);
      setServerNote(response.notes.join(" "));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not rank tracks.");
    } finally {
      setBusy(false);
    }
  }

  const queue = items.map((item) => item.track);
  const reasons = Object.fromEntries(items.map((item) => [item.track.id, item.explanations]));

  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.22em] text-mist">Mood Studio</div>
      <h1 className="font-display mt-2 text-5xl">A listening target, not a diagnosis.</h1>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-mist">
        The camera is optional. Frames stay in the browser, are not saved, and are not uploaded. An expression is a temporary, uncertain signal. You confirm it before the ranker uses it.
      </p>
      <div className="mt-6 grid gap-6 lg:grid-cols-[320px_1fr]">
        <div className="rounded-3xl border border-white/8 bg-white/[0.02] p-4">
          <div className="relative aspect-[4/3] overflow-hidden rounded-2xl bg-black">
            <video ref={videoRef} muted playsInline className="h-full w-full object-cover" />
            {!cameraOn && <div className="absolute inset-0 grid place-items-center text-sm text-mist">Camera is off</div>}
          </div>
          <div className="mt-3 flex gap-2">
            {!cameraOn ? (
              <button className="rounded-full bg-foam px-3 py-1.5 text-sm text-ink" onClick={() => void startCamera()}>
                <Camera size={14} className="mr-1 inline" />
                Enable camera
              </button>
            ) : (
              <button className="rounded-full border border-white/10 px-3 py-1.5 text-sm" onClick={stopCamera}>
                <CameraOff size={14} className="mr-1 inline" />
                Stop
              </button>
            )}
            <button className="rounded-full border border-white/10 px-3 py-1.5 text-sm text-mist" onClick={() => void checkReading()} disabled={!cameraOn}>
              Check reading
            </button>
          </div>
          <p className="mt-3 text-sm text-foam">{reading}</p>
          <p className="text-xs text-mist">{face ? "Face detected. Expression model is running locally." : "Face detection has not locked a face."}</p>
        </div>
        <div>
          <div className="flex gap-2">
            {(["match", "shift"] as const).map((item) => (
              <button
                key={item}
                onClick={() => setMode(item)}
                className={`rounded-full px-3 py-1.5 text-sm ${mode === item ? "bg-sand text-ink" : "border border-white/10 text-mist"}`}
              >
                {item === "match" ? "Match my mood" : "Shift my mood"}
              </button>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {MOODS.map((mood) => (
              <button
                key={mood}
                onClick={() => setSelected(mood)}
                className={`rounded-full border px-3 py-1.5 text-sm ${selected === mood ? "border-sand text-sand" : "border-white/10 text-mist"}`}
              >
                {mood}
                {suggested === mood ? " · suggested" : ""}
              </button>
            ))}
          </div>
          <div className="mt-4 flex gap-2">
            <button className="rounded-full bg-foam px-4 py-2 text-sm text-ink" onClick={() => void recommend("manual")} disabled={busy}>
              Rank manually
            </button>
            <button
              className="rounded-full border border-white/10 px-4 py-2 text-sm"
              onClick={() => void recommend("camera")}
              disabled={busy || !suggested}
            >
              Use confirmed camera mood
            </button>
          </div>
          {serverNote && <p className="mt-3 max-w-xl text-sm text-mist">{serverNote}</p>}
          {error && <p className="mt-3 text-sm text-rose-300">{error}</p>}
        </div>
      </div>
      <div className="mt-8">
        {items.map((item, index) => (
          <TrackRow key={item.track.id} track={item.track} queue={queue} reasons={reasons} index={index} explanation={item.explanations[0]} score={item.score} />
        ))}
      </div>
    </div>
  );
}
