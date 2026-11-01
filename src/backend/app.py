"""FastAPI application: REST API for the UI, AG-UI for the chatbot, background MAF workflows."""
from __future__ import annotations

import os
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import (
    JSONResponse,
)

from backend import config
from backend import db as database
from backend.api import ROUTERS
from backend.core import auth, documents, files, gates, prompts
from backend.core.security import install_log_mask, PathEscape
from backend.maf import agui, engine, evals, governance, llm, workflows  # noqa: F401 - workflows registers definitions
from backend.repos import git, github, ingest


install_log_mask()


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.migrate()
    prompts.seed()
    files.seed_templates()
    engine.recover()
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from agent_framework.observability import configure_otel_providers

        configure_otel_providers()
    yield


app = FastAPI(title="Agentic QE Platform", version="2.0.0", lifespan=lifespan)
app.include_router(agui.router)
for _router in ROUTERS:
    app.include_router(_router)


PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/api/auth/status"}


@app.middleware("http")
async def session_guard(request: Request, call_next):
    """Deny by default: every API and chat path needs a session, and then access to the item it names."""
    path = request.url.path
    if path in PUBLIC_PATHS or not path.startswith(("/api/", "/agui/")):
        return await call_next(request)
    user = auth.session_user(request.cookies.get(auth.COOKIE))
    if not user:
        return JSONResponse({"detail": "Sign in first"}, status_code=401)
    if status := auth.access_problem(request.method, path, user):
        return JSONResponse({"detail": "Only an administrator can do this" if status == 403 else "Not found"}, status_code=status)
    auth.current_user.set(user)
    return await call_next(request)


@app.middleware("http")
async def origin_guard(request: Request, call_next):
    """Block browser cross-site writes and DNS rebinding against this loopback service."""
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in config.ALLOWED_ORIGINS:
        return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
    host = request.headers.get("host", "").rsplit(":", 1)[0].strip("[]")
    allowed = {"localhost", "127.0.0.1", "::1", "testserver", *(h.strip() for h in os.environ.get("ATLAS_ALLOWED_HOSTS", "").split(",") if h.strip())}
    if host not in allowed:
        return JSONResponse({"detail": "Host not allowed"}, status_code=403)
    return await call_next(request)


@app.exception_handler(KeyError)
async def not_found(_: Request, exc: KeyError):
    return JSONResponse({"detail": f"Not found: {exc.args[0] if exc.args else ''}"}, status_code=404)


def _bad_request(_: Request, exc: Exception):
    return JSONResponse({"detail": str(exc)}, status_code=400)


for _error in (documents.DocumentError, files.UnsupportedFile, ingest.IngestError, git.GitError, github.GitHubError, gates.GateOrderError, PathEscape):
    app.add_exception_handler(_error, _bad_request)
app.add_exception_handler(governance.AgentDisabled, lambda _r, e: JSONResponse({"detail": str(e)}, status_code=409))
app.add_exception_handler(auth.AllowanceError, lambda _r, e: JSONResponse({"detail": str(e)}, status_code=403))
app.add_exception_handler(llm.LLMNotConfigured, lambda _r, e: JSONResponse({"detail": str(e)}, status_code=412))


@app.get("/api/health")
def health():
    """Doctor: what this machine can actually run."""
    return {"status": "ok", "llm": llm.public()["configured"], "git": bool(shutil.which("git")), "node": bool(shutil.which("node")), "npx": bool(shutil.which("npx")), "ruff": bool(shutil.which("ruff") or shutil.which("ruff", path=str(Path(sys.executable).parent)))}
