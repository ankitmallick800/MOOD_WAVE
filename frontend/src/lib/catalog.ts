import type { Track } from "../types";

const PLACEHOLDER_TITLES = new Set([
  "indie pop",
  "indie rock",
  "indie folk",
  "singer songwriter",
  "pop",
  "folk",
  "jazz",
  "ambient",
  "electronic",
  "hip hop",
  "k-pop",
  "latin pop",
  "bollywood",
  "arijit singh",
  "bengali songs",
  "rabindra sangeet",
]);

export function bareTitle(title: string): string {
  return title
    .toLowerCase()
    .replace(/\([^)]*\)/g, " ")
    .replace(/\[[^\]]*\]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function isBrowseNoise(track: Track): boolean {
  if (track.provider === "demo" || track.provider === "youtube" || track.id.startsWith("mw-") || track.id.startsWith("yt:")) {
    return true;
  }
  if (/\bdemo\b/i.test(track.title)) return true;
  return PLACEHOLDER_TITLES.has(bareTitle(track.title));
}

export function isLibraryNoise(track: Track): boolean {
  return track.provider === "demo" || track.provider === "youtube" || track.id.startsWith("mw-") || track.id.startsWith("yt:");
}
