"""One log of everything agents and workflows did, for a run, a project, or all projects. Reads stored records only."""
from __future__ import annotations

import base64
import json

from backend.core import ledger
from backend.core.auth import EVAL_PROJECT
from backend.core.security import redact
from backend.db import db, now, rows

# workflow stage to the agentic-qe skill it implements. See docs/ARCHITECTURE.md
SKILLS = {
    ("qe", "discover"): "analyzing-repositories",
    ("qe", "requirements"): "extracting-requirements",
    ("qe", "plan"): "planning-tests",
    ("qe", "design"): "designing-test-cases",
    ("qe", "data"): "generating-test-data",
    ("qe", "generate"): "generating-test-code",
    ("qe", "execute"): "executing-tests",
    ("qe", "heal"): "healing-tests",
    ("qe", "trace"): "tracing-coverage",
    ("qe", "sign"): "building-qe-dashboard",
    ("ba", "draft"): "authoring-user-stories",
}
KINDS = ("skill", "agent", "tool", "mcp", "workflow", "approval", "guardrail", "audit")
EXPORT_CAP = 25000  # records in one JSON export
APPROVAL_EVENTS = {"approval_required", "approved", "rejected"}


def record_tool(agent: str, project_id: str | None, run_id: str | None, source: str, tool: str, arguments: dict, latency_ms: int, error: str = "", kind: str = "function") -> None:
    with db() as con:
        con.execute(
            "INSERT INTO tool_calls (agent, project_id, run_id, source, tool, kind, arguments, latency_ms, status, error, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (agent, project_id, run_id, source, tool, kind, redact(json.dumps(arguments, default=str))[:4000], latency_ms, "error" if error else "ok", redact(error)[:1000], now()),
        )


# One normalized row per record: ts, s (source rank, breaks ties), id (that source's row id), kind, level, project_id, run_id, tokens, hay (text a search looks in).
# Scope (project, run, owner) is part of each SELECT, so every count and page is already limited to what the caller may see.
_SKILL_PARAMS = {f"sk{i}": f"{w}/{st}" for i, (w, st) in enumerate(SKILLS)}


def _where(project: str, run: str, owner: str) -> str:
    owned = "IN (SELECT id FROM projects WHERE (owner_id=:owner OR id IN (SELECT project_id FROM project_members WHERE user_id=:owner)) AND id!=:eval)"
    return "".join(f" AND {clause}" for clause in (project, run, f"{owner} {owned}" if owner else "") if clause)


def _sources(project_id, run_id, owner_id) -> tuple[list[str], dict]:
    params = {**_SKILL_PARAMS, "project": project_id, "run": run_id, "owner": owner_id, "eval": EVAL_PROJECT}
    marks = ", ".join(f":{k}" for k in _SKILL_PARAMS)
    pj = lambda col: f"{col}=:project" if project_id else ""
    rn = lambda col: f"{col}=:run" if run_id else ""
    own = lambda col: col if owner_id else ""
    ledger_run = "json_extract(l.data,'$.run_id')"
    return [
        f"""SELECT e.ts AS ts, 0 AS s, e.rowid AS id,
              CASE WHEN e.type='stage_start' AND r.workflow||'/'||e.stage IN ({marks}) THEN 'skill' WHEN e.type IN ('approval_required','approved','rejected') THEN 'approval' ELSE 'workflow' END AS kind,
              CASE e.type WHEN 'error' THEN 'error' WHEN 'warning' THEN 'warning' ELSE 'info' END AS level, r.project_id AS project_id, e.run_id AS run_id, 0 AS tokens,
              e.type||' '||e.stage||' '||e.message||' '||e.run_id||' '||e.data AS hay
            FROM run_events e JOIN runs r ON r.id=e.run_id WHERE e.type NOT IN ('agent','tool'){_where(pj('r.project_id'), rn('e.run_id'), own('r.project_id'))}""",
        f"""SELECT a.created_at AS ts, 1 AS s, a.id AS id, 'agent' AS kind, CASE WHEN a.status!='ok' THEN 'error' ELSE 'info' END AS level, a.project_id AS project_id, a.run_id AS run_id, a.tokens_in+a.tokens_out AS tokens,
              a.agent||' '||a.status||' '||a.error||' '||a.source||' '||a.prompt_ref||' '||IFNULL(a.run_id,'') AS hay
            FROM agent_calls a WHERE 1=1{_where(pj('a.project_id'), rn('a.run_id'), own('a.project_id'))}""",
        f"""SELECT t.created_at AS ts, 2 AS s, t.id AS id, CASE WHEN t.kind='mcp' THEN 'mcp' ELSE 'tool' END AS kind, CASE WHEN t.status!='ok' THEN 'error' ELSE 'info' END AS level, t.project_id AS project_id, t.run_id AS run_id, 0 AS tokens,
              t.tool||' '||t.agent||' '||t.source||' '||t.error||' '||t.arguments||' '||IFNULL(t.run_id,'') AS hay
            FROM tool_calls t WHERE 1=1{_where(pj('t.project_id'), rn('t.run_id'), own('t.project_id'))}""",
        f"""SELECT g.created_at AS ts, 3 AS s, g.id AS id, 'guardrail' AS kind, 'warning' AS level, g.project_id AS project_id, g.run_id AS run_id, 0 AS tokens, g.kind||' '||g.agent||' '||g.action||' '||g.detail||' '||IFNULL(g.run_id,'') AS hay
            FROM guardrail_events g WHERE 1=1{_where(pj('g.project_id'), rn('g.run_id'), own('g.project_id'))}""",
        f"""SELECT l.ts AS ts, 4 AS s, l.rowid AS id, 'audit' AS kind, 'info' AS level, l.project_id AS project_id, {ledger_run} AS run_id, 0 AS tokens, l.action||' '||l.actor||' '||l.target||' '||l.data AS hay
            FROM ledger l WHERE 1=1{_where(pj('l.project_id'), rn(ledger_run), own('l.project_id'))}""",
    ], params


