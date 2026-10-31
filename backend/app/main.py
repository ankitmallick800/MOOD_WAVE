"""Uvicorn entrypoint: `uvicorn app.main:app --app-dir backend`."""

from __future__ import annotations

import uvicorn

from app.config import Settings
from app.factory import create_app

app = create_app()


def main() -> None:
    settings = app.state.settings if isinstance(app.state.settings, Settings) else Settings.from_env()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
