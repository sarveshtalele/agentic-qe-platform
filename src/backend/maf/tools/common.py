"""Helpers shared by tools."""
from __future__ import annotations

from backend.core import documents


def owned_document(project_id: str, doc_id: str) -> dict:
    """A tool may only reach documents of its own project."""
    doc = documents.get(doc_id)
    if doc["project_id"] != project_id:
        raise KeyError(doc_id)
    return doc
