"""Generates executable tests for approved cases. Prompt: prompts/test-automation-engineer.md. Evals: evals/test-automation-engineer.json."""
from backend.maf.agents.policy import AgentPolicy

POLICY = AgentPolicy("Test automation", "Generates executable tests for approved cases", "medium", skills=('generating-test-code',))
