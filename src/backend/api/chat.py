"""Chat API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import (
    Response,
)
from pydantic import BaseModel, Field

from backend.api.common import _project
from backend.db import db, row, rows
from backend.maf import agui, engine, evals, governance, llm, workflows  # noqa: F401 - workflows registers definitions
from backend.maf import runtime as agents

router = APIRouter()


class ThreadIn(BaseModel):
    agent: str = "copilot"
    title: str = "New chat"


class ThreadPatch(BaseModel):
    title: str | None = None
    agent: str | None = None


class MemoryIn(BaseModel):
    content: str = Field(min_length=1)


@router.get("/api/chat/agents")
def chat_agents():
    return [{"key": k, "name": v} for k, v in agents.CHAT_AGENTS.items()]


@router.get("/api/projects/{project_id}/chats")
def list_chats(project_id: str):
    with db() as con:
        return rows(con.execute("SELECT t.*, (SELECT COUNT(*) FROM chat_messages m WHERE m.thread_id=t.id) AS messages FROM chat_threads t WHERE project_id=? ORDER BY updated_at DESC", (project_id,)))


@router.post("/api/projects/{project_id}/chats", status_code=201)
def create_chat(project_id: str, body: ThreadIn):
    _project(project_id)
    try:
        return agui.create_thread(project_id, body.agent, body.title)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/chats/{thread_id}")
def get_chat(thread_id: str):
    with db() as con:
        thread = row(con.execute("SELECT * FROM chat_threads WHERE id=?", (thread_id,)))
    if not thread:
        raise KeyError(thread_id)
    return {**thread, "messages": agui.thread_messages(thread_id)}


@router.patch("/api/chats/{thread_id}")
def patch_chat(thread_id: str, body: ThreadPatch):
    if body.agent and body.agent not in agents.CHAT_AGENTS:
        raise HTTPException(400, "Unknown agent")
    with db() as con:
        if body.title:
            con.execute("UPDATE chat_threads SET title=? WHERE id=?", (body.title[:120], thread_id))
        if body.agent:
            con.execute("UPDATE chat_threads SET agent=? WHERE id=?", (body.agent, thread_id))
    return get_chat(thread_id)


@router.delete("/api/chats/{thread_id}", status_code=204)
def delete_chat(thread_id: str):
    with db() as con:
        con.execute("DELETE FROM chat_threads WHERE id=?", (thread_id,))
    return Response(status_code=204)


@router.get("/api/projects/{project_id}/memories")
def list_memories(project_id: str):
    with db() as con:
        return rows(con.execute("SELECT * FROM memories WHERE project_id=? ORDER BY created_at DESC", (project_id,)))


@router.post("/api/projects/{project_id}/memories", status_code=201)
def add_memory(project_id: str, body: MemoryIn):
    _project(project_id)
    return agents.memory_add(project_id, body.content, "user")


@router.delete("/api/memories/{memory_id}", status_code=204)
def delete_memory(memory_id: str):
    with db() as con:
        con.execute("DELETE FROM memories WHERE id=?", (memory_id,))
    return Response(status_code=204)
