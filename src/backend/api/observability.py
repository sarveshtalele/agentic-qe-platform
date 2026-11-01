"""Observability API: the log of agents, skills, tools, workflows, approvals, guardrails, and the ledger."""
from __future__ import annotations

import json

from fastapi import APIRouter, Query
from fastapi.responses import Response

from backend.db import now
from backend.maf import observability

router = APIRouter()


@router.get("/api/observability")
def get_log(project_id: str | None = None, run_id: str | None = None, kind: str = "", q: str = "", limit: int = Query(300, ge=1, le=2000)):
    return observability.query(project_id, run_id, kind, q, limit)


@router.get("/api/observability/export")
def export_log(project_id: str | None = None, run_id: str | None = None, kind: str = "", q: str = ""):
    data = observability.query(project_id, run_id, kind, q, limit=observability.CAP * 5)
    body = json.dumps({"exported_at": now(), "filters": {"project_id": project_id, "run_id": run_id, "kind": kind, "q": q}, **data}, indent=2, default=str)
    return Response(body, media_type="application/json", headers={"Content-Disposition": 'attachment; filename="agentic-qe-observability.json"'})