def _cursor(key: str) -> list:
    try:
        ts, s, id_ = json.loads(base64.urlsafe_b64decode(key.encode()))
        return [str(ts), int(s), int(id_)]
    except (ValueError, TypeError):
        raise ValueError("The page marker is not valid") from None


def _key(item: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps([item["ts"], item["s"], item["id"]]).encode()).decode()


def _hydrate(con, keys: list[dict]) -> list[dict]:
    """Full records for one page of keys, in the page's order."""
    by_source: dict[int, list[int]] = {}
    for k in keys:
        by_source.setdefault(k["s"], []).append(k["id"])
    marks = lambda ids: ",".join("?" * len(ids))
    found: dict[tuple[int, int], dict] = {}
    for s, ids in by_source.items():
        if s == 0:
            for e in rows(con.execute(f"SELECT e.rowid AS rid, e.*, r.project_id, r.workflow FROM run_events e JOIN runs r ON r.id=e.run_id WHERE e.rowid IN ({marks(ids)})", ids)):
                skill = SKILLS.get((e["workflow"], e["stage"])) if e["type"] == "stage_start" else None
                found[0, e["rid"]] = {"kind": "skill" if skill else "approval" if e["type"] in APPROVAL_EVENTS else "workflow",
                                      "level": "error" if e["type"] == "error" else "warning" if e["type"] == "warning" else "info", "project_id": e["project_id"], "run_id": e["run_id"],
                                      "workflow": e["workflow"], "stage": e["stage"], "name": skill or e["type"], "message": e["message"], "detail": json.loads(e["data"] or "{}")}
        elif s == 1:
            for a in rows(con.execute(f"SELECT * FROM agent_calls WHERE id IN ({marks(ids)})", ids)):
                found[1, a["id"]] = {"kind": "agent", "level": "error" if a["status"] != "ok" else "info", "project_id": a["project_id"], "run_id": a["run_id"], "name": a["agent"],
                                     "message": a["error"] or f"{a['tokens_in'] + a['tokens_out']} tokens in {a['latency_ms']} ms, {a['tool_calls']} tool calls",
                                     "detail": {k: a[k] for k in ("source", "prompt_ref", "tokens_in", "tokens_out", "latency_ms", "tool_calls", "status")}}
        elif s == 2:
            for t in rows(con.execute(f"SELECT * FROM tool_calls WHERE id IN ({marks(ids)})", ids)):
                found[2, t["id"]] = {"kind": "mcp" if t["kind"] == "mcp" else "tool", "level": "error" if t["status"] != "ok" else "info", "project_id": t["project_id"], "run_id": t["run_id"], "name": t["tool"],
                                     "message": t["error"] or f"Called by {t['agent']} in {t['latency_ms']} ms",
                                     "detail": {"agent": t["agent"], "source": t["source"], "arguments": json.loads(t["arguments"]), "latency_ms": t["latency_ms"], "status": t["status"]}}
        elif s == 3:
            for g in rows(con.execute(f"SELECT * FROM guardrail_events WHERE id IN ({marks(ids)})", ids)):
                found[3, g["id"]] = {"kind": "guardrail", "level": "warning", "project_id": g["project_id"], "run_id": g["run_id"], "name": g["kind"],
                                     "message": f"{g['agent']}: {g['action']}. {g['detail']}", "detail": {"agent": g["agent"], "action": g["action"]}}
        else:
            for entry in rows(con.execute(f"SELECT rowid AS rid, * FROM ledger WHERE rowid IN ({marks(ids)})", ids)):
                data = json.loads(entry["data"] or "{}")
                found[4, entry["rid"]] = {"kind": "audit", "level": "info", "project_id": entry["project_id"], "run_id": data.get("run_id"), "name": entry["action"],
                                          "message": f"{entry['actor']}: {entry['target']}".rstrip(": "), "detail": {**data, "seq": entry["seq"], "hash": entry["hash"]}}
    return [{"ts": k["ts"], **found[k["s"], k["id"]], "key": _key(k)} for k in keys if (k["s"], k["id"]) in found]


