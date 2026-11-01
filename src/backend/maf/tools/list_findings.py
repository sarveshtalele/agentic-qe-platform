"""The list_findings agent tool."""
from __future__ import annotations

import json
from typing import Annotated

from agent_framework import tool
from pydantic import Field

from backend.db import db, rows


def build(project_id: str, thread_id: str, start_run):
    @tool(name="list_findings", description="List open bug and security findings with file and line.")
    def list_findings(severity: Annotated[str, Field(description="critical, high, medium, low, or empty for all")] = "") -> str:
        query = "SELECT id, severity, title, file, line, evidence, source FROM findings WHERE project_id=? AND status IN ('open','fix_attempted')" + (" AND severity=?" if severity else "") + " LIMIT 60"
        with db() as con:
            return json.dumps(rows(con.execute(query, (project_id, severity) if severity else (project_id,))))

    return list_findings
