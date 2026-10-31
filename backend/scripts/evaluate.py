"""Run the temporal-holdout evaluation and print the warning plus metric means.

    python scripts/evaluate.py
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
    engine = Engine(Settings.from_env())
    engine.startup()
    result = engine.evaluate(k=10, diversify=False, include_svd=False)
    compact = {
        "warning": result["warning"],
        "suppressed": result["suppressed"],
        "meaningful_as_real_world": result["meaningful_as_real_world"],
        "dataset": result["dataset"],
        "models": [
            {
                "strategy": model["strategy"],
                "n_users": model["n_users"],
                "metrics": model["metrics"],
                "coverage": model["coverage"],
            }
            for model in result["models"]
        ],
    }
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
