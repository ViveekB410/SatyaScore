"""Production entry point: the web app (web/dist) and the API on one origin.

    uvicorn member3_backend.serve:create_app --factory --host 0.0.0.0 --port 7860 \
        --proxy-headers --forwarded-allow-ips "*"

- /api/*  -> the FastAPI app in api.py (the web build calls the API at /api, as in dev:phone).
- /*      -> the built React app; unknown paths return index.html so client-side routes
             such as /account or /reset-password work on reload.

One origin means the session cookie is first-party and the auth origin check passes
without any cross-site setup. On Hugging Face Spaces, SPACE_HOST gives the public host
name; it becomes the allowed origin unless SATYASCORE_CORS_ORIGINS is set explicitly.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
DIST = Path(os.environ.get("SATYASCORE_WEB_DIST", ROOT / "web" / "dist"))


def allowed_origin_from_space(environ: dict) -> str | None:
    """https://<SPACE_HOST> on Hugging Face Spaces, else None."""
    host = environ.get("SPACE_HOST", "").strip()
    return f"https://{host}" if host else None


class SPAStaticFiles(StaticFiles):
    """Static files; a path that is not a file falls back to index.html (client-side routing)."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


def build_app(api_app, dist: Path) -> Starlette:
    """The API under /api and the web build at /. The API's startup handlers (model and
    index loading) run through this app's lifespan: Starlette does not run the lifespan
    of a mounted sub-application by itself."""

    @asynccontextmanager
    async def lifespan(_):
        async with api_app.router.lifespan_context(api_app):
            yield

    routes = [Mount("/api", app=api_app)]
    if (dist / "index.html").is_file():
        routes.append(Mount("/", app=SPAStaticFiles(directory=dist, html=True)))
    return Starlette(routes=routes, lifespan=lifespan)


def create_app() -> Starlette:
    """uvicorn --factory entry point. api.py is imported here, after the allowed origin
    is in the environment (api.py reads its settings at import time)."""
    if (origin := allowed_origin_from_space(os.environ)) and not os.environ.get("SATYASCORE_CORS_ORIGINS"):
        os.environ["SATYASCORE_CORS_ORIGINS"] = origin
    from member3_backend.api import app as api_app
    return build_app(api_app, DIST)
