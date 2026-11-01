"""Writes requirements documents from a brief and sources. Prompt: prompts/business_analyst.md. Evals: evals/business_analyst.json."""
from backend.maf.agents.policy import CHAT_READ, AgentPolicy

POLICY = AgentPolicy("Business analyst", "Writes requirements documents from a brief and sources", "low", chat_tools=frozenset(CHAT_READ | {"save_document"}))
