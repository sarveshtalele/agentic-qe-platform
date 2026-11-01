"""Converts requirements to validated Gherkin. Prompt: prompts/gherkin_author.md. Evals: evals/gherkin_author.json."""
from backend.maf.agents.policy import AgentPolicy

POLICY = AgentPolicy("Gherkin author", "Converts requirements to validated Gherkin", "low", max_tokens=8_000)
