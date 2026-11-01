"""The project_status agent tool."""
from __future__ import annotations

import json

from agent_framework import tool

from backend.core import gates
from backend.db import db, rows


def build(project_id: str, thread_id: str, start_run):
    @tool(name="project_status", description="Quality gates, recent workflow runs, open approvals, and open findings for this project.")
    def project_status() -> str:
        with db() as con:
            runs = rows(con.execute("SELECT id, workflow, status, started_at, ended_at, error FROM runs WHERE project_id=? ORDER BY started_at DESC LIMIT 10", (project_id,)))
            pending = rows(con.execute("SELECT id, run_id, gate, title FROM approvals WHERE project_id=? AND status='pending'", (project_id,)))
            findings = rows(con.execute("SELECT severity, COUNT(*) AS count FROM findings WHERE project_id=? AND status='open' GROUP BY severity", (project_id,)))
        return json.dumps({"gates": [{k: g[k] for k in ("gate", "name", "status", "decided_by")} for g in gates.status(project_id)], "runs": runs, "pending_approvals": pending, "open_findings": findings})

    return project_status
