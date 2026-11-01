"""Agent governance: one registry, per-agent tool policy, an admin kill switch, guardrails, and call telemetry."""
from __future__ import annotations

import re
import time
from dataclasses import asdict

from agent_framework import chat_middleware

from backend.core import ledger, prompts
from backend.core.errors import AllowanceError, AqeError, classify
from backend.core.security import redact, scan_secrets
from backend.db import db, now, row, rows
from backend.maf import observability
from backend.maf.agents import CHAT_READ, DOCS, POLICIES, READ, AgentPolicy  # noqa: F401 - re-exported

INJECTION = re.compile(
    r"(?:ignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|earlier)\s+(instructions|prompts|rules)"
    r"|disregard\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|your)\s+(instructions|prompts|rules)"
    r"|reveal\s+(your\s+|the\s+)?(system\s+)?(prompt|instructions)"
    r"|you\s+are\s+now\s+(a|an|in)\b"
    r"|send\s+.{0,40}(api[_ ]?key|token|credential|secret).{0,40}\bto\b"
    r")[^\n.]*\.?",  # the whole sentence goes, or its tail still gives the order
    re.I,
)


class AgentDisabled(AllowanceError):
    action = "Ask your administrator to enable the agent on the Agents page, then retry the stage."


def settings(agent: str) -> dict:
    with db() as con:
        found = row(con.execute("SELECT * FROM agent_settings WHERE agent=?", (agent,)))
    return found or {"agent": agent, "enabled": 1, "max_tokens": None, "updated_by": "", "reason": "", "updated_at": None}


def update_settings(agent: str, enabled: bool, max_tokens: int | None, by: str, reason: str) -> dict:
    if agent not in POLICIES:
        raise KeyError(agent)
    if not by.strip():
        raise ValueError("A named person is required to change agent settings")
    if max_tokens is not None and not 500 <= max_tokens <= 64_000:
        raise ValueError("Token limit must be between 500 and 64000")
    with db() as con:
        con.execute("INSERT OR REPLACE INTO agent_settings VALUES (?,?,?,?,?,?)", (agent, int(enabled), max_tokens, by, reason, now()))
        projects = rows(con.execute("SELECT id FROM projects"))
    for project in projects:  # the agent is shared, so each project's audit trail records the change
        ledger.append(project["id"], by, "agent.settings", agent, {"enabled": enabled, "max_tokens": max_tokens, "reason": reason})
    return settings(agent)


def require_enabled(agent: str) -> None:
    if not settings(agent)["enabled"]:
        reason = settings(agent)["reason"]
        raise AgentDisabled(f"Agent {POLICIES[agent].name} is disabled on the Agents page" + (f": {reason}" if reason else ""))


def token_limit(agent: str) -> int:
    return settings(agent)["max_tokens"] or POLICIES[agent].max_tokens


def allowed(agent: str, tool_list: list, chat: bool) -> list:
    """Deny by default: a tool reaches the model only if this agent's policy lists it."""
    policy = POLICIES[agent]
    permitted = (policy.chat_tools or frozenset()) if chat else policy.workflow_tools
    return [t for t in tool_list if t.name in permitted]


def flag(agent: str, kind: str, action: str, detail: str, project_id: str | None = None, run_id: str | None = None) -> None:
    with db() as con:
        con.execute("INSERT INTO guardrail_events (agent, project_id, run_id, kind, action, detail, created_at) VALUES (?,?,?,?,?,?,?)",
                    (agent, project_id, run_id, kind, action, redact(detail)[:500], now()))


REMOVED = "[removed by Agentic QE Platform: possible prompt injection]"


def guard_text(agent: str, text: str, direction: str, project_id: str | None, run_id: str | None = None) -> str:
    """Input and output guardrail. Secrets and likely prompt injection never reach the model or the record."""
    hits = scan_secrets(text)
    if hits:
        flag(agent, "secret", "redacted", f"{direction}: {sorted({h['type'] for h in hits})}", project_id, run_id)
        text = redact(text)
    return neutralize(agent, text, direction, project_id, run_id)


def neutralize(agent: str, text: str, where: str, project_id: str | None, run_id: str | None = None) -> str:
    """Remove injection attempts from untrusted text. Model providers may also reject such text outright, failing the call."""
    matches = [m.group(0) for m in INJECTION.finditer(text)]
    if not matches:
        return text
    flag(agent, "prompt_injection", "removed", f"{where}: {matches[0]}", project_id, run_id)
    return INJECTION.sub(REMOVED, text)


def typed_error(agent: str, exc: Exception, project_id: str | None, run_id: str | None = None) -> AqeError:
    """Turn any failure into a typed error. A provider refusal is also recorded as a guardrail event."""
    error = classify(exc)
    if error.code == "AQE-MODEL-005":
        flag(agent, "provider_filter", "blocked", error.message, project_id, run_id)
    return error


def explain_error(agent: str, exc: Exception, project_id: str | None, run_id: str | None = None) -> str:
    """The sentence a person can act on, for places that show text only."""
    return typed_error(agent, exc, project_id, run_id).message


def guard_tool_result(agent: str, tool: str, result, project_id: str | None, run_id: str | None):
    """Repository text is untrusted, so tool results pass the same filter before the model reads them."""
    if isinstance(result, str):
        return neutralize(agent, result, f"tool {tool}", project_id, run_id)
    for content in result if isinstance(result, list) else []:  # MAF wraps tool output in Content objects
        if getattr(content, "type", "") == "text" and content.text:
            content.text = neutralize(agent, content.text, f"tool {tool}", project_id, run_id)
    return result


