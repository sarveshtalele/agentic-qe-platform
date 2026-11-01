"""Governance API."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.api.common import _project
from backend.core import auth, gates, ledger, prompts
from backend.db import db, rows
from backend.maf import agui, engine, evals, governance, llm, workflows  # noqa: F401 - workflows registers definitions

router = APIRouter()


@router.get("/api/projects/{project_id}/gates")
def project_gates(project_id: str):
    return gates.status(project_id)


class GateIn(BaseModel):
    approved: bool
    by: str
    reason: str = ""


@router.post("/api/projects/{project_id}/gates/{gate}/decision")
def decide_gate(project_id: str, gate: int, body: GateIn):
    _project(project_id)
    gates.decide(project_id, gate, body.approved, body.by, body.reason)
    return gates.status(project_id)


@router.get("/api/projects/{project_id}/approvals")
def project_approvals(project_id: str, status: str = "pending"):
    with db() as con:
        items = rows(con.execute("SELECT * FROM approvals WHERE project_id=? AND status=? ORDER BY created_at DESC", (project_id, status)))
    return [{**a, "payload": json.loads(a["payload"])} for a in items]


@router.get("/api/projects/{project_id}/ledger")
def project_ledger(project_id: str):
    return {"entries": ledger.entries(project_id), "verification": ledger.verify(project_id)}


class PromptIn(BaseModel):
    body: str = Field(min_length=10)
    note: str = Field(min_length=1)
    author: str = "user"


@router.get("/api/prompts")
def list_prompts():
    return prompts.list_all()


@router.get("/api/prompts/{agent}")
def prompt_history(agent: str):
    items = prompts.history(agent)
    if not items:
        raise KeyError(agent)
    return items


@router.post("/api/prompts/{agent}", status_code=201)
def add_prompt_version(agent: str, body: PromptIn):
    return prompts.add_version(agent, body.body, body.note, body.author)


@router.post("/api/prompts/{agent}/activate/{version}")
def activate_prompt(agent: str, version: int):
    return prompts.activate(agent, version)


class AgentSettingsIn(BaseModel):
    enabled: bool
    max_tokens: int | None = None
    by: str
    reason: str = ""


@router.get("/api/agents")
def list_agents():
    return governance.overview()


@router.get("/api/agents/guardrail-events")
def guardrail_events():
    return governance.recent_events()


@router.post("/api/agents/evals/run-all")
async def run_all_evals():
    return await evals.run_all()


@router.get("/api/agents/{agent}")
def agent_detail(agent: str):
    item = next((a for a in governance.overview() if a["key"] == agent), None)
    if not item:
        raise KeyError(agent)
    admin = auth.current_user.get()["role"] == "admin"  # recent calls and events span projects
    return {**item, "calls_recent": governance.recent_calls(agent) if admin else [], "events_recent": governance.recent_events(agent) if admin else [], "evals": evals.history(agent), "has_evals": agent in evals.available()}


@router.put("/api/agents/{agent}/settings")
def agent_settings(agent: str, body: AgentSettingsIn):
    try:
        governance.update_settings(agent, body.enabled, body.max_tokens, body.by, body.reason)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return agent_detail(agent)


@router.post("/api/agents/{agent}/evals")
async def run_agent_eval(agent: str):
    return await evals.run(agent)


@router.get("/api/evals")
def list_evals():
    return evals.available()


@router.get("/api/evals/{agent}")
def eval_history(agent: str):
    return evals.history(agent)


@router.get("/api/projects/{project_id}/metrics")
def metrics(project_id: str):
    """Numbers computed from stored runs and events. Empty until real work has happened."""
    with db() as con:
        by_status = rows(con.execute("SELECT workflow, status, COUNT(*) AS count, SUM(tokens_in) AS tokens_in, SUM(tokens_out) AS tokens_out FROM runs WHERE project_id=? GROUP BY workflow, status", (project_id,)))
        durations = rows(con.execute("SELECT workflow, ROUND(AVG((julianday(ended_at)-julianday(started_at))*86400),1) AS avg_seconds, COUNT(*) AS count FROM runs WHERE project_id=? AND ended_at IS NOT NULL GROUP BY workflow", (project_id,)))
        tools_used = rows(con.execute("SELECT json_extract(e.data,'$.tool') AS tool, COUNT(*) AS calls, ROUND(AVG(json_extract(e.data,'$.ms'))) AS avg_ms FROM run_events e JOIN runs r ON r.id=e.run_id WHERE r.project_id=? AND e.type='tool' GROUP BY tool ORDER BY calls DESC", (project_id,)))
        agent_runs = rows(con.execute("SELECT agent, COUNT(*) AS calls, SUM(tokens_in+tokens_out) AS tokens, CAST(AVG(latency_ms) AS INT) AS avg_ms, SUM(status='error') AS errors FROM agent_calls WHERE project_id=? GROUP BY agent ORDER BY tokens DESC", (project_id,)))
    return {"runs": by_status, "durations": durations, "tools": tools_used, "agents": agent_runs}
