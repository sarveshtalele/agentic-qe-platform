"""Observability API: the log of agents, skills, tools, workflows, approvals, guardrails, and the ledger."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from backend.core import auth
from backend.db import db, now, rows
from backend.maf import observability

router = APIRouter()


def _scoped() -> str | None:
    """The account whose projects limit the log, or None for the administrator, who sees all of it. The limit is applied in SQL."""
    user = auth.current_user.get()
    return None if user["role"] == "admin" else user["id"]


@router.get("/api/observability")
def get_log(project_id: str | None = None, run_id: str | None = None, kind: str = "", q: str = "", limit: int = Query(300, ge=1, le=2000), before: str = ""):
    try:
        return observability.query(project_id, run_id, kind, q, limit, before, _scoped())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/api/observability/errors")
def get_errors(project_id: str | None = None):
    """Failed stages grouped by error code and agent, newest group first. The stack is never selected here."""
    owner = _scoped()
    where = ["1=1"]
    if project_id:
        where.append("r.project_id=:project")
    if owner:
        where.append("r.project_id IN (SELECT id FROM projects WHERE owner_id=:owner AND id!=:eval)")
    params = {"project": project_id, "owner": owner, "eval": auth.EVAL_PROJECT}
    with db() as con:
        groups = rows(con.execute(f"""
            WITH ranked AS (
              SELECT f.code, f.agent, f.message, f.created_at,
                ROW_NUMBER() OVER (PARTITION BY f.code, f.agent ORDER BY f.created_at DESC, f.rowid DESC) AS rn,
                COUNT(*) OVER (PARTITION BY f.code, f.agent) AS total
              FROM run_failures f JOIN runs r ON r.id = f.run_id
              WHERE {' AND '.join(where)}
            )
            SELECT code, agent, total AS count, created_at AS latest_at, message AS latest_message
            FROM ranked WHERE rn = 1 ORDER BY latest_at DESC, code, agent
        """, params))
    return {"total": sum(g["count"] for g in groups), "groups": groups}


@router.get("/api/observability/export")
def export_log(project_id: str | None = None, run_id: str | None = None, kind: str = "", q: str = ""):
    data = observability.query(project_id, run_id, kind, q, observability.EXPORT_CAP, owner_id=_scoped())
    body = json.dumps({"exported_at": now(), "filters": {"project_id": project_id, "run_id": run_id, "kind": kind, "q": q}, **data}, indent=2, default=str)
    return Response(body, media_type="application/json", headers={"Content-Disposition": 'attachment; filename="agentic-qe-observability.json"'})
