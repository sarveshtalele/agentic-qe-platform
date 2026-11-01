"""The list_files agent tool."""
from __future__ import annotations

from typing import Annotated

from agent_framework import tool
from pydantic import Field

from backend.repos import scan


def build(base):
    @tool(name="list_files", description="List repository files, optionally only those whose path contains a substring.")
    def list_files(contains: Annotated[str, Field(description="Path substring filter; empty for all")] = "") -> str:
        if not base.exists():
            return "No repository connected."
        files = [f for f in scan.tree(base) if contains.lower() in f.lower()]
        return "\n".join(files[:400]) + (f"\n… {len(files) - 400} more" if len(files) > 400 else "")

    return list_files
