"""FastAPI application: REST API for the UI, AG-UI for the chatbot, background MAF workflows."""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import (
    JSONResponse,
)
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend import config
from backend import db as database
from backend.api import ROUTERS
from backend.core import auth, documents, files, gates, logs, models, prompts
from backend.core.errors import AqeError, classify, stack_of
from backend.core.security import install_log_mask, redact, PathEscape
from backend.db import new_id
from backend.maf import agui, engine, evals, governance, llm, workflows  # noqa: F401 - workflows registers definitions
from backend.repos import git, github, ingest


install_log_mask()
logs.install()
log = logging.getLogger("aqe.api")
request_log = logging.getLogger("aqe.request")


def fail(request: Request | None, status: int, message: str, *, code: str | None = None, action: str = "", detail=None) -> JSONResponse:
    """The one error shape: code, message, action, error_id. `detail` stays for older clients."""
    error_id = new_id("err")
    request_id = getattr(request.state, "request_id", "") if request else ""
    message = redact(message)
    if status >= 500 or code:
        log.error("request %s answered %s %s error_id=%s %s", request_id, status, code or "", error_id, message, extra={"fields": {"request_id": request_id, "error_id": error_id, "status": status, "code": code}})
    body = {"code": code, "message": message, "action": action, "error_id": error_id, "detail": message if detail is None else detail}
    return JSONResponse(body, status_code=status, headers={"X-Request-Id": request_id} if request_id else None)


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.migrate()
    prompts.seed()
    files.seed_templates()
    models.seed_from_config(llm.current()["model"])
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
        return fail(request, 401, "Sign in first", action="Sign in again.")
    if refusal := auth.access_problem(request.method, path, user):
        return fail(request, refusal[0], refusal[1])
    auth.current_user.set(user)
    request.state.user_id = user["id"]
    return await call_next(request)


@app.middleware("http")
async def origin_guard(request: Request, call_next):
    """Block browser cross-site writes and DNS rebinding against this loopback service."""
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in config.ALLOWED_ORIGINS:
        return fail(request, 403, "Origin not allowed")
    host = request.headers.get("host", "").rsplit(":", 1)[0].strip("[]")
    allowed = {"localhost", "127.0.0.1", "::1", "testserver", *(h.strip() for h in os.environ.get("ATLAS_ALLOWED_HOSTS", "").split(",") if h.strip())}
    if host not in allowed:
        return fail(request, 403, "Host not allowed")
    return await call_next(request)


@app.middleware("http")
async def request_id(request: Request, call_next):
    """Outermost: every response, including a refusal by a guard, carries the id that links it to the logs."""
    request.state.request_id = new_id("req")
    started, status = time.perf_counter(), 500
    try:
        response = await call_next(request)
        status = response.status_code
    finally:
        if request.url.path.startswith(("/api/", "/agui/")):  # path only: never the query string, body, or cookies
            request_log.info("request", extra={"fields": {"request_id": request.state.request_id, "method": request.method, "path": request.url.path, "status": status,
                                                          "duration_ms": round((time.perf_counter() - started) * 1000), "user_id": getattr(request.state, "user_id", "")}})
    response.headers["X-Request-Id"] = request.state.request_id
    return response


STATUS = {"AQE-ALLOW-001": 403, "AQE-ALLOW-002": 429, "AQE-MODEL-006": 502, "AQE-MODEL-004": 504, "AQE-REPO-001": 400}
HINT = {401: "Sign in again.", 403: "Ask your administrator.", 404: "Check the address, or refresh the page.", 409: "Wait for the current action to finish, then try again.", 412: "Open Settings and finish the setup.", 413: "Use a smaller file."}


@app.exception_handler(AqeError)
async def typed_failure(request: Request, exc: AqeError):
    status = 409 if isinstance(exc, governance.AgentDisabled) else 412 if isinstance(exc, llm.LLMNotConfigured) else STATUS.get(exc.code, 500 if exc.code == "AQE-INT-001" else 422)
    return fail(request, status, exc.message, code=exc.code, action=exc.action)


@app.exception_handler(auth.Forbidden)
async def forbidden(request: Request, exc: auth.Forbidden):
    return fail(request, 403, str(exc), action="Ask your administrator or the project owner.")


@app.exception_handler(StarletteHTTPException)
async def http_failure(request: Request, exc: StarletteHTTPException):
    return fail(request, exc.status_code, str(exc.detail), action=HINT.get(exc.status_code, "Check the request and try again."), detail=exc.detail)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    fields = "; ".join(f"{'.'.join(str(p) for p in e['loc'] if p != 'body')}: {e['msg']}" for e in exc.errors()[:5])
    return fail(request, 422, f"The request is not valid: {fields}", action="Fix the fields named and send it again.", detail=jsonable_errors(exc))


def jsonable_errors(exc: RequestValidationError) -> list:
    return [{k: v for k, v in e.items() if k in {"loc", "msg", "type"}} for e in exc.errors()]


@app.exception_handler(KeyError)
async def not_found(request: Request, exc: KeyError):
    return fail(request, 404, f"Not found: {exc.args[0] if exc.args else ''}", action=HINT[404])


def _bad_request(request: Request, exc: Exception):
    error = classify(exc) if isinstance(exc, AqeError) else None
    return fail(request, 400, str(exc), code=error.code if error else None, action=error.action if error else "Check the request and try again.")


for _error in (documents.DocumentError, files.UnsupportedFile, ingest.IngestError, git.GitError, github.GitHubError, gates.GateOrderError, PathEscape):
    app.add_exception_handler(_error, _bad_request)


@app.exception_handler(Exception)
async def unexpected(request: Request, exc: Exception):
    """A bug in this application. The reply names an id, and the log holds the redacted stack under it."""
    error = classify(exc)
    response = fail(request, 500, error.message, code=error.code, action=error.action)
    log.error("unexpected failure on %s %s: %s", request.method, request.url.path, stack_of(exc), extra={"fields": {"request_id": getattr(request.state, "request_id", ""), "error_id": json.loads(response.body)["error_id"]}})
    response.headers["X-Request-Id"] = getattr(request.state, "request_id", "")
    return response


@app.get("/api/health")
def health():
    """Doctor: what this machine can actually run."""
    return {"status": "ok", "llm": llm.public()["configured"], "git": bool(shutil.which("git")), "node": bool(shutil.which("node")), "npx": bool(shutil.which("npx")), "ruff": bool(shutil.which("ruff") or shutil.which("ruff", path=str(Path(sys.executable).parent)))}
