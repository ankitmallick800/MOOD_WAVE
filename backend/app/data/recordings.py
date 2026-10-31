"""Public-domain recordings paired with demo catalog ids.

The files live in frontend/public/audio and are served by the web app.
They are CC0 pieces from the FreePD library. They are not performances of the
fictional catalog titles, and their audio was not used to fill feature fields.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).with_name("recordings.json")


@lru_cache(maxsize=1)
def recordings() -> dict[str, dict]:
    if not _PATH.is_file():
        return {}
    payload = json.loads(_PATH.read_text(encoding="utf-8"))
    rows = payload.get("tracks", {})
    return rows if isinstance(rows, dict) else {}


def playback_fields(track_id: str, duration_ms: int) -> dict:
    row = recordings().get(track_id)
    if not row:
        return {
            "duration_ms": duration_ms,
            "preview": "synthesized",
            "audio_url": None,
            "recording_title": None,
            "recording_license": None,
        }
    file_name = str(row["file"])
    if "/" in file_name or file_name.startswith("."):
        raise ValueError("Recording file name must stay inside the audio directory.")
    return {
        "duration_ms": int(row["duration_ms"]),
        "preview": "recording",
        "audio_url": f"/audio/{file_name}",
        "recording_title": row["title"],
        "recording_license": row["license"],
    }
