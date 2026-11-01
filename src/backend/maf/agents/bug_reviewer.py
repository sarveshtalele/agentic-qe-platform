"""Finds defects in code it is given. Prompt: prompts/bug_reviewer.md. Evals: evals/bug_reviewer.json."""
from backend.maf.agents.policy import READ, AgentPolicy

POLICY = AgentPolicy("Bug reviewer", "Finds defects in code it is given", "medium", chat_tools=frozenset(READ | {"list_findings", "remember"}))
