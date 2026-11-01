"""Implements features on a branch. Prompt: prompts/feature-engineer.md. Evals: evals/feature-engineer.json."""
from backend.maf.agents.policy import AgentPolicy

POLICY = AgentPolicy("Feature engineer", "Implements features on a branch", "high", can_change_code=True)
