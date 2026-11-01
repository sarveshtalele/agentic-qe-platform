"""The verify_ledger agent tool."""
from __future__ import annotations

import json

from agent_framework import tool

from backend.core import ledger


def build(project_id: str, thread_id: str, start_run):
    @tool(name="verify_ledger", description="Verify the audit ledger's hash chain for this project.")
    def verify_ledger() -> str:
        return json.dumps(ledger.verify(project_id))

    return verify_ledger
