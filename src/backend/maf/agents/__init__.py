"""Agent registry. Each file in this folder declares one agent's POLICY, so adding an agent means adding a file."""
from __future__ import annotations

import importlib
import pkgutil

from backend.maf.agents.policy import CHAT_READ, DOCS, READ, AgentPolicy

# the copilot comes first because the chat offers the first agent by default
_names = sorted((m.name for m in pkgutil.iter_modules(__path__) if m.name != "policy"), key=lambda name: (name != "copilot", name))
POLICIES: dict[str, AgentPolicy] = {name: importlib.import_module(f"{__name__}.{name}").POLICY for name in _names}

__all__ = ["CHAT_READ", "DOCS", "POLICIES", "READ", "AgentPolicy"]
