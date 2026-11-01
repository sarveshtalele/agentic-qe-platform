"""Answers from project data and starts workflows on request. Prompt: prompts/project-copilot.md. Evals: evals/project-copilot.json."""
from backend.maf.agents.policy import CHAT_READ, AgentPolicy

POLICY = AgentPolicy("Project copilot", "Answers from project data and starts workflows on request", "medium", chat_tools=frozenset(CHAT_READ | {"save_document", "project_status", "list_findings", "verify_ledger", "start_workflow"}))
