import { useState } from "react";

const PALETTES = [
  ["#2a211c", "#e4b48a"],
  ["#1b2422", "#8fb9aa"],
  ["#241c26", "#d2b0c8"],
  ["#1a1e28", "#a9b7d4"],
  ["#2a2218", "#d08a6a"],
  ["#1c2430", "#d9c7a1"],
];

function hash(value: string): number {
  let h = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function slot(seed: number, shift: number, base: number): number {
  return (seed >>> shift) % base;
}

export function Cover({ id, size = 48, fluid = false, src }: { id: string; size?: number; fluid?: boolean; src?: string | null }) {
  const [failed, setFailed] = useState(false);
  const frame = fluid ? "aspect-square w-full rounded-xl object-cover" : "shrink-0 rounded-md object-cover";
  if (src && !failed) {
    return (
      <img
        src={src}
        alt=""
        width={fluid ? undefined : size}
        height={fluid ? undefined : size}
        className={frame}
        style={fluid ? undefined : { width: size, height: size }}
        onError={() => setFailed(true)}
      />
    );
  }
  const seed = hash(id || "moodwave");
  const [ink, accent] = PALETTES[slot(seed, 0, PALETTES.length)];
  const second = PALETTES[slot(seed, 3, PALETTES.length)][1];
  return (
    <svg
      width={fluid ? "100%" : size}
      height={fluid ? "100%" : size}
      viewBox="0 0 80 80"
      aria-hidden
      className={fluid ? "aspect-square w-full rounded-xl" : "shrink-0 rounded-md"}
    >
      <rect width="80" height="80" fill={ink} />
      <circle cx={20 + slot(seed, 0, 28)} cy={24 + slot(seed, 5, 20)} r={18 + slot(seed, 0, 8)} fill={accent} opacity="0.9" />
      <circle cx={58} cy={54} r={16} fill={second} opacity="0.75" />
      <rect x="8" y="62" width="64" height="2" fill="#f4f1ea" opacity="0.35" />
    </svg>
  );
}
