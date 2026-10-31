export type LyricLine = {
  at_ms: number;
  text: string;
};

export type LyricsResult = {
  found: boolean;
  source: string;
  instrumental: boolean;
  synced: boolean;
  lines: LyricLine[];
  plain: string;
  message: string | null;
};

export type Track = {
  id: string;
  title: string;
  artist: string;
  album: string;
  genres: string[];
  language: string;
  language_label: string;
  year: number;
  duration_ms: number;
  tempo: number | null;
  energy: number | null;
  danceability: number | null;
  acousticness: number | null;
  valence: number | null;
  speechiness: number | null;
  instrumentalness: number | null;
  loudness: number | null;
  musical_key: number | null;
  mode: number | null;
  mode_label: string | null;
  mood_tags: string[];
  feature_source: string;
  preview: "recording" | "synthesized" | "preview" | "full" | "embed" | "unavailable" | string;
  audio_url: string | null;
  recording_title: string | null;
  recording_license: string | null;
  artwork_url?: string | null;
  external_url?: string | null;
  embed_url?: string | null;
  provider?: string;
  provider_label?: string;
  genre_labels?: string[];
  song_duration_ms?: number | null;
  preview_duration_ms?: number | null;
};

export type ScoreComponents = {
  content: number | null;
  collaborative: number | null;
  preference: number | null;
  mood: number | null;
  discovery: number | null;
};

export type Recommendation = {
  track: Track;
  score: number;
  components: ScoreComponents;
  weights_used: Record<string, number>;
  explanations: string[];
  neighbor: { track_id: string; title: string; artist: string; similarity: number } | null;
  language_factor: number;
};

export type RecommendationResponse = {
  user_id: string;
  items: Recommendation[];
  strategy: string;
  ranking_mode: string;
  mood: string | null;
  mood_mode: string | null;
  source_mood: string | null;
  target_mood: string | null;
  notes: string[];
  cold_start: boolean;
  diversified: boolean;
  dataset_origin: string;
};

export type ExplicitProfile = {
  artists: string[];
  genres: string[];
  languages: string[];
  purpose: string;
  discovery: number;
  energy: number;
  danceability: number;
  acousticness: number;
  valence: number;
  tempo: number;
};

export type InferredProfile = {
  genre_affinity: Record<string, number>;
  language_affinity: Record<string, number>;
  artist_affinity: Record<string, number>;
  energy: number | null;
  danceability: number | null;
  acousticness: number | null;
  valence: number | null;
  tempo: number | null;
  n_events: number;
  n_positive: number;
  confidence: number;
  plays_by_artist: Record<string, number>;
  plays_by_genre: Record<string, number>;
  plays_by_track: Record<string, number>;
  replays: number;
  completes: number;
  skips: number;
};

export type Taste = {
  user_id: string;
  explicit: ExplicitProfile;
  inferred: InferredProfile;
  stage: string;
  positive_tracks: number;
  collaborative_unlocked: boolean;
  notes: string[];
};

export type Facets = {
  genres: string[];
  languages: { code: string; label: string; count: number }[];
  artists: { name: string; genres: string[]; count: number }[];
  moods: string[];
  purposes: { id: string; label: string }[];
};

export type Health = {
  status: string;
  demo_mode: boolean;
  catalog_tracks: number;
  synthetic_users: number;
  synthetic_interactions: number;
  feature_source: string;
  models: Record<string, string>;
  warnings: string[];
};

export type MetricStat = { mean: number | null; std: number | null };

export type EvalModel = {
  strategy: string;
  label: string;
  n_users: number;
  coverage: number | null;
  metrics: Record<string, MetricStat> | null;
};

export type Evaluation = {
  suppressed: boolean;
  meaningful_as_real_world: boolean;
  warning: string;
  protocol: Record<string, unknown>;
  dataset: {
    origin: string;
    label?: string;
    n_users: number;
    n_tracks: number;
    n_interactions: number;
    n_train_interactions?: number;
    n_test_interactions?: number;
    n_eval_users: number;
  };
  models: EvalModel[];
  metric_notes: Record<string, string>;
};

export type ClusterView = {
  available: boolean;
  reason?: string;
  k?: number;
  silhouette?: number;
  diagnostics?: { k: number; silhouette: number }[];
  selection?: string;
  feature_source?: string;
  explained_variance_ratio?: number[];
  clusters?: {
    id: number;
    size: number;
    label: string;
    top_genre: string;
    mean_energy: number | null;
    mean_valence: number | null;
  }[];
  points?: {
    track_id: string;
    title: string;
    artist: string;
    x: number;
    y: number;
    cluster: number;
    genres: string[];
    energy: number | null;
    valence: number | null;
  }[];
};

export type Analytics = {
  events: number;
  listens: number;
  completes: number;
  skips: number;
  likes: number;
  listen_ms: number;
  completion_rate: number | null;
  skip_rate: number | null;
  by_genre: { genre: string; plays: number; listen_ms: number }[];
  by_language: { language: string; label: string; plays: number }[];
  by_hour: { hour: number; plays: number }[];
  note: string;
};

export type Playlist = {
  id: number;
  name: string;
  created_at: string;
  track_ids: string[];
  tracks: Track[];
};

export type SpotifyTrack = {
  spotify_id: string;
  title: string;
  artist: string;
  album: string;
  image: string | null;
  preview_url: string | null;
  spotify_url: string;
  duration_ms: number;
};

export type SpotifyPlaylist = {
  id: number;
  name: string;
  prompt: string;
  created_at: string;
  tracks: SpotifyTrack[];
  queries?: string[];
  notes?: string[];
};

export type YtMusicTrack = {
  video_id: string;
  title: string;
  artist: string;
  album: string;
  image: string | null;
  watch_url: string;
  duration_ms: number;
  embeddable?: boolean | null;
  embed_url?: string | null;
};

export type YtMusicPlaylist = {
  id: number;
  name: string;
  prompt: string;
  created_at: string;
  tracks: YtMusicTrack[];
  queries?: string[];
  notes?: string[];
};

export type RankConfig = {
  weights: Record<string, number>;
  group_weights: Record<string, number>;
  diversity_lambda: number;
  artist_cap: number;
  limit: number;
  weight_notes: Record<string, string>;
  group_weight_notes: Record<string, string>;
};

export const USER_ID = "local-user";
