"""The search_documents agent tool."""
from __future__ import annotations

import json

from agent_framework import tool

from backend.core import documents


def build(project_id: str):
    @tool(name="search_documents", description="Keyword search across the current version of all saved project documents.")
    def search_documents(query: str) -> str:
        return json.dumps(documents.search(project_id, query)) or "[]"

    return search_documents
