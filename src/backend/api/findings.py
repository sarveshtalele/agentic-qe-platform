"""Findings API."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core import auth, ledger
from backend.db import db, row, rows
from backend.maf import agui, engine, evals, governance, llm, workflows  # noqa: F401 - workflows registers definitions

router = APIRouter()


@router.get("/api/findings")
def all_findings():
    with db() as con:
        found = rows(con.execute("""SELECT f.*, p.name AS project FROM findings f JOIN projects p ON p.id=f.project_id
                                   WHERE f.status IN ('open','fix_attempted') AND p.archived=0 AND p.id!='prj_agent_evals'
                                   ORDER BY CASE f.severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, f.created_at DESC LIMIT 500"""))
    return [f for f in found if auth.can_see_project(f["project_id"])]


class FindingPatch(BaseModel):
    status: str = Field(pattern="^(open|dismissed|fixed|fix_attempted)$")


@router.get("/api/projects/{project_id}/findings")
def findings(project_id: str, status: str = "open"):
    """Open means still to do: it includes findings a fix was tried on whose tests did not pass."""
    with db() as con:
        return rows(con.execute(
            "SELECT * FROM findings WHERE project_id=? AND (status=? OR (?='open' AND status='fix_attempted')) ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END, file, line",
            (project_id, status, status)))


@router.patch("/api/findings/{finding_id}")
def patch_finding(finding_id: str, body: FindingPatch):
    with db() as con:
        found = row(con.execute("SELECT project_id FROM findings WHERE id=?", (finding_id,)))
        if not found:
            raise KeyError(finding_id)
        con.execute("UPDATE findings SET status=? WHERE id=?", (body.status, finding_id))
    ledger.append(found["project_id"], auth.signer(), f"finding.{body.status}", finding_id)
    return {"id": finding_id, "status": body.status}
