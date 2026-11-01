"""One log of everything agents and workflows did, for a run, a project, or all projects. Reads stored records only."""
from __future__ import annotations

import json

from backend.core import ledger
from backend.core.security import redact
from backend.db import db, now, rows

# workflow stage to the agentic-qe skill it implements. See docs/ARCHITECTURE.md
SKILLS = {
    ("qe", "discover"): "analyzing-repositories",
    ("qe", "requirements"): "extracting-requirements",
    ("qe", "plan"): "planning-tests",
    ("qe", "design"): "designing-test-cases, generating-test-data",
    ("qe", "generate"): "generating-test-code",
    ("qe", "execute"): "executing-tests",
    ("qe", "heal"): "healing-tests",
    ("qe", "trace"): "tracing-coverage",
    ("qe", "sign"): "building-qe-dashboard",
    ("ba", "draft"): "authoring-user-stories",
}
KINDS = ("skill", "agent", "tool", "mcp", "workflow", "approval", "guardrail", "audit")
CAP = 5000  # ponytail: newest records per source, enough for one user. Paginate in SQL if a project outgrows it
APPROVAL_EVENTS = {"approval_required", "approved", "rejected"}


def record_tool(agent: str, project_id: str | None, run_id: str | None, source: str, tool: str, arguments: dict, latency_ms: int, error: str = "", kind: str = "function") -> None:
    with db() as con:
        con.execute(
            "INSERT INTO tool_calls (agent, project_id, run_id, source, tool, kind, arguments, latency_ms, status, error, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (agent, project_id, run_id, source, tool, kind, redact(json.dumps(arguments, default=str))[:4000], latency_ms, "error" if error else "ok", redact(error)[:1000], now()),
        )


def _scope(project_id: str | None, run_id: str | None, project_column: str = "project_id", run_column: str = "run_id") -> tuple[str, tuple]:
    clauses, values = [], []
    if project_id:
        clauses.append(f"{project_column}=?")
        values.append(project_id)
    if run_id:
        clauses.append(f"{run_column}=?")
        values.append(run_id)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), tuple(values)


def _workflow_items(con, project_id, run_id) -> list[dict]:
    where, values = _scope(project_id, run_id, "r.project_id", "e.run_id")
    found = rows(con.execute(f"SELECT e.*, r.project_id, r.workflow FROM run_events e JOIN runs r ON r.id=e.run_id{where} ORDER BY e.ts DESC, e.seq DESC LIMIT {CAP}", values))
    items = []
    for e in found:
        if e["type"] in {"agent", "tool"}:  # agent_calls and tool_calls hold these with more detail
            continue
        skill = SKILLS.get((e["workflow"], e["stage"])) if e["type"] == "stage_start" else None
        kind = "skill" if skill else "approval" if e["type"] in APPROVAL_EVENTS else "workflow"
        items.append({"ts": e["ts"], "kind": kind, "level": "error" if e["type"] == "error" else "warning" if e["type"] == "warning" else "info",
                      "project_id": e["project_id"], "run_id": e["run_id"], "workflow": e["workflow"], "stage": e["stage"], "name": skill or e["type"],
                      "message": e["message"], "detail": json.loads(e["data"] or "{}")})
    return items


def _agent_items(con, project_id, run_id) -> list[dict]:
    where, values = _scope(project_id, run_id)
    return [{"ts": a["created_at"], "kind": "agent", "level": "error" if a["status"] != "ok" else "info", "project_id": a["project_id"], "run_id": a["run_id"], "name": a["agent"],
             "message": a["error"] or f"{a['tokens_in'] + a['tokens_out']} tokens in {a['latency_ms']} ms, {a['tool_calls']} tool calls",
             "detail": {k: a[k] for k in ("source", "prompt_ref", "tokens_in", "tokens_out", "latency_ms", "tool_calls", "status")}}
            for a in rows(con.execute(f"SELECT * FROM agent_calls{where} ORDER BY id DESC LIMIT {CAP}", values))]


