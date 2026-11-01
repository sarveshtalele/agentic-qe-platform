"""Agent registry. Each file in this folder declares one agent's POLICY, so adding an agent means adding a file.

The agent key is the file name with hyphens, as in the agentic-qe plugin (repo_intelligence_analyst.py is repo-intelligence-analyst),
because Python modules cannot contain hyphens. The prompt and eval files use the key.
"""
from __future__ import annotations

import importlib
import pkgutil

from backend.maf.agents.policy import CHAT_READ, DOCS, READ, AgentPolicy

# project-copilot comes first because the chat offers the first agent by default
_names = sorted((m.name for m in pkgutil.iter_modules(__path__) if m.name != "policy"), key=lambda name: (name != "project_copilot", name))
POLICIES: dict[str, AgentPolicy] = {name.replace("_", "-"): importlib.import_module(f"{__name__}.{name}").POLICY for name in _names}

__all__ = ["CHAT_READ", "DOCS", "POLICIES", "READ", "AgentPolicy"]
