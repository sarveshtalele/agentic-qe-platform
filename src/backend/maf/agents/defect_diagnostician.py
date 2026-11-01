"""Fixes defects and test drift on a branch. Prompt: prompts/defect_diagnostician.md. Evals: evals/defect_diagnostician.json."""
from backend.maf.agents.policy import CHAT_READ, AgentPolicy

POLICY = AgentPolicy("Defect diagnostician", "Fixes defects and test drift on a branch", "high", chat_tools=frozenset(CHAT_READ), can_change_code=True)
