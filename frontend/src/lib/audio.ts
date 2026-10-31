import type { Track } from "../types";

/**
 * Plays a shipped recording when the track has one.
 * Tracks without a file fall back to a tone built from catalog metadata.
 */
export class PreviewEngine {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private nodes: AudioScheduledSourceNode[] = [];
  private file: HTMLAudioElement | null = null;
  private mode: "file" | "tone" | "idle" = "idle";
  private running = false;
  private offset = 0;
  private started = 0;
  private duration = 0;
  private timer = 0;
  private onEnded = () => {};
  private volume = 0.8;
  private token = 0;

  position(): number {
    if (this.mode === "file" && this.file) {
      return Math.min(this.duration, this.file.currentTime * 1000);
    }
    if (!this.running) return this.offset;
    return Math.min(this.duration, this.offset + (performance.now() - this.started));
  }

  setVolume(value: number): void {
    this.volume = value;
    if (this.file) this.file.volume = this.fileLevel();
    if (this.master && this.ctx) {
      this.master.gain.setTargetAtTime(this.toneLevel(), this.ctx.currentTime, 0.03);
    }
  }

  private fileLevel(): number {
    return Math.max(0, Math.min(1, this.volume));
  }

  private toneLevel(): number {
    return this.fileLevel() * 0.2;
  }

  private async context(): Promise<AudioContext> {
    if (!this.ctx) {
      const ctx = new AudioContext();
      const master = ctx.createGain();
      master.gain.value = this.toneLevel();
      master.connect(ctx.destination);
      this.ctx = ctx;
      this.master = master;
    }
    if (this.ctx.state === "suspended") await this.ctx.resume();
    return this.ctx;
  }

  private stopTone(): void {
    this.nodes.forEach((node) => {
      try {
        node.stop();
      } catch {
        /* already stopped */
      }
      try {
        node.disconnect();
      } catch {
        /* already disconnected */
      }
    });
    this.nodes = [];
    window.clearInterval(this.timer);
  }

  private stopFile(): void {
    if (!this.file) return;
    this.file.onended = null;
    this.file.pause();
  }

  pause(): number {
    if (this.mode === "file" && this.file) {
      this.offset = this.file.currentTime * 1000;
      this.stopFile();
      this.running = false;
      return this.offset;
    }
    if (this.running) this.offset = this.position();
    this.stopTone();
    this.running = false;
    this.mode = "idle";
    return this.offset;
  }

  async play(
    track: Track,
    offsetMs: number,
    onEnded: () => void,
    onDuration?: (ms: number) => void,
  ): Promise<boolean> {
    const token = ++this.token;
    this.stopTone();
    this.stopFile();
    this.onEnded = onEnded;
    const report = onDuration ?? (() => {});
    if (track.audio_url && track.preview !== "embed" && track.preview !== "unavailable") {
      try {
        await this.playFile(track.audio_url, offsetMs, track.duration_ms, token, report);
        return true;
      } catch {
        if (token !== this.token) return false;
        this.stopFile();
      }
    }
    const blocksTone =
      Boolean(track.provider && track.provider !== "demo") ||
      track.preview === "preview" ||
      track.preview === "full" ||
      track.preview === "embed" ||
      track.preview === "unavailable" ||
      track.preview === "spotify-preview";
    if (token !== this.token || blocksTone) {
      this.running = false;
      this.mode = "idle";
      return false;
    }
    await this.playTone(track, offsetMs);
    return true;
  }

  private media(): HTMLAudioElement {
    if (!this.file) {
      const audio = new Audio();
      audio.preload = "auto";
      this.file = audio;
    }
    return this.file;
  }

  private async playFile(
    url: string,
    offsetMs: number,
    fallbackDuration: number,
    token: number,
    report: (ms: number) => void,
  ): Promise<void> {
    const audio = this.media();
    const absolute = new URL(url, window.location.origin).href;
    if (audio.src !== absolute) {
      audio.src = absolute;
      await new Promise<void>((resolve, reject) => {
        const finish = (failed: boolean) => {
          audio.removeEventListener("loadedmetadata", ready);
          audio.removeEventListener("error", failedLoad);
          if (failed) reject(new Error("Could not load the recording."));
          else resolve();
        };
        const ready = () => finish(false);
        const failedLoad = () => finish(true);
        audio.addEventListener("loadedmetadata", ready);
        audio.addEventListener("error", failedLoad);
        audio.load();
      });
    }
    if (token !== this.token) return;
    const durationMs = Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration * 1000 : fallbackDuration;
    const offset = Math.min(Math.max(0, offsetMs), Math.max(0, durationMs - 250));
    audio.currentTime = offset / 1000;
    audio.volume = this.fileLevel();
    this.mode = "file";
    this.running = true;
    this.duration = durationMs;
    this.offset = offset;
    report(durationMs);
    this.started = performance.now();
    audio.onended = () => {
      if (this.mode !== "file" || token !== this.token) return;
      this.running = false;
      this.offset = this.duration;
      this.onEnded();
    };
    await audio.play();
  }

  private async playTone(track: Track, offsetMs: number): Promise<void> {
    const ctx = await this.context();
    this.mode = "tone";
    this.offset = Math.min(Math.max(0, offsetMs), track.duration_ms);
    this.duration = track.duration_ms;
    this.started = performance.now();
    this.running = true;
    this.buildTone(ctx, track);
    this.timer = window.setInterval(() => {
      if (this.mode !== "tone" || !this.running) return;
      if (this.position() >= this.duration - 40) {
        this.stopTone();
        this.running = false;
        this.offset = this.duration;
        this.onEnded();
      }
    }, 200);
  }

  private buildTone(ctx: AudioContext, track: Track): void {
    if (!this.master) return;
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    const energy = track.energy ?? 0.4;
    filter.frequency.value = 380 + energy * 3200;
    filter.Q.value = 0.65;
    filter.connect(this.master);

    const key = track.musical_key ?? 0;
    const third = track.mode === 0 ? 3 : 4;
    const intervals = [0, third, 7];
    const gains = [0.085, 0.045, 0.035];
    const types: OscillatorType[] = ["sine", "triangle", "sine"];
    intervals.forEach((interval, index) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      const midi = 57 + ((key + interval) % 12);
      osc.type = types[index];
      osc.frequency.value = 440 * 2 ** ((midi - 69) / 12);
      osc.detune.value = index === 1 ? 7 : 0;
      gain.gain.value = gains[index] * (0.5 + energy * 0.7);
      osc.connect(gain);
      gain.connect(filter);
      osc.start();
      this.nodes.push(osc);
    });

    const lfo = ctx.createOscillator();
    const depth = ctx.createGain();
    const tempo = track.tempo ?? 96;
    lfo.frequency.value = Math.max(0.35, tempo / 60);
    depth.gain.value = 0.012 + (track.danceability ?? 0.4) * 0.035;
    lfo.connect(depth);
    depth.connect(this.master.gain);
    lfo.start();
    this.nodes.push(lfo);
  }
}

export const preview = new PreviewEngine();
