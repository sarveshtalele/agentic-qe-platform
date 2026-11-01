"""Summarizes a repository from scan facts and code. Prompt: prompts/repo-intelligence-analyst.md. Evals: evals/repo-intelligence-analyst.json."""
from backend.maf.agents.policy import READ, AgentPolicy

POLICY = AgentPolicy("Repository analyst", "Summarizes a repository from scan facts and code", "medium", chat_tools=frozenset(READ | {"remember"}), max_tokens=8_000)
