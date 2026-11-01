"""Writes requirements documents from a brief and sources, and converts them to validated Gherkin. Prompt: prompts/business-analyst.md. Evals: evals/business-analyst.json."""
from backend.maf.agents.policy import CHAT_READ, AgentPolicy

POLICY = AgentPolicy("Business analyst", "Writes requirements documents from a brief and sources, and converts them to validated Gherkin", "low", chat_tools=frozenset(CHAT_READ | {"save_document"}), skills=('authoring-user-stories',))
