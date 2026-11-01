"""What an agent is allowed to do. Each agent file declares one POLICY."""
from __future__ import annotations

from dataclasses import dataclass

READ = {"list_files", "read_file", "grep"}
DOCS = {"list_documents", "read_document", "search_documents"}
CHAT_READ = READ | DOCS | {"remember"}


@dataclass(frozen=True)
class AgentPolicy:
    name: str
    purpose: str
    risk: str  # low: reads and writes text. medium: reads all code. high: changes code
    workflow_tools: frozenset = frozenset()
    chat_tools: frozenset | None = None  # None means this agent is not offered in chat
    max_tokens: int = 16_000
    can_change_code: bool = False
    skills: tuple[str, ...] = ()  # folder names under skills/ (the agentic-qe plugin skills this agent applies)
