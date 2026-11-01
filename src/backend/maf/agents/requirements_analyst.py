"""Derives testable requirements with quoted evidence. Prompt: prompts/requirements_analyst.md. Evals: evals/requirements_analyst.json."""
from backend.maf.agents.policy import CHAT_READ, AgentPolicy

POLICY = AgentPolicy("Requirements analyst", "Derives testable requirements with quoted evidence", "medium", chat_tools=frozenset(CHAT_READ))
