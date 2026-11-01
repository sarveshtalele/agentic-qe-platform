"""Summarizes a repository from scan facts and code. Prompt: prompts/repo_analyst.md. Evals: evals/repo_analyst.json."""
from backend.maf.agents.policy import READ, AgentPolicy

POLICY = AgentPolicy("Repository analyst", "Summarizes a repository from scan facts and code", "medium", chat_tools=frozenset(READ | {"remember"}), max_tokens=8_000)
