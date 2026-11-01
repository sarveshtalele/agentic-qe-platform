"""Designs test cases with oracles. Prompt: prompts/test-design-architect.md. Evals: evals/test-design-architect.json."""
from backend.maf.agents.policy import CHAT_READ, AgentPolicy

POLICY = AgentPolicy("Test designer", "Designs test cases with oracles", "low", chat_tools=frozenset(CHAT_READ), max_tokens=32_000)
