"""Explains test results from the evidence. Code runs the tests. Prompt: prompts/qa-execution-engineer.md. Evals: evals/qa-execution-engineer.json."""
from backend.maf.agents.policy import AgentPolicy

POLICY = AgentPolicy("QA execution engineer", "Explains test results from the recorded evidence", "low", max_tokens=2_000, skills=('executing-tests',))
