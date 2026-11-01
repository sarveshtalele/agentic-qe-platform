"""The list_documents agent tool."""
from __future__ import annotations

import json
from typing import Annotated

from agent_framework import tool
from pydantic import Field

from backend.core import documents


def build(project_id: str):
    @tool(name="list_documents", description="List saved project documents, optionally by kind (brd, prd, stories, gherkin, requirements, test_plan, test_cases, release, patch, discovery).")
    def list_documents(kind: Annotated[str, Field(description="Document kind or empty for all")] = "") -> str:
        items = documents.list_for(project_id, kind or None)
        return json.dumps([{k: d[k] for k in ("id", "kind", "title", "status", "current_version", "updated_at")} for d in items]) if items else "No documents saved yet."

    return list_documents
