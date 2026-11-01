"""Plans tests by risk and level. Prompt: prompts/principal-test-architect.md. Evals: evals/principal-test-architect.json."""
from backend.maf.agents.policy import CHAT_READ, AgentPolicy

POLICY = AgentPolicy("Test architect", "Plans tests by risk and level", "low", chat_tools=frozenset(CHAT_READ))
