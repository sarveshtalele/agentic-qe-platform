"""Workflows API."""
from __future__ import annotations

import asyncio
import io
import json
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import (
    Response,
    StreamingResponse,
)
from pydantic import BaseModel, Field

from backend.api.common import _project
from backend.api.documents import ActorIn
from backend.core import ledger
from backend.core.security import safe_path
from backend.db import db, rows
from backend.maf import agui, engine, evals, governance, llm, workflows  # noqa: F401 - workflows registers definitions
from backend.repos import git, github, ingest

router = APIRouter()


class RunIn(BaseModel):
    workflow: str
    input: dict = Field(default_factory=dict)


class DecisionIn(BaseModel):
    approved: bool
    by: str
    feedback: str = ""
    open_pr: bool = False


@router.post("/api/projects/{project_id}/runs", status_code=201)
async def start_run(project_id: str, body: RunIn):
    _project(project_id)
    try:
        return await engine.start(project_id, body.workflow, body.input)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/projects/{project_id}/runs")
def list_runs(project_id: str):
    with db() as con:
        return rows(con.execute("SELECT id, workflow, status, error, tokens_in, tokens_out, started_at, ended_at FROM runs WHERE project_id=? ORDER BY started_at DESC LIMIT 100", (project_id,)))


@router.get("/api/runs/{run_id}")
def get_run(run_id: str):
    return engine.get(run_id)


@router.get("/api/runs/{run_id}/events")
async def stream_events(run_id: str, request: Request, after: int = 0):
    engine.get(run_id)

    async def generator():
        last = after
        idle = 0
        while not await request.is_disconnected():
            items = engine.events(run_id, last)
            for item in items:
                last = item["seq"]
                yield f"id: {last}\nevent: run\ndata: {json.dumps(item)}\n\n"
            status = engine.get(run_id)["status"]
            if not items and status in {"completed", "failed", "rejected", "cancelled", "interrupted", "waiting_approval"}:
                yield f"event: end\ndata: {json.dumps({'status': status})}\n\n"
                return
            idle = 0 if items else idle + 1
            if idle and idle % 30 == 0:
                yield ": keepalive\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/api/runs/{run_id}/cancel")
def cancel_run(run_id: str):
    try:
        return engine.cancel(run_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/approvals")
def all_approvals():
    """Everything waiting on a human, across all active projects."""
    with db() as con:
        items = rows(con.execute(
            """SELECT a.*, p.name AS project_name, r.workflow FROM approvals a JOIN projects p ON p.id=a.project_id JOIN runs r ON r.id=a.run_id
               WHERE a.status='pending' AND p.archived=0 ORDER BY a.created_at DESC"""))
    return [{**a, "payload": json.loads(a["payload"])} for a in items]


@router.get("/api/runs/{run_id}/changes.zip")
def changes_zip(run_id: str):
    """The files a change or QE run touched, read from its branch worktree."""
    state = engine.get(run_id)["state"]
    if not state.get("worktree"):
        raise HTTPException(400, "This run has no code changes")
    root = Path(state["worktree"])
    if not root.exists():
        raise HTTPException(410, "The worktree for this run no longer exists")
    changed = git.run(["diff", "--name-only", "--diff-filter=d", "HEAD~1" if state.get("commit") or state.get("test_commit") else "HEAD"], cwd=root, check=False).splitlines()
    changed += git.run(["ls-files", "--others", "--exclude-standard"], cwd=root, check=False).splitlines()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in sorted(set(changed)):
            target = safe_path(root, name)
            if target.is_file():
                bundle.write(target, name)
    return Response(buffer.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="changes-{run_id[-6:]}.zip"'})


@router.post("/api/runs/{run_id}/merge-pr")
async def merge_pr(run_id: str, body: ActorIn):
    run = engine.get(run_id)
    pr = run["state"].get("pull_request")
    repo = ingest.get(run["project_id"])
    if not pr or not repo or not repo["credential_id"]:
        raise HTTPException(400, "This run has no pull request to merge")
    owner, name = github.parse_slug(repo["url"])
    result = await github.merge_pr(github.token_for(repo["credential_id"]), owner, name, pr["number"])
    ledger.append(run["project_id"], body.by, "pull_request.merged", pr["url"], result)
    return result


@router.post("/api/approvals/{approval_id}/decide")
async def decide(approval_id: str, body: DecisionIn):
    try:
        return await engine.decide(approval_id, body.approved, body.by, body.feedback, {"open_pr": body.open_pr})
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
