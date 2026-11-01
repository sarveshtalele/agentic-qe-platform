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
    return _named(gates.status(project_id))


def _named(items: list[dict]) -> list[dict]:
    names = auth.display_names({g["decided_by"] for g in items if g["decided_by"]})
    return [{**g, "decided_by_name": names.get(g["decided_by"], g["decided_by"])} for g in items]


class GateIn(BaseModel):
    approved: bool
    reason: str = ""


@router.post("/api/projects/{project_id}/gates/{gate}/decision")
def decide_gate(project_id: str, gate: int, body: GateIn):
    _project(project_id)
    auth.require_gate_signer(project_id, gate)
    gates.decide(project_id, gate, body.approved, auth.signer(), body.reason)
    return _named(gates.status(project_id))


@router.get("/api/projects/{project_id}/approvals")
def project_approvals(project_id: str, status: str = "pending"):
    with db() as con:
        items = rows(con.execute("SELECT * FROM approvals WHERE project_id=? AND status=? ORDER BY created_at DESC", (project_id, status)))
    return [{**a, "payload": json.loads(a["payload"])} for a in items]


@router.get("/api/projects/{project_id}/ledger")
def project_ledger(project_id: str):
    found = ledger.entries(project_id)
    names = auth.display_names({e["actor"] for e in found})
    return {"entries": [{**e, "actor_name": names.get(e["actor"], e["actor"])} for e in found], "verification": ledger.verify(project_id)}


class PromptIn(BaseModel):
    body: str = Field(min_length=10)
    note: str = Field(min_length=1)


@router.get("/api/prompts")
def list_prompts():
    return prompts.list_all()


@router.get("/api/prompts/{agent}")
def prompt_history(agent: str):
    items = prompts.history(agent)
    if not items:
        raise KeyError(agent)
    names = auth.display_names({i["author"] for i in items})
    return [{**i, "author_name": names.get(i["author"], i["author"])} for i in items]


@router.post("/api/prompts/{agent}", status_code=201)
def add_prompt_version(agent: str, body: PromptIn):
    return prompts.add_version(agent, body.body, body.note, auth.signer())


@router.post("/api/prompts/{agent}/activate/{version}")
def activate_prompt(agent: str, version: int):
    return prompts.activate(agent, version)


class AgentSettingsIn(BaseModel):
    enabled: bool
    max_tokens: int | None = None
    reason: str = ""
    model: str = ""


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
    item = {**item, "settings_by_name": auth.display_names({item["settings_by"]}).get(item["settings_by"], item["settings_by"]) if item.get("settings_by") else None}
    admin = auth.current_user.get()["role"] == "admin"  # recent calls and events span projects
    return {**item, "calls_recent": governance.recent_calls(agent) if admin else [], "events_recent": governance.recent_events(agent) if admin else [], "evals": evals.history(agent), "has_evals": agent in evals.available()}


@router.put("/api/agents/{agent}/settings")
def agent_settings(agent: str, body: AgentSettingsIn):
    try:
        governance.update_settings(agent, body.enabled, body.max_tokens, auth.signer(), body.reason, body.model)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return agent_detail(agent)


class EvalRunIn(BaseModel):
    benchmark: str = ""
    repeats: int = Field(1, ge=1, le=5)
    ragas: bool = False  # model-graded metrics cost tokens, so they are asked for


@router.post("/api/agents/{agent}/evals")
async def run_agent_eval(agent: str, body: EvalRunIn | None = None):
    body = body or EvalRunIn()
    try:
        return await evals.run(agent, benchmark=body.benchmark, repeats=body.repeats, ragas=body.ragas)
    except KeyError as exc:
        raise HTTPException(404, str(exc.args[0])) from exc


@router.get("/api/agents/{agent}/metrics")
def agent_metrics(agent: str):
    """Every metric with its caveats, the trend by prompt version, the spread over repeated runs, and the latest cases, worst first."""
    if agent not in governance.POLICIES:
        raise HTTPException(404, f"No agent {agent}")
    return {**evals.store.detail(agent), "cases": evals.cases_worst_first(agent)}


@router.get("/api/prompts/{agent}/scores")
def prompt_scores(agent: str):
    return evals.store.by_version(agent)


@router.get("/api/evals")
def list_evals():
    return evals.available()


@router.get("/api/evals/cards")
def eval_cards():
    """The four tiles of every agent card, plus whether RAGAS can run and which judge model is set."""
    ok, why = evals.ragas_evaluator.installed()
    return {"cards": evals.store.cards(), "ragas": {"installed": ok, "reason": why, "judge_model": evals.ragas_evaluator.judge_model()}, "benchmarks": evals.benchmarks()}


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
