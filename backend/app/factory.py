"""Application factory. Tests build an app with a temporary data directory."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import Settings
from app.services.engine import Engine, EngineError

_LOCAL_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
)
_PAGES_ORIGIN = "https://ankitmallick800.github.io"


def cors_origins() -> list[str]:
    origins = [*_LOCAL_ORIGINS, _PAGES_ORIGIN]
    extra = os.environ.get("MOODWAVE_CORS_ORIGINS", "")
    for item in extra.split(","):
        origin = item.strip().rstrip("/")
        if origin.startswith(("http://", "https://")) and origin not in origins:
            origins.append(origin)
    return origins


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    recommender = Engine(settings)
    recommender.startup()
    app = FastAPI(
        title="MOODWAVE",
        version="1.0.0",
        summary="Explainable music ranking, taste learning, and mood-aware playback.",
    )
    app.state.engine = recommender
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def service_root() -> dict[str, str]:
        return {"service": "MOODWAVE", "health": "/api/health", "docs": "/docs"}

    @app.exception_handler(EngineError)
    async def handle_engine_error(_request: Request, exc: EngineError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"error": "request_error", "detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "detail": _safe_validation(exc)},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("moodwave.api").exception("Unhandled error")
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "detail": "The request could not be completed."},
        )

    return app


def _safe_validation(exc: RequestValidationError) -> str:
    parts = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error.get("loc", []) if item != "body")
        parts.append(f"{location}: {error.get('msg', 'invalid')}" if location else error.get("msg", "invalid"))
    return "; ".join(parts) or "Invalid request."