def record_call(agent: str, project_id: str | None, run_id: str | None, source: str, usage: dict, latency_ms: int, tool_calls: int, status: str, error: str = "") -> None:
    with db() as con:
        con.execute(
            "INSERT INTO agent_calls (agent, project_id, run_id, source, prompt_ref, tokens_in, tokens_out, latency_ms, tool_calls, status, error, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (agent, project_id, run_id, source, prompts.ref(agent), usage.get("input_token_count") or 0, usage.get("output_token_count") or 0, latency_ms, tool_calls, status, redact(error)[:400], now()),
        )


def telemetry(agent: str, project_id: str | None, run_id: str | None, source: str):
    """MAF chat middleware: records each model round, streamed or not."""

    @chat_middleware
    async def record(context, call_next) -> None:
        started = time.perf_counter()
        try:
            await call_next()
        except Exception as exc:
            record_call(agent, project_id, run_id, source, {}, int((time.perf_counter() - started) * 1000), 0, "error", str(exc))
            raise
        if context.stream:
            def finished(response):
                _record_refused_tools(agent, project_id, run_id, source, response)
                record_call(agent, project_id, run_id, source, dict(response.usage_details or {}), int((time.perf_counter() - started) * 1000), _tool_count(response), "ok")
                return response

            context.stream_result_transforms = [*context.stream_result_transforms, finished]
            return
        response = context.result
        _record_refused_tools(agent, project_id, run_id, source, response)
        record_call(agent, project_id, run_id, source, dict(response.usage_details or {}), int((time.perf_counter() - started) * 1000), _tool_count(response), "ok")

    return record


def _record_refused_tools(agent: str, project_id: str | None, run_id: str | None, source: str, response) -> None:
    """A tool the agent may not use never reaches the tool middleware, so its request is logged here for the audit trail."""
    policy = POLICIES[agent]
    allowed = (policy.chat_tools or frozenset()) if source == "chat" else policy.workflow_tools
    for message in response.messages:
        for content in message.contents:
            if content.type == "function_call" and content.name not in allowed:
                observability.record_tool(agent, project_id, run_id, source, content.name, {"requested": str(content.arguments)[:2000]}, 0, "Refused: not allowed for this agent")


def _tool_count(response) -> int:
    return sum(1 for m in response.messages for c in m.contents if c.type == "function_call")


def overview() -> list[dict]:
    """Registry joined with stored numbers. All figures come from recorded calls and events."""
    with db() as con:
        calls = {r["agent"]: r for r in rows(con.execute(
            """SELECT agent, COUNT(*) AS calls, SUM(tokens_in) AS tokens_in, SUM(tokens_out) AS tokens_out, CAST(AVG(latency_ms) AS INT) AS avg_latency_ms,
                      SUM(tool_calls) AS tool_calls, SUM(status='error') AS errors, MAX(created_at) AS last_call FROM agent_calls GROUP BY agent"""))}
        events = {r["agent"]: r["count"] for r in rows(con.execute("SELECT agent, COUNT(*) AS count FROM guardrail_events GROUP BY agent"))}
        latest_eval = {r["agent"]: r for r in rows(con.execute(
            "SELECT e.* FROM evaluations e JOIN (SELECT agent, MAX(created_at) AS at, MAX(rowid) AS id FROM evaluations GROUP BY agent) x ON e.rowid=x.id"))}
    result = []
    for key, policy in POLICIES.items():
        current = settings(key)
        stored = calls.get(key, {})
        evaluation = latest_eval.get(key)
        active = prompts.ref(key)
        result.append({
            "key": key, **{k: v for k, v in asdict(policy).items() if k not in {"workflow_tools", "chat_tools"}},
            "workflow_tools": sorted(policy.workflow_tools), "chat_tools": sorted(policy.chat_tools or []), "in_chat": policy.chat_tools is not None,
            "enabled": bool(current["enabled"]), "token_limit": token_limit(key), "settings_by": current["updated_by"], "settings_reason": current["reason"],
            "prompt_ref": active,
            "calls": stored.get("calls", 0), "tokens": (stored.get("tokens_in") or 0) + (stored.get("tokens_out") or 0), "avg_latency_ms": stored.get("avg_latency_ms"),
            "tool_calls": stored.get("tool_calls") or 0, "errors": stored.get("errors") or 0, "last_call": stored.get("last_call"), "guardrail_events": events.get(key, 0),
            "eval": {"passed": evaluation["passed"], "total": evaluation["total"], "prompt_ref": evaluation["prompt_ref"], "current": evaluation["prompt_ref"] == active, "created_at": evaluation["created_at"]} if evaluation else None,
        })
    return result


def recent_calls(agent: str, limit: int = 30) -> list[dict]:
    with db() as con:
        return rows(con.execute("SELECT * FROM agent_calls WHERE agent=? ORDER BY id DESC LIMIT ?", (agent, limit)))


def recent_events(agent: str | None = None, limit: int = 50) -> list[dict]:
    query = "SELECT * FROM guardrail_events" + (" WHERE agent=?" if agent else "") + " ORDER BY id DESC LIMIT ?"
    with db() as con:
        return rows(con.execute(query, (agent, limit) if agent else (limit,)))
