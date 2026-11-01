"""Projects API."""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import (
    Response,
)
from pydantic import BaseModel, Field

from backend.api.common import _project
from backend.config import project_dir
from backend.core import documents, gates, ledger
from backend.db import db, new_id, now, rows
from backend.maf import agui, engine, evals, governance, llm, workflows  # noqa: F401 - workflows registers definitions
from backend.repos import ingest

router = APIRouter()


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    archived: bool | None = None


def _project_summary(item: dict) -> dict:
    with db() as con:
        counts = con.execute(
            """SELECT (SELECT COUNT(*) FROM documents WHERE project_id=:p) AS documents,
                      (SELECT COUNT(*) FROM runs WHERE project_id=:p) AS runs,
                      (SELECT COUNT(*) FROM findings WHERE project_id=:p AND status='open') AS findings,
                      (SELECT COUNT(*) FROM approvals WHERE project_id=:p AND status='pending') AS pending,
                      (SELECT COUNT(*) FROM gates WHERE project_id=:p AND status='approved') AS gates_approved""",
            {"p": item["id"]},
        ).fetchone()
        repo = con.execute("SELECT kind, url, commit_sha, analysis FROM repo_sources WHERE project_id=?", (item["id"],)).fetchone()
    analysis = json.loads(repo["analysis"]) if repo else {}
    return {**item, **dict(counts), "archived": bool(item["archived"]),
            "repo": {"kind": repo["kind"], "url": repo["url"], "commit": repo["commit_sha"][:10], "languages": list(analysis.get("languages", {}))[:4]} if repo else None}


@router.get("/api/projects")
def list_projects(archived: bool = False):
    with db() as con:
        items = rows(con.execute("SELECT * FROM projects WHERE archived=? AND id!='prj_agent_evals' ORDER BY updated_at DESC", (int(archived),)))
    return [_project_summary(i) for i in items]


@router.post("/api/projects", status_code=201)
def create_project(body: ProjectIn):
    item = {"id": new_id("prj"), "name": body.name.strip(), "description": body.description.strip(), "created_at": now(), "updated_at": now()}
    with db() as con:
        con.execute("INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (:id,:name,:description,:created_at,:updated_at)", item)
    ledger.append(item["id"], "user", "project.created", item["id"], {"name": item["name"]})
    return _project_summary(_project(item["id"]))


@router.get("/api/projects/{project_id}")
def get_project(project_id: str):
    return _project_summary(_project(project_id))


@router.patch("/api/projects/{project_id}")
def patch_project(project_id: str, body: ProjectPatch):
    current = _project(project_id)
    with db() as con:
        con.execute("UPDATE projects SET name=?, description=?, archived=?, updated_at=? WHERE id=?",
                    (body.name or current["name"], current["description"] if body.description is None else body.description,
                     current["archived"] if body.archived is None else int(body.archived), now(), project_id))
    return get_project(project_id)


@router.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: str):
    _project(project_id)
    with db() as con:
        con.execute("DELETE FROM projects WHERE id=?", (project_id,))
    ingest._rm_tree(project_dir(project_id))
    return Response(status_code=204)


@router.get("/api/projects/{project_id}/overview")
def overview(project_id: str):
    with db() as con:
        pending = rows(con.execute("SELECT id, run_id, gate, title, summary, created_at FROM approvals WHERE project_id=? AND status='pending' ORDER BY created_at", (project_id,)))
        latest = rows(con.execute("SELECT id, workflow, status, started_at, ended_at, error FROM runs WHERE project_id=? ORDER BY started_at DESC LIMIT 6", (project_id,)))
    repo = ingest.get(project_id)
    return {"project": get_project(project_id), "gates": gates.status(project_id), "pending_approvals": pending, "recent_runs": latest,
            "documents": documents.list_for(project_id)[:8], "repo": {k: repo[k] for k in ("kind", "url", "commit_sha", "scanned_at")} | {"analysis": {k: repo["analysis"].get(k) for k in ("mode", "languages", "frameworks", "test_runners", "total_files", "test_file_count")}} if repo else None}
