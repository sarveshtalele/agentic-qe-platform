"""The save_document agent tool."""
from __future__ import annotations

import json

from agent_framework import tool

from backend.core import documents
from backend.maf.tools.common import owned_document


def build(project_id: str):
    @tool(name="save_document", description="Save new text as a new version of a document. Earlier versions stay restorable. Use only when the user asks for a change.")
    def save_document(document_id: str, content: str, note: str) -> str:
        try:
            owned_document(project_id, document_id)
            return json.dumps({"saved_version": documents.save_version(document_id, content, "agent:chat", note=note)["version"]})
        except (KeyError, documents.DocumentError) as exc:
            return f"Not saved: {exc}"

    return save_document
