"""AG-UI endpoint for the chatbot. MAF's AgentFrameworkAgent produces the protocol stream.

The project comes from the server-side thread row, never from the client, so a thread id cannot reach
another project's tools. This thin route replaces add_agent_framework_fastapi_endpoint because agents are
built per request with project-scoped tools. Messages are persisted here, around the MAF stream.
"""
from __future__ import annotations

import json
import logging

from ag_ui.core import RunErrorEvent
from ag_ui.encoder import EventEncoder
from agent_framework.ag_ui import AgentFrameworkAgent
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.core import auth
from backend.core import ledger
from backend.core.errors import stack_of
from backend.core.security import redact
from backend.db import db, new_id, now, row, rows
from backend.maf import engine, governance, llm, tools
from backend.maf import runtime as agents

router = APIRouter()


def create_thread(project_id: str, agent: str, title: str = "New chat") -> dict:
    if agent not in agents.CHAT_AGENTS:
        raise ValueError(f"Unknown agent {agent}")
    thread = {"id": new_id("thr"), "project_id": project_id, "title": title, "agent": agent, "created_at": now(), "updated_at": now()}
    with db() as con:
        con.execute("INSERT INTO chat_threads VALUES (:id,:project_id,:title,:agent,:created_at,:updated_at)", thread)
    return thread


def thread_messages(thread_id: str) -> list[dict]:
    with db() as con:
        return rows(con.execute("SELECT id, role, content, agent, created_at FROM chat_messages WHERE thread_id=? ORDER BY seq", (thread_id,)))


def _append(thread_id: str, role: str, content: str, agent: str, message_id: str | None = None) -> None:
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        seq = con.execute("SELECT COALESCE(MAX(seq),0)+1 FROM chat_messages WHERE thread_id=?", (thread_id,)).fetchone()[0]
        con.execute("INSERT INTO chat_messages VALUES (?,?,?,?,?,?,?)", (thread_id, seq, message_id or new_id("msg"), role, redact(content), agent, now()))
        con.execute("UPDATE chat_threads SET updated_at=? WHERE id=?", (now(), thread_id))
        title = con.execute("SELECT title FROM chat_threads WHERE id=?", (thread_id,)).fetchone()["title"]
        if role == "user" and title == "New chat":
            con.execute("UPDATE chat_threads SET title=? WHERE id=?", (" ".join(content.split())[:60], thread_id))


def _text_of(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content or ""


@router.post("/agui/{agent_key}")
async def agui(agent_key: str, request: Request):
    if agent_key not in agents.CHAT_AGENTS:
        raise HTTPException(404, "Unknown agent")
    body = await request.json()
    thread_id = body.get("threadId") or body.get("thread_id") or ""
    with db() as con:
        thread = row(con.execute("SELECT * FROM chat_threads WHERE id=?", (thread_id,)))
    if not thread:
        raise HTTPException(404, "Unknown thread. Create one first")
    project_id = thread["project_id"]
    if not auth.can_see_project(project_id):
        raise HTTPException(404, "Unknown thread. Create one first")
    incoming = body.get("messages") or []
    last_user = next((m for m in reversed(incoming) if m.get("role") == "user"), None)
    if last_user:
        clean = governance.guard_text(agent_key, _text_of(last_user), "input", project_id)
        if clean != _text_of(last_user):  # the model and the store only ever see the redacted text
            last_user["content"] = clean
        _append(thread_id, "user", clean, agent_key, last_user.get("id"))
    encoder = EventEncoder()

    async def stream():
        answer: list[str] = []
        agents.set_emitter(None)
        try:
            chat_tools = tools.document_tools(project_id) + tools.chat_tools(project_id, thread_id, engine.start)
            agent = agents.build(agent_key, project_id, chat_tools, chat=True, source="chat")
            wrapped = AgentFrameworkAgent(agent, require_confirmation=False)
            payload = {"messages": incoming, "thread_id": thread_id, "run_id": body.get("runId") or new_id("rn"),
                       "state": body.get("state") or {}, "tools": body.get("tools") or [], "context": body.get("context") or [],
                       "forwarded_props": body.get("forwardedProps") or {}}
            async for event in wrapped.run(payload):
                kind = getattr(event, "type", "")
                if str(getattr(kind, "value", kind)) == "TEXT_MESSAGE_CONTENT":
                    answer.append(event.delta)
                # every event type is redacted, including the final message snapshot
                # ponytail: a secret split across two deltas passes in the live stream; the snapshot and stored copy are clean
                yield redact(encoder.encode(event))
        except llm.LLMNotConfigured as exc:
            yield encoder.encode(RunErrorEvent(message=str(exc), code="LLM_NOT_CONFIGURED"))
        except Exception as exc:  # recorded in the log with an id, and the user sees the failure in chat instead of a dead stream
            error = governance.typed_error(agent_key, exc, project_id)
            error_id = new_id("err")
            logging.getLogger("aqe.chat").error("chat %s failed: %s error_id=%s %s", thread_id, error.code, error_id, error.message)
            logging.getLogger("aqe.chat").error("stack for %s: %s", error_id, stack_of(exc))
            yield encoder.encode(RunErrorEvent(message=f"{error.message} {error.action} (error {error_id})", code=error.code))
        finally:
            if answer:
                reply = governance.guard_text(agent_key, "".join(answer), "output", project_id)
                _append(thread_id, "assistant", reply, agent_key)
                ledger.append(project_id, f"agent:{agent_key}", "chat.reply", thread_id, {"chars": sum(map(len, answer))})

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


__all__ = ["router", "create_thread", "thread_messages", "json"]
