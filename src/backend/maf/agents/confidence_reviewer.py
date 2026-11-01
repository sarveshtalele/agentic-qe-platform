"""Scores requirements documents, plans, and releases from evidence. Prompt: prompts/confidence-reviewer.md. Evals: evals/confidence-reviewer.json."""
from backend.maf.agents.policy import AgentPolicy

POLICY = AgentPolicy("Confidence reviewer", "Scores requirements documents, plans, and releases from evidence", "low", max_tokens=4_000)