def query(project_id: str | None = None, run_id: str | None = None, kind: str = "", text: str = "", limit: int = 300, before: str = "", owner_id: str | None = None) -> dict:
    """Newest first, one page. `before` is the `key` of the last item already shown; `next` is the key to ask for the page after this one.

    owner_id limits everything to the projects that account owns or is a member of (None means all projects).
    """
    sources, params = _sources(project_id, run_id, owner_id)
    params |= {"n": limit + 1, "kind": kind, "q": text}
    where = [" AND kind=:kind" if kind else "", " AND instr(lower(hay), lower(:q))>0" if text else ""]
    if before:
        params |= dict(zip(("kts", "ks", "kid"), _cursor(before)))
        where.append(" AND (ts<:kts OR (ts=:kts AND (s>:ks OR (s=:ks AND id<:kid))))")
    filters = "".join(where)
    page = " UNION ALL ".join(f"SELECT * FROM (SELECT * FROM ({src}) WHERE 1=1{filters} ORDER BY ts DESC, id DESC LIMIT :n)" for src in sources)
    union = " UNION ALL ".join(sources)
    with db() as con:
        keys = rows(con.execute(f"SELECT ts, s, id FROM ({page}) ORDER BY ts DESC, s ASC, id DESC LIMIT :n", params))
        more = len(keys) > limit
        keys = keys[:limit]
        items = _hydrate(con, keys)
        # totals ignore the cursor, so the numbers do not change as pages are loaded
        total = con.execute(f"SELECT COUNT(*) FROM ({union}) WHERE 1=1{''.join(where[:2])}", params).fetchone()[0]
        grouped = rows(con.execute(f"SELECT kind, COUNT(*) AS n, SUM(level='error') AS errors, SUM(tokens) AS tokens FROM ({union}) GROUP BY kind", params))
        scope = " WHERE (owner_id=:owner OR id IN (SELECT project_id FROM project_members WHERE user_id=:owner)) AND id!=:eval" if owner_id else ""
        names = {p["id"]: p["name"] for p in rows(con.execute(f"SELECT id, name FROM projects{scope}", params))}
        run_clause = [c for c in ("project_id=:project" if project_id else "", "project_id IN (SELECT id FROM projects WHERE (owner_id=:owner OR id IN (SELECT project_id FROM project_members WHERE user_id=:owner)) AND id!=:eval)" if owner_id else "") if c]
        runs = rows(con.execute(f"SELECT id, project_id, workflow, status, tokens_in, tokens_out, started_at, ended_at, error FROM runs{' WHERE ' + ' AND '.join(run_clause) if run_clause else ''} ORDER BY started_at DESC LIMIT 200",
                                {k: params[k] for k in ("project", "owner", "eval")}))
    counts = {k: next((g["n"] for g in grouped if g["kind"] == k), 0) for k in KINDS}
    for item in items:
        item["project"] = names.get(item["project_id"], "")
        item["message"] = redact(item["message"])
    for run in runs:
        run["project"] = names.get(run["project_id"], "")
    return {"items": items, "total": total, "next": items[-1]["key"] if more and items else None, "counts": counts, "errors": sum(g["errors"] or 0 for g in grouped),
            "tokens": sum(g["tokens"] or 0 for g in grouped if g["kind"] == "agent"), "runs": runs, "integrity": integrity(project_id, names)}


def integrity(project_id: str | None, names: dict[str, str]) -> list[dict]:
    return [{"project_id": pid, "project": names[pid], **ledger.verify(pid)} for pid in ([project_id] if project_id in names else names if not project_id else [])]
