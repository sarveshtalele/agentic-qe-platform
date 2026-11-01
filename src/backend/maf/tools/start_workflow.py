"""The start_workflow agent tool."""
from __future__ import annotations

import json
from typing import Annotated

from agent_framework import tool
from pydantic import Field


def build(project_id: str, thread_id: str, start_run):
    @tool(name="start_workflow", description="Start a workflow run. workflow is one of: ba (needs brief), qe, bug_scan, change (needs spec or finding_id). Humans approve gates in the app. Use only when the user asks to run it.")
    async def start_workflow(
        workflow: str,
        brief: Annotated[str, Field(description="Requirements brief for ba, or the change description for change")] = "",
        title: Annotated[str, Field(description="Short title")] = "",
        finding_id: Annotated[str, Field(description="Finding to fix, for change")] = "",
    ) -> str:
        try:
            payload = {"brief": brief, "spec": brief, "title": title or workflow, "kind": "bugfix" if finding_id else "feature"}
            if finding_id:
                payload["finding_id"] = finding_id
            run = await start_run(project_id, workflow, payload)
        except (ValueError, KeyError, RuntimeError) as exc:
            return f"Could not start: {exc}"
        return json.dumps({"run_id": run["id"], "status": run["status"], "view": f"/projects/{project_id}/runs/{run['id']}"})

    return start_workflow
