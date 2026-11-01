"""Scores requirements documents independently. Prompt: prompts/doc_reviewer.md. Evals: evals/doc_reviewer.json."""
from backend.maf.agents.policy import AgentPolicy

POLICY = AgentPolicy("Document reviewer", "Scores requirements documents independently", "low", max_tokens=4_000)
