import { create } from "zustand";

import type { Taste, Track } from "../types";
import { preview } from "./audio";
import { api, ApiError } from "./api";
import { canPlay } from "./playback";

type RepeatMode = "off" | "all" | "one";

type Persisted = {
  volume: number;
  shuffle: boolean;
  repeat: RepeatMode;
  queueIds: string[];
  index: number;
  reasons: Record<string, string[]>;
};

const STORAGE_KEY = "moodwave.player";

function loadPersisted(): Persisted {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const empty = { volume: 0.8, shuffle: false, repeat: "off" as RepeatMode, queueIds: [], index: 0, reasons: {} };
    if (!raw) return empty;
    return { ...empty, ...JSON.parse(raw) };
  } catch {
    return { volume: 0.8, shuffle: false, repeat: "off", queueIds: [], index: 0, reasons: {} };
  }
}

const sessionPlayed = new Set<string>();

type Store = {
  ready: boolean;
  offline: string | null;
  profile: Taste | null;
  catalog: Track[];
  queue: Track[];
  index: number;
  playing: boolean;
  positionMs: number;
  volume: number;
  shuffle: boolean;
  repeat: RepeatMode;
  liked: string[];
  disliked: string[];
  reasons: Record<string, string[]>;
  mood: string | null;
  moodMode: "match" | "shift";
  playbackNote: string | null;
  boot: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  setProfile: (profile: Taste | null) => void;
  playTrack: (track: Track, queue?: Track[], reason?: string[] | Record<string, string[]>) => Promise<void>;
  toggle: () => Promise<void>;
  next: (reason?: "ended" | "skip") => Promise<void>;
  prev: () => Promise<void>;
  seek: (ms: number) => Promise<void>;
  setVolume: (value: number) => void;
  toggleShuffle: () => void;
  cycleRepeat: () => void;
  enqueue: (track: Track) => void;
  setQueue: (tracks: Track[]) => void;
  removeAt: (index: number) => void;
  move: (from: number, to: number) => void;
  clearQueue: () => void;
  replaceQueue: (tracks: Track[], reasons?: Record<string, string[]>) => Promise<void>;
  toggleLike: (track: Track) => Promise<void>;
  toggleDislike: (track: Track) => Promise<void>;
  setMood: (mood: string | null, mode?: "match" | "shift") => void;
  tick: () => void;
};

let flushing = false;

