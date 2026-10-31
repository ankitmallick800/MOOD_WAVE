"""Fit the demo models and write a small artifact summary.

    python scripts/train.py

The live server fits the same models on startup. This script is the reproducible
training entry point: same seed, same catalog, same synthetic generator.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config import Settings  # noqa: E402
from app.services.engine import Engine  # noqa: E402


def main() -> None:
    settings = Settings.from_env()
    engine = Engine(settings)
    engine.startup()
    summary = {
        "seed": settings.seed,
        "tracks": len(engine.tracks),
        "synthetic_events": len(engine.events),
        "feature_source": engine.tracks[0].feature_source if engine.tracks else None,
        "clusters": {
            "k": engine.clusters.get("k"),
            "silhouette": engine.clusters.get("silhouette"),
            "available": engine.clusters.get("available"),
        },
        "artifact": str(settings.artifacts_dir / "popularity.joblib"),
    }
    destination = settings.artifacts_dir / "train_summary.json"
    destination.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
