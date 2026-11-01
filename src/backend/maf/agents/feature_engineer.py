"""Implements features on a branch. Prompt: prompts/feature_engineer.md. Evals: evals/feature_engineer.json."""
from backend.maf.agents.policy import AgentPolicy

POLICY = AgentPolicy("Feature engineer", "Implements features on a branch", "high", can_change_code=True)
