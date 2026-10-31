"""Runtime configuration. Paths come from the environment, never from request bodies."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _location(value: str | None) -> str:
    code = (value or "IN").strip().upper()
    if len(code) == 2 and code.isalpha():
        return code
    return "IN"


def _load_env_file(path: Path) -> None:
    """Fill unset variables from a local env file. Existing process env wins."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    seed: int = 42
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8000
    catalog_csv: Path | None = None
    interactions_json: Path | None = None
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_market: str = "IN"
    ytmusic_location: str = "IN"
    ytmusic_embed_check: bool = False
    catalog_source: str = "demo"
    itunes_country: str = "US"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def audio_features_dir(self) -> Path:
        return self.data_dir / "audio_features"

    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "artifacts"

    @classmethod
    def from_env(cls) -> "Settings":
        # .env overrides the example file. Neither overrides variables already set.
        _load_env_file(BACKEND_ROOT / ".env")
        _load_env_file(BACKEND_ROOT / ".env.example")
        data_dir = Path(os.environ.get("MOODWAVE_DATA_DIR", BACKEND_ROOT / "data")).expanduser()
        if not data_dir.is_absolute():
            data_dir = (BACKEND_ROOT / data_dir).resolve()
        db_path = Path(os.environ.get("MOODWAVE_DB_PATH", data_dir / "moodwave.db")).expanduser()
        if not db_path.is_absolute():
            db_path = (BACKEND_ROOT / db_path).resolve()
        catalog = os.environ.get("MOODWAVE_CATALOG_CSV", "").strip()
        interactions = os.environ.get("MOODWAVE_INTERACTIONS_JSON", "").strip()
        market = os.environ.get("MOODWAVE_SPOTIFY_MARKET", "IN").strip().upper() or "IN"
        if len(market) != 2 or not market.isalpha():
            market = "IN"
        source = os.environ.get("MOODWAVE_CATALOG_SOURCE", "itunes").strip().lower()
        if source not in {"itunes", "demo"}:
            source = "itunes"
        itunes_country = os.environ.get("MOODWAVE_ITUNES_COUNTRY", "US").strip().upper() or "US"
        if len(itunes_country) != 2 or not itunes_country.isalpha():
            itunes_country = "US"
        embed_check = os.environ.get("MOODWAVE_YTMUSIC_EMBED_CHECK", "1").strip().lower() not in {"0", "false", "no", "off"}
        return cls(
            data_dir=data_dir,
            db_path=db_path,
            seed=int(os.environ.get("MOODWAVE_SEED", "42")),
            log_level=os.environ.get("MOODWAVE_LOG_LEVEL", "INFO"),
            host=os.environ.get("MOODWAVE_HOST", "127.0.0.1"),
            port=int(os.environ.get("MOODWAVE_PORT", "8000")),
            catalog_csv=Path(catalog).expanduser() if catalog else None,
            interactions_json=Path(interactions).expanduser() if interactions else None,
            spotify_client_id=os.environ.get("MOODWAVE_SPOTIFY_CLIENT_ID", os.environ.get("SPOTIFY_CLIENT_ID", "")).strip(),
            spotify_client_secret=os.environ.get("MOODWAVE_SPOTIFY_CLIENT_SECRET", os.environ.get("SPOTIFY_CLIENT_SECRET", "")).strip(),
            spotify_market=market,
            ytmusic_location=_location(os.environ.get("MOODWAVE_YTMUSIC_LOCATION", "IN")),
            ytmusic_embed_check=embed_check,
            catalog_source=source,
            itunes_country=itunes_country,
        )