def _tool_items(con, project_id, run_id) -> list[dict]:
    where, values = _scope(project_id, run_id)
    return [{"ts": t["created_at"], "kind": "mcp" if t["kind"] == "mcp" else "tool", "level": "error" if t["status"] != "ok" else "info", "project_id": t["project_id"], "run_id": t["run_id"], "name": t["tool"],
             "message": t["error"] or f"Called by {t['agent']} in {t['latency_ms']} ms", "detail": {"agent": t["agent"], "source": t["source"], "arguments": json.loads(t["arguments"]), "latency_ms": t["latency_ms"], "status": t["status"]}}
            for t in rows(con.execute(f"SELECT * FROM tool_calls{where} ORDER BY id DESC LIMIT {CAP}", values))]


def _guardrail_items(con, project_id, run_id) -> list[dict]:
    where, values = _scope(project_id, run_id)
    return [{"ts": g["created_at"], "kind": "guardrail", "level": "warning", "project_id": g["project_id"], "run_id": g["run_id"], "name": g["kind"], "message": f"{g['agent']}: {g['action']}. {g['detail']}", "detail": {"agent": g["agent"], "action": g["action"]}}
            for g in rows(con.execute(f"SELECT * FROM guardrail_events{where} ORDER BY id DESC LIMIT {CAP}", values))]


def _audit_items(con, project_id, run_id) -> list[dict]:
    where, values = _scope(project_id, None)
    items = []
    for entry in rows(con.execute(f"SELECT * FROM ledger{where} ORDER BY ts DESC, seq DESC LIMIT {CAP}", values)):
        data = json.loads(entry["data"] or "{}")
        if run_id and data.get("run_id") != run_id:
            continue
        items.append({"ts": entry["ts"], "kind": "audit", "level": "info", "project_id": entry["project_id"], "run_id": data.get("run_id"), "name": entry["action"],
                      "message": f"{entry['actor']}: {entry['target']}".rstrip(": "), "detail": {**data, "seq": entry["seq"], "hash": entry["hash"]}})
    return items


def query(project_id: str | None = None, run_id: str | None = None, kind: str = "", text: str = "", limit: int = 300) -> dict:
    with db() as con:
        items = [*_workflow_items(con, project_id, run_id), *_agent_items(con, project_id, run_id), *_tool_items(con, project_id, run_id), *_guardrail_items(con, project_id, run_id), *_audit_items(con, project_id, run_id)]
        names = {p["id"]: p["name"] for p in rows(con.execute("SELECT id, name FROM projects"))}
        where, values = _scope(project_id, None)
        runs = rows(con.execute(f"SELECT id, project_id, workflow, status, tokens_in, tokens_out, started_at, ended_at, error FROM runs{where} ORDER BY started_at DESC LIMIT 200", values))
    # newest first; sorted is stable, so records from one second keep their source's order
    items.sort(key=lambda item: item["ts"], reverse=True)
    counts = {k: sum(i["kind"] == k for i in items) for k in KINDS}
    errors = sum(i["level"] == "error" for i in items)
    tokens = sum((i["detail"].get("tokens_in") or 0) + (i["detail"].get("tokens_out") or 0) for i in items if i["kind"] == "agent")
    if kind:
        items = [i for i in items if i["kind"] == kind]
    if text:
        needle = text.lower()
        items = [i for i in items if needle in f"{i['name']} {i['message']} {i.get('run_id')} {json.dumps(i['detail'], default=str)}".lower()]
    total = len(items)
    for item in items:
        item["project"] = names.get(item["project_id"], "")
        item["message"] = redact(item["message"])
    for run in runs:
        run["project"] = names.get(run["project_id"], "")
    return {"items": items[:limit], "total": total, "counts": counts, "errors": errors, "tokens": tokens, "runs": runs, "integrity": integrity(project_id, names)}


def integrity(project_id: str | None, names: dict[str, str]) -> list[dict]:
    return [{"project_id": pid, "project": names[pid], **ledger.verify(pid)} for pid in ([project_id] if project_id in names else names if not project_id else [])]