export const usePlayer = create<Store>((set, get) => {
  const persisted = loadPersisted();
  preview.setVolume(persisted.volume);

  function persist() {
    const state = get();
    const payload: Persisted = {
      volume: state.volume,
      shuffle: state.shuffle,
      repeat: state.repeat,
      queueIds: state.queue.map((track) => track.id),
      index: state.index,
      reasons: state.reasons,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  }

  async function flush(track: Track | undefined, position: number, reason: "ended" | "skip" | "play") {
    if (!track || flushing || track.id.startsWith("spotify:")) return;
    const embed = track.preview === "embed";
    if (position < 2000 && reason !== "ended" && !(embed && reason === "skip")) return;
    const ratio = track.duration_ms > 0 ? position / track.duration_ms : 0;
    let event: "play" | "complete" | "skip" | "replay" = "play";
    if (embed && reason === "skip") event = "skip";
    else if (reason === "ended" || ratio >= 0.9) event = sessionPlayed.has(track.id) ? "replay" : "complete";
    else if (reason === "skip" && ratio < 0.4) event = "skip";
    else if (sessionPlayed.has(track.id) && ratio >= 0.5) event = "replay";
    sessionPlayed.add(track.id);
    flushing = true;
    try {
      const taste = await api.feedback({
        track_id: track.id,
        event_type: event,
        listen_ms: Math.round(position),
        duration_ms: track.duration_ms,
      });
      set({ profile: taste });
    } catch {
      /* Playback should keep going if a feedback write fails. */
    } finally {
      flushing = false;
    }
  }

  async function begin(track: Track, offsetMs: number) {
    if (track.preview === "embed" && track.embed_url) {
      preview.pause();
      set({ playing: true, positionMs: 0, playbackNote: null });
      if (offsetMs === 0) {
        void api
          .feedback({
            track_id: track.id,
            event_type: "play",
            listen_ms: 0,
            duration_ms: track.song_duration_ms || track.duration_ms || 0,
          })
          .then((taste) => set({ profile: taste }))
          .catch(() => undefined);
      }
      return;
    }
    if (!canPlay(track)) {
      preview.pause();
      set({ playing: false, positionMs: 0, playbackNote: "No playable audio for this song." });
      return;
    }
    set({ playing: true, playbackNote: null });
    const started = await preview.play(
      track,
      offsetMs,
      () => {
        void get().next("ended");
      },
      (ms) => {
        const rounded = Math.round(ms);
        set({
          queue: get().queue.map((item) =>
            item.id === track.id
              ? {
                  ...item,
                  duration_ms: rounded,
                  preview_duration_ms: item.preview === "preview" ? rounded : item.preview_duration_ms,
                }
              : item,
          ),
        });
      },
    );
    if (!started && get().queue[get().index]?.id === track.id) {
      set({ playing: false, playbackNote: "The audio could not be loaded." });
    }
  }

  return {
    ready: false,
    offline: null,
    profile: null,
    catalog: [],
    queue: [],
    index: 0,
    playing: false,
    positionMs: 0,
    volume: persisted.volume,
    shuffle: persisted.shuffle,
    repeat: persisted.repeat,
    liked: [],
    disliked: [],
    reasons: persisted.reasons,
    mood: sessionStorage.getItem("moodwave.mood"),
    moodMode: (sessionStorage.getItem("moodwave.moodMode") as "match" | "shift") || "match",
    playbackNote: null,

    boot: async () => {
      try {
        const library = await api.library();
        let profile: Taste | null = null;
        try {
          profile = await api.taste();
        } catch (error) {
          if (!(error instanceof ApiError) || error.status !== 404) throw error;
        }
        const byId = new Map(library.tracks.map((track) => [track.id, track]));
        const saved = loadPersisted();
        const queue = saved.queueIds.map((id) => byId.get(id)).filter((track): track is Track => Boolean(track));
        set({
          ready: true,
          offline: null,
          profile,
          catalog: library.tracks,
          liked: library.liked.map((track) => track.id),
          disliked: library.disliked,
          queue,
          index: Math.min(saved.index, Math.max(0, queue.length - 1)),
          reasons: saved.reasons ?? {},
        });
      } catch (error) {
        set({
          ready: true,
          offline: error instanceof Error ? error.message : "The recommendation service is not running.",
        });
      }
    },

    refreshProfile: async () => {
      const profile = await api.taste();
      const library = await api.library();
      set({
        profile,
        liked: library.liked.map((track) => track.id),
        disliked: library.disliked,
        catalog: library.tracks,
      });
    },

    setProfile: (profile) => set({ profile }),

    playTrack: async (track, queue, reason) => {
      const state = get();
      const current = state.queue[state.index];
      if (current && state.playing) await flush(current, state.positionMs, "play");
      const nextQueue = queue && queue.length ? queue : [track, ...state.queue.filter((item) => item.id !== track.id)];
      const index = Math.max(0, nextQueue.findIndex((item) => item.id === track.id));
      const reasons = { ...state.reasons };
      if (Array.isArray(reason)) reasons[track.id] = reason;
      else if (reason) Object.assign(reasons, reason);
      set({ queue: nextQueue, index, positionMs: 0, reasons });
      persist();
      await begin(track, 0);
    },

    toggle: async () => {
      const state = get();
      const track = state.queue[state.index];
      if (!track) return;
      if (track.preview === "embed") {
        set({ playing: !state.playing });
        return;
      }
      if (!canPlay(track)) return;
      if (state.playing) {
        const position = preview.pause();
        set({ playing: false, positionMs: position });
        return;
      }
      await begin(track, state.positionMs);
    },

    next: async (reason = "skip") => {
      const state = get();
      const current = state.queue[state.index];
      await flush(current, preview.position() || state.positionMs, reason);
      if (!state.queue.length) return;
      if (state.repeat === "one" && reason === "ended" && current) {
        set({ positionMs: 0 });
        await begin(current, 0);
        return;
      }
      let index = state.index + 1;
      if (index >= state.queue.length) {
        if (state.repeat === "all") index = 0;
        else {
          preview.pause();
          set({ playing: false, positionMs: 0, index: state.queue.length - 1 });
          persist();
          return;
        }
      }
      const track = state.queue[index];
      set({ index, positionMs: 0 });
      persist();
      await begin(track, 0);
    },

    prev: async () => {
      const state = get();
      const position = preview.position();
      if (position > 3000) {
        await get().seek(0);
        return;
      }
      const index = Math.max(0, state.index - 1);
      const track = state.queue[index];
      if (!track) return;
      set({ index, positionMs: 0 });
      persist();
      await begin(track, 0);
    },

    seek: async (ms) => {
      const state = get();
      const track = state.queue[state.index];
      if (!track || track.preview === "embed" || track.preview === "unavailable") return;
      const limit = track.duration_ms || track.song_duration_ms || 0;
      const clamped = Math.max(0, Math.min(ms, limit));
      set({ positionMs: clamped });
      if (state.playing) {
        await begin(track, clamped);
      } else {
        preview.pause();
        set({ positionMs: clamped });
      }
    },

    setVolume: (value) => {
      preview.setVolume(value);
      set({ volume: value });
      persist();
    },

    toggleShuffle: () => {
      const state = get();
      if (!state.shuffle) {
        const head = state.queue.slice(0, state.index + 1);
        const tail = state.queue.slice(state.index + 1);
        for (let i = tail.length - 1; i > 0; i -= 1) {
          const j = Math.floor(Math.random() * (i + 1));
          [tail[i], tail[j]] = [tail[j], tail[i]];
        }
        set({ shuffle: true, queue: [...head, ...tail] });
      } else {
        set({ shuffle: false });
      }
      persist();
    },

    cycleRepeat: () => {
      const order: RepeatMode[] = ["off", "all", "one"];
      const next = order[(order.indexOf(get().repeat) + 1) % order.length];
      set({ repeat: next });
      persist();
    },

    enqueue: (track) => {
      const state = get();
      if (state.queue.some((item) => item.id === track.id)) return;
      set({ queue: [...state.queue, track] });
      persist();
    },

    setQueue: (tracks) => {
      const state = get();
      const current = state.queue[state.index];
      const found = current ? tracks.findIndex((item) => item.id === current.id) : 0;
      set({ queue: tracks, index: found >= 0 ? found : 0 });
      persist();
    },

    removeAt: (index) => {
      const state = get();
      const queue = state.queue.filter((_, item) => item !== index);
      let nextIndex = state.index;
      if (index < state.index) nextIndex -= 1;
      if (nextIndex >= queue.length) nextIndex = Math.max(0, queue.length - 1);
      const removedCurrent = index === state.index;
      set({ queue, index: nextIndex, playing: removedCurrent ? false : state.playing, positionMs: removedCurrent ? 0 : state.positionMs });
      if (removedCurrent) preview.pause();
      persist();
    },

    move: (from, to) => {
      const state = get();
      if (to < 0 || to >= state.queue.length || from === to) return;
      const queue = [...state.queue];
      const [item] = queue.splice(from, 1);
      queue.splice(to, 0, item);
      let index = state.index;
      if (from === index) index = to;
      else if (from < index && to >= index) index -= 1;
      else if (from > index && to <= index) index += 1;
      set({ queue, index });
      persist();
    },

    clearQueue: () => {
      preview.pause();
      set({ queue: [], index: 0, playing: false, positionMs: 0 });
      persist();
    },

    replaceQueue: async (tracks, reasons) => {
      if (!tracks.length) return;
      await get().playTrack(tracks[0], tracks, reasons?.[tracks[0].id]);
      if (reasons) set({ reasons: { ...get().reasons, ...reasons } });
    },

    toggleLike: async (track) => {
      const liked = get().liked.includes(track.id);
      const taste = await api.react(track.id, liked ? "none" : "like");
      const library = await api.library();
      set({ profile: taste, liked: library.liked.map((item) => item.id), disliked: library.disliked });
    },

    toggleDislike: async (track) => {
      const disliked = get().disliked.includes(track.id);
      const taste = await api.react(track.id, disliked ? "none" : "dislike");
      const library = await api.library();
      set({ profile: taste, liked: library.liked.map((item) => item.id), disliked: library.disliked });
    },

    setMood: (mood, mode) => {
      const moodMode = mode ?? get().moodMode;
      if (mood) sessionStorage.setItem("moodwave.mood", mood);
      else sessionStorage.removeItem("moodwave.mood");
      sessionStorage.setItem("moodwave.moodMode", moodMode);
      set({ mood, moodMode });
    },

    tick: () => {
      if (!get().playing) return;
      set({ positionMs: preview.position() });
    },
  };
});
