"""The read_document agent tool."""
from __future__ import annotations

from typing import Annotated

from agent_framework import tool
from pydantic import Field

from backend.core import documents
from backend.maf.tools.common import owned_document


def build(project_id: str):
    @tool(name="read_document", description="Read a saved document's content. Defaults to the current version.")
    def read_document(document_id: str, version: Annotated[int, Field(description="Version number, 0 for current")] = 0) -> str:
        try:
            doc = owned_document(project_id, document_id)
            if version:
                doc = documents.get(document_id, version)
        except KeyError:
            return f"No such document: {document_id}"
        return f"# {doc['title']} ({doc['kind']} v{doc['version']}, {doc['status']})\n\n{doc['content']}"

    return read_document
