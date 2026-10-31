import { useEffect, useState } from "react";

import { api } from "../lib/api";
import type { LyricsResult, Track } from "../types";

export function Lyrics({ track }: { track: Track }) {
  const [lyrics, setLyrics] = useState<LyricsResult | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancel = false;
    setLyrics(null);
    setFailed(false);
    void api
      .lyrics(track.id)
      .then((result) => {
        if (!cancel) setLyrics(result);
      })
      .catch(() => {
        if (!cancel) setFailed(true);
      });
    return () => {
      cancel = true;
    };
  }, [track.id]);

  if (failed) {
    return <p className="text-sm text-mist">Lyrics could not be loaded.</p>;
  }
  if (!lyrics) {
    return <p className="text-sm text-mist">Looking up lyrics…</p>;
  }
  if (!lyrics.found || lyrics.instrumental) {
    return <p className="text-sm text-mist">{lyrics.message || "No lyrics on LRCLIB for this song."}</p>;
  }

  const text = lyrics.plain || lyrics.lines.map((line) => line.text).filter(Boolean).join("\n");

  return (
    <div>
      <div className="max-h-64 overflow-y-auto whitespace-pre-wrap pr-2 text-sm leading-6 text-mist">{text}</div>
      <p className="mt-2 text-[11px] text-mist/80">Lyrics from LRCLIB</p>
    </div>
  );
}
