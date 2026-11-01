"""Scores plans and releases from evidence. Prompt: prompts/confidence_reviewer.md. Evals: evals/confidence_reviewer.json."""
from backend.maf.agents.policy import AgentPolicy

POLICY = AgentPolicy("Confidence reviewer", "Scores plans and releases from evidence", "low", max_tokens=4_000)
