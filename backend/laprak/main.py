from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import get_settings
from .db import init_db
from .routers import ai, ai_profiles, auth, builds, files, projects, steps, templates

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Laprak", version="2.0.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    # Authlib keeps the OAuth state in this cookie session; the login session itself is a separate signed cookie.
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, session_cookie="laprak_oauth", same_site="lax",
                       https_only=settings.cookie_secure, max_age=600)
    for router in (auth.router, projects.router, steps.router, templates.router, ai_profiles.router, ai.router, builds.router, files.router):
        app.include_router(router, prefix="/api")

    @app.exception_handler(ValueError)
    async def _value_error(_request: Request, error: ValueError):
        return JSONResponse({"detail": str(error)}, status_code=422)

    @app.get("/api/health")
    def health():
        return {"ok": True, "dev_login": settings.dev_login, "google": bool(settings.google_client_id)}

    if FRONTEND_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            candidate = FRONTEND_DIST / path
            if path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")
    return app


app = create_app()
