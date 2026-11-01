"""Derives testable requirements with quoted evidence. Prompt: prompts/requirements-analyst.md. Evals: evals/requirements-analyst.json."""
from backend.maf.agents.policy import CHAT_READ, AgentPolicy

POLICY = AgentPolicy("Requirements analyst", "Derives testable requirements with quoted evidence", "medium", chat_tools=frozenset(CHAT_READ), skills=('extracting-requirements',))
