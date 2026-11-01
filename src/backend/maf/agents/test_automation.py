"""Generates executable tests for approved cases. Prompt: prompts/test_automation.md. Evals: evals/test_automation.json."""
from backend.maf.agents.policy import AgentPolicy

POLICY = AgentPolicy("Test automation", "Generates executable tests for approved cases", "medium")
