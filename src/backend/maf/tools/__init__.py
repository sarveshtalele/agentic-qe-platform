"""MAF function tools, one file each. Every set closes over a project, so an agent can only reach that project's data.

To add a tool: add a file with build(), list it in a set here, and allow it in the agent's policy.
"""
from __future__ import annotations

from backend.config import repo_dir
from backend.maf.tools import (
    grep,
    list_documents,
    list_files,
    list_findings,
    project_status,
    read_document,
    read_file,
    remember,
    save_document,
    search_documents,
    start_workflow,
    verify_ledger,
)


def repo_tools(project_id: str, root=None) -> list:
    base = root or repo_dir(project_id)
    return [list_files.build(base), read_file.build(base), grep.build(base)]


def document_tools(project_id: str) -> list:
    return [list_documents.build(project_id), read_document.build(project_id), search_documents.build(project_id), save_document.build(project_id)]


def chat_tools(project_id: str, thread_id: str, start_run) -> list:
    return [remember.build(project_id, thread_id, start_run), project_status.build(project_id, thread_id, start_run), list_findings.build(project_id, thread_id, start_run), verify_ledger.build(project_id, thread_id, start_run), start_workflow.build(project_id, thread_id, start_run)]
