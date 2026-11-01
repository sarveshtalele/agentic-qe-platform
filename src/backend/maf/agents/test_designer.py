"""Designs test cases with oracles. Prompt: prompts/test_designer.md. Evals: evals/test_designer.json."""
from backend.maf.agents.policy import CHAT_READ, AgentPolicy

POLICY = AgentPolicy("Test designer", "Designs test cases with oracles", "low", chat_tools=frozenset(CHAT_READ), max_tokens=32_000)
