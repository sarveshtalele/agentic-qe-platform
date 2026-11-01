"""The remember agent tool."""
from __future__ import annotations

import json

from agent_framework import tool


def build(project_id: str, thread_id: str, start_run):
    from backend.maf.runtime import memory_add

    @tool(name="remember", description="Store a durable fact or user preference for this project. It will be available in all future chats.")
    def remember(fact: str) -> str:
        return json.dumps(memory_add(project_id, fact, f"chat:{thread_id}"))

    return remember
