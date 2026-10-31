import type {
  Analytics,
  ClusterView,
  Evaluation,
  Facets,
  Health,
  Playlist,
  RankConfig,
  SpotifyPlaylist,
  YtMusicPlaylist,
  LyricsResult,
  RecommendationResponse,
  Taste,
  Track,
} from "../types";
import { USER_ID } from "../types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(`${BASE}${path}`, { ...init, headers });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new ApiError(response.status, data?.detail || `Request failed (${response.status})`);
  }
  return data as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  facets: () => request<Facets>("/api/catalog/facets"),
  taste: () => request<Taste>(`/api/user/taste?user_id=${USER_ID}`),
  onboard: (body: Record<string, unknown>) =>
    request<Taste>("/api/onboarding/profile", { method: "POST", body: JSON.stringify({ user_id: USER_ID, ...body }) }),
  reset: (scope: "inferred" | "all") =>
    request<Taste | { reset: string }>("/api/user/reset", {
      method: "POST",
      body: JSON.stringify({ user_id: USER_ID, scope }),
    }),
  recommendations: (params: Record<string, string | number | boolean | undefined>) => {
    const query = new URLSearchParams({ user_id: USER_ID });
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    return request<RecommendationResponse>(`/api/recommendations?${query.toString()}`);
  },
  feedback: (body: Record<string, unknown>) =>
    request<Taste>("/api/recommendations/feedback", {
      method: "POST",
      body: JSON.stringify({ user_id: USER_ID, ...body }),
    }),
  react: (trackId: string, reaction: "like" | "dislike" | "none") =>
    request<Taste>("/api/user/reactions", {
      method: "POST",
      body: JSON.stringify({ user_id: USER_ID, track_id: trackId, reaction }),
    }),
  search: (params: { q?: string; genre?: string; language?: string; mood?: string; limit?: number }) => {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.genre) query.set("genre", params.genre);
    if (params.language) query.set("language", params.language);
    if (params.mood) query.set("mood", params.mood);
    query.set("limit", String(params.limit ?? 40));
    query.set("user_id", USER_ID);
    return request<{ tracks: Track[]; count: number; warning?: string | null }>(`/api/tracks/search?${query.toString()}`);
  },
  matchApple: (body: { title: string; artist: string }) =>
    request<Track>("/api/catalog/apple-match", {
      method: "POST",
      body: JSON.stringify({ user_id: USER_ID, ...body }),
    }),
  removePlaylistTrack: (playlistId: number, trackId: string) =>
    request<{ removed: string }>(`/api/playlists/${playlistId}/tracks/${encodeURIComponent(trackId)}?user_id=${USER_ID}`, {
      method: "DELETE",
    }),
  importTrack: (body: {
    provider: string;
    provider_id: string;
    title: string;
    artist: string;
    album?: string;
    artwork_url?: string | null;
    external_url?: string | null;
    song_duration_ms?: number | null;
    embeddable?: boolean | null;
  }) => request<Track>("/api/catalog/import", { method: "POST", body: JSON.stringify({ user_id: USER_ID, ...body }) }),
  lyrics: (trackId: string) => request<LyricsResult>(`/api/tracks/${encodeURIComponent(trackId)}/lyrics`),
  similar: (trackId: string, limit = 8) =>
    request<{ feature_source: string; items: { track: Track; similarity: number; explanations: string[] }[] }>(
      `/api/tracks/${trackId}/similar?limit=${limit}`,
    ),
  library: () => request<{ tracks: Track[]; liked: Track[]; disliked: string[] }>(`/api/library?user_id=${USER_ID}`),
  playlists: () => request<{ playlists: Playlist[] }>(`/api/playlists?user_id=${USER_ID}`),
  createPlaylist: (name: string) =>
    request<Playlist>("/api/playlists", { method: "POST", body: JSON.stringify({ user_id: USER_ID, name }) }),
  deletePlaylist: (id: number) => request<{ deleted: number }>(`/api/playlists/${id}?user_id=${USER_ID}`, { method: "DELETE" }),
  spotifyStatus: () => request<{ configured: boolean; market: string }>("/api/spotify/status"),
  spotifyPlaylists: () => request<{ playlists: SpotifyPlaylist[] }>(`/api/spotify/playlists?user_id=${USER_ID}`),
  generateSpotifyPlaylist: (body: { name: string; prompt: string; mood: string | null; limit: number; use_profile: boolean }) =>
    request<SpotifyPlaylist>("/api/spotify/playlists/generate", {
      method: "POST",
      body: JSON.stringify({ user_id: USER_ID, ...body }),
    }),
  deleteSpotifyPlaylist: (id: number) =>
    request<{ deleted: number }>(`/api/spotify/playlists/${id}?user_id=${USER_ID}`, { method: "DELETE" }),
  ytmusicStatus: () => request<{ available: boolean; location: string; auth: string }>("/api/ytmusic/status"),
  ytmusicPlaylists: () => request<{ playlists: YtMusicPlaylist[] }>(`/api/ytmusic/playlists?user_id=${USER_ID}`),
  generateYtMusicPlaylist: (body: { name: string; prompt: string; mood: string | null; limit: number; use_profile: boolean }) =>
    request<YtMusicPlaylist>("/api/ytmusic/playlists/generate", {
      method: "POST",
      body: JSON.stringify({ user_id: USER_ID, ...body }),
    }),
  deleteYtMusicPlaylist: (id: number) =>
    request<{ deleted: number }>(`/api/ytmusic/playlists/${id}?user_id=${USER_ID}`, { method: "DELETE" }),
  analytics: () => request<Analytics>(`/api/analytics/listening?user_id=${USER_ID}`),
  config: () => request<RankConfig>("/api/ml/config"),
  saveConfig: (body: Record<string, unknown>) =>
    request<RankConfig>("/api/ml/config", { method: "POST", body: JSON.stringify(body) }),
  evaluate: (k: number, diversify: boolean) =>
    request<Evaluation>("/api/ml/evaluate", {
      method: "POST",
      body: JSON.stringify({ k, diversify, include_svd: false }),
    }),
  clusters: () => request<ClusterView>("/api/ml/clusters"),
  predictMood: (distribution: Record<string, number>) =>
    request<{
      expression: string;
      confidence: number;
      uncertain: boolean;
      suggested_mood: string | null;
      reason: string;
      disclaimer: string;
      images_stored: boolean;
    }>("/api/mood/predict", { method: "POST", body: JSON.stringify({ distribution }) }),
  moodRecommendations: (body: Record<string, unknown>) =>
    request<RecommendationResponse>("/api/mood/recommendations", {
      method: "POST",
      body: JSON.stringify({ user_id: USER_ID, ...body }),
    }),
};
