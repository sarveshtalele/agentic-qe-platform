"""Observability API: the log of agents, skills, tools, workflows, approvals, guardrails, and the ledger."""
from __future__ import annotations

import json

from fastapi import APIRouter, Query
from fastapi.responses import Response

from backend.core import auth
from backend.db import now
from backend.maf import observability

router = APIRouter()


def _scoped(found: dict) -> dict:
    """A user sees only records from their own projects, and their totals count only those."""
    if auth.current_user.get()["role"] == "admin":
        return found
    items = [i for i in found["items"] if auth.can_see_project(i["project_id"])]
    counts = {kind: sum(i["kind"] == kind for i in items) for kind in observability.KINDS}
    tokens = sum((i["detail"].get("tokens_in") or 0) + (i["detail"].get("tokens_out") or 0) for i in items if i["kind"] == "agent")
    return {**found, "items": items[:300], "total": len(items), "counts": counts, "errors": sum(i["level"] == "error" for i in items), "tokens": tokens,
            "runs": [r for r in found["runs"] if auth.can_see_project(r["project_id"])], "integrity": [i for i in found["integrity"] if auth.can_see_project(i["project_id"])]}


@router.get("/api/observability")
def get_log(project_id: str | None = None, run_id: str | None = None, kind: str = "", q: str = "", limit: int = Query(300, ge=1, le=2000)):
    return _scoped(observability.query(project_id, run_id, kind, q, limit if auth.current_user.get()["role"] == "admin" else observability.CAP))


@router.get("/api/observability/export")
def export_log(project_id: str | None = None, run_id: str | None = None, kind: str = "", q: str = ""):
    data = _scoped(observability.query(project_id, run_id, kind, q, limit=observability.CAP * 5))
    body = json.dumps({"exported_at": now(), "filters": {"project_id": project_id, "run_id": run_id, "kind": kind, "q": q}, **data}, indent=2, default=str)
    return Response(body, media_type="application/json", headers={"Content-Disposition": 'attachment; filename="agentic-qe-observability.json"'})
