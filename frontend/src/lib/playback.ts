import type { Track } from "../types";
import { formatTime, titleCase } from "./format";

export function sourceLabel(track: Track): string {
  if (track.provider_label) return track.provider_label;
  if (track.provider === "itunes") return "Apple Music";
  if (track.provider === "youtube") return "YouTube";
  if (track.provider === "demo") return "Demo catalog";
  return track.provider || "Catalog";
}

export function genreText(track: Track): string {
  if (track.genre_labels && track.genre_labels.length) return track.genre_labels.slice(0, 2).join(", ");
  if (track.genres.length) return track.genres.slice(0, 2).map(titleCase).join(", ");
  return "Genre unknown";
}

export function canPlay(track: Track): boolean {
  if (track.preview === "unavailable") return false;
  if (track.preview === "embed") return Boolean(track.embed_url);
  if (track.preview === "synthesized") return !track.provider || track.provider === "demo";
  return Boolean(track.audio_url);
}

export function playbackCaption(track: Track): string {
  if (track.preview === "preview") {
    const seconds = track.preview_duration_ms ? Math.round(track.preview_duration_ms / 1000) : null;
    const song = track.song_duration_ms ? formatTime(track.song_duration_ms) : null;
    if (seconds && song) return `${seconds}s preview of ${song}`;
    if (seconds) return `${seconds}s preview`;
    return song ? `Preview of ${song}` : "Preview";
  }
  if (track.preview === "full") return "Full track";
  if (track.preview === "embed") return "Full video";
  if (track.preview === "unavailable") return "No audio";
  if (track.preview === "recording" && track.recording_title) return track.recording_title;
  if (track.preview === "spotify-preview") return "30s Spotify preview";
  if (track.preview === "synthesized") return "No audio file";
  return "";
}

export function lengthLabel(track: Track): string {
  if (track.preview === "preview") {
    if (track.preview_duration_ms) return `${Math.round(track.preview_duration_ms / 1000)}s`;
    return "Preview";
  }
  if (track.preview === "unavailable") return "—";
  if (track.preview === "embed") return formatTime(track.song_duration_ms || track.duration_ms);
  return formatTime(track.duration_ms);
}

export function describePlayback(track: Track): string {
  const source = sourceLabel(track);
  if (track.preview === "preview") {
    const length = track.preview_duration_ms
      ? `${Math.round(track.preview_duration_ms / 1000)}-second preview`
      : "Preview";
    const song = track.song_duration_ms ? ` The song is ${formatTime(track.song_duration_ms)}.` : "";
    return `${length} from ${source}.${song} This is not the full track.`;
  }
  if (track.preview === "embed") return `YouTube's player has the full video. ${source} audio is not downloaded.`;
  if (track.preview === "unavailable") return `No playable audio was provided. The link opens the song on ${source}.`;
  if (track.preview === "full") return `Full track from ${source}.`;
  if (track.preview === "recording" && track.recording_title) {
    return `Hearing “${track.recording_title}”, a public-domain recording (${track.recording_license}). The catalog title is editorial metadata, not this performance.`;
  }
  if (track.preview === "spotify-preview") return "Playing the 30-second preview Spotify provided. The full track stays on Spotify.";
  return "No recording is attached for this track.";
}
