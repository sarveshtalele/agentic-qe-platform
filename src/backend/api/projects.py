"""Projects API."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import (
    Response,
)
from pydantic import BaseModel, Field

from backend.api.common import _project
from backend.config import RUNS, project_dir
from backend.core import auth, documents, gates, ledger
from backend.core.security import safe_path
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
                      (SELECT COUNT(*) FROM findings WHERE project_id=:p AND status IN ('open','fix_attempted')) AS findings,
                      (SELECT COUNT(*) FROM approvals WHERE project_id=:p AND status='pending') AS pending,
                      (SELECT COUNT(*) FROM gates WHERE project_id=:p AND status='approved') AS gates_approved""",
            {"p": item["id"]},
        ).fetchone()
        repo = con.execute("SELECT kind, url, commit_sha, analysis FROM repo_sources WHERE project_id=?", (item["id"],)).fetchone()
    analysis = json.loads(repo["analysis"]) if repo else {}
    mine = auth.project_role(item["id"])
    can_sign = [g for g in range(6) if not auth.gate_signing_problem(item["id"], g)]
    return {**item, "my_role": mine, "can_write": auth.can_write(item["id"]), "can_sign": can_sign, **dict(counts), "archived": bool(item["archived"]),
            "repo": {"kind": repo["kind"], "url": repo["url"], "commit": repo["commit_sha"][:10], "languages": list(analysis.get("languages", {}))[:4]} if repo else None}


@router.get("/api/projects")
def list_projects(archived: bool = False):
    with db() as con:
        items = rows(con.execute("SELECT * FROM projects WHERE archived=? AND id!='prj_agent_evals' ORDER BY updated_at DESC", (int(archived),)))
    return [_project_summary(i) for i in items if auth.can_see_project(i["id"])]


@router.post("/api/projects", status_code=201)
def create_project(body: ProjectIn):
    item = {"id": new_id("prj"), "name": body.name.strip(), "description": body.description.strip(), "owner_id": auth.current_user.get()["id"], "created_at": now(), "updated_at": now()}
    with db() as con:
        con.execute("INSERT INTO projects (id, name, description, owner_id, created_at, updated_at) VALUES (:id,:name,:description,:owner_id,:created_at,:updated_at)", item)
    ledger.append(item["id"], auth.signer(), "project.created", item["id"], {"name": item["name"]})
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
        run_ids = [r["id"] for r in con.execute("SELECT id FROM runs WHERE project_id=?", (project_id,))]
        con.execute("DELETE FROM projects WHERE id=?", (project_id,))
    for run_id in filter(None, run_ids):  # saved failure replies and finished batches belong to the project's runs
        ingest._rm_tree(safe_path(RUNS, run_id, for_write=True))
    ingest._rm_tree(project_dir(project_id))
    return Response(status_code=204)


class MemberIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    role: str = "developer"


class TransferIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)


@router.get("/api/projects/{project_id}/members")
def list_members(project_id: str):
    _project(project_id)
    return auth.members(project_id)


@router.post("/api/projects/{project_id}/members", status_code=201)
def add_member(project_id: str, body: MemberIn):
    """The owner types the exact username. The answer is added or not found, and nothing else about the account."""
    _project(project_id)
    try:
        auth.add_member(project_id, body.username, body.role)
    except auth.AuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, "No account has that username") from exc
    return auth.members(project_id)


@router.delete("/api/projects/{project_id}/members/{user_id}", status_code=204)
def remove_member(project_id: str, user_id: str):
    _project(project_id)
    auth.remove_member(project_id, user_id)
    return Response(status_code=204)


@router.post("/api/projects/{project_id}/transfer")
def transfer(project_id: str, body: TransferIn):
    _project(project_id)
    try:
        auth.transfer_project(project_id, body.username)
    except KeyError as exc:
        raise HTTPException(404, "No account has that username") from exc
    return get_project(project_id)


@router.get("/api/projects/{project_id}/overview")
def overview(project_id: str):
    with db() as con:
        pending = rows(con.execute("SELECT id, run_id, gate, title, summary, created_at FROM approvals WHERE project_id=? AND status='pending' ORDER BY created_at", (project_id,)))
        latest = rows(con.execute("SELECT id, workflow, status, started_at, ended_at, error FROM runs WHERE project_id=? ORDER BY started_at DESC LIMIT 6", (project_id,)))
    repo = ingest.get(project_id)
    return {"project": get_project(project_id), "gates": gates.status(project_id), "pending_approvals": pending, "recent_runs": latest,
            "documents": documents.list_for(project_id)[:8], "repo": {k: repo[k] for k in ("kind", "url", "commit_sha", "scanned_at")} | {"analysis": {k: repo["analysis"].get(k) for k in ("mode", "languages", "frameworks", "test_runners", "total_files", "test_file_count")}} if repo else None}
