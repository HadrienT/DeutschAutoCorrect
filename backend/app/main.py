from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import recordings, rubrics
from .config import Settings, get_settings
from .context import AppContext, build_engines
from .db import Database
from .jobs import requeue_unfinished

FRONT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app(settings: Settings | None = None, ctx: AppContext | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        c = ctx
        if c is None:
            settings.data_dir.mkdir(parents=True, exist_ok=True)
            engines, notices = build_engines(settings)
            c = AppContext(settings, Database(settings.db_path), engines, notices)
        app.state.ctx = c
        requeue_unfinished(c)
        yield
        assert c.executor is not None
        c.executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="DeutschAutoCorrect", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","),
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(recordings.router)
    app.include_router(rubrics.router)

    @app.get("/api/health")
    def health() -> dict:
        c: AppContext = app.state.ctx
        e = c.engines
        return {"status": "ok", "engines": {
            "asr": e.asr.name, "corrector": e.corrector.name,
            "pronunciation": e.pronunciation.name if e.pronunciation else "désactivée"},
            "degraded": bool(c.notices) or e.asr.name == "mock", "notices": c.notices}

    if FRONT_DIST.exists():  # single-process deployment: serve the built SPA
        app.mount("/assets", StaticFiles(directory=FRONT_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            f = FRONT_DIST / path
            return FileResponse(f if path and f.is_file() else FRONT_DIST / "index.html")

    return app


logging.basicConfig(level=logging.INFO)
app = create_app()
