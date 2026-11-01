"""Structured edits from agents, applied by code through path, secret, and scope guards."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from backend.core.security import (
    PathEscape,
    has_masked_secret,
    safe_path,
    scan_secrets,
)
from backend.qe import execution


class Edit(BaseModel):
    path: str
    action: str = Field(description="create, replace, or delete")
    content: str = Field(default="", description="Full file for create")
    search: str = Field(default="", description="Exact text to find for replace")
    replace: str = Field(default="", description="Replacement text for replace")


def apply_edits(worktree: Path, edits: list[Edit]) -> list[str]:
    """Guard-write equivalent: confined paths, no protected directories, no secrets, exact-match replaces."""
    errors: list[str] = []
    for edit in edits:
        try:
            target = safe_path(worktree, edit.path, for_write=True)
        except PathEscape as exc:
            errors.append(str(exc))
            continue
        written = edit.content if edit.action == "create" else edit.replace
        if scan_secrets(written) or has_masked_secret(written):
            errors.append(f"{edit.path}: edit contains a secret")
            continue
        previous = target.read_text(encoding="utf-8") if target.is_file() else None
        if edit.action == "create":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(edit.content, encoding="utf-8")
        elif edit.action == "delete":
            target.unlink(missing_ok=True)
        elif edit.action == "replace":
            if not target.is_file():
                errors.append(f"{edit.path}: file not found")
                continue
            body = target.read_text(encoding="utf-8")
            if not edit.search or edit.search not in body:
                errors.append(f"{edit.path}: search text not found exactly")
                continue
            target.write_text(body.replace(edit.search, edit.replace, 1), encoding="utf-8")
        else:
            errors.append(f"{edit.path}: unknown action {edit.action}")
        issue = execution.syntax_error(edit.path, target.read_text(encoding="utf-8")) if target.is_file() else None
        if issue:
            # an edit that breaks the file never stays on disk, or every test would fail to load
            if previous is None:
                target.unlink(missing_ok=True)
            else:
                target.write_text(previous, encoding="utf-8")
            errors.append(f"{issue}. The edit was not applied")
    return errors


class ChangeSet(BaseModel):
    summary: str
    edits: list[Edit] = []


def guarded_apply(worktree: Path, edits: list[Edit], guard=None) -> tuple[list[str], list[str]]:
    """Apply agent edits through every guard. Returns what changed and refusals the agent can act on."""
    applied, refused = [], []
    for edit in edits:
        try:
            exists = safe_path(worktree, edit.path).exists()
        except PathEscape as exc:
            refused.append(str(exc))
            continue
        if edit.action == "create" and exists:
            refused.append(f"{edit.path} exists. Use action replace so the rest of the file stays intact.")
            continue
        if edit.action == "delete":
            refused.append(f"{edit.path}: deleting files is not allowed.")
            continue
        reason = guard(edit) if guard else None
        problems = [reason] if reason else apply_edits(worktree, [edit])
        if problems:
            refused.extend(problems)
        else:
            applied.append(edit.path)
    return applied, refused
