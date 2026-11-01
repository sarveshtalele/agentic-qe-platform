"""Helpers every workflow uses: repository facts, the code pack, and the Gate 0 intake."""
from __future__ import annotations

import json
from pathlib import Path

from backend.config import repo_dir
from backend.core import gates
from backend.core.security import (
    redact,
    safe_path,
)
from backend.maf.engine import RunContext
from backend.repos import ingest, scan, static_analysis

MAX_SOURCE_CHARS = 60_000

def _analysis(project_id: str) -> dict:
    repo = ingest.get(project_id)
    return repo["analysis"] if repo else {"mode": "greenfield", "languages": {}, "frameworks": [], "test_runners": [], "total_files": 0, "test_file_count": 0}


def _brief_of_analysis(a: dict) -> str:
    keep = {k: a.get(k) for k in ("mode", "languages", "frameworks", "test_runners", "test_file_count", "entrypoints", "ci")}
    keep["routes"] = a.get("routes", [])[:60]
    keep["largest_sources"] = [{"path": s["path"], "lines": s["lines"], "symbols": s["symbols"][:10]} for s in a.get("largest_sources", [])[:40]]
    return json.dumps(keep)


def code_pack(project_id: str, root: Path | None = None, paths: list[str] | None = None, limit: int = 40_000) -> str:
    """Line-numbered source for one agent message, riskiest files first and bounded in size.

    Agents get code up front instead of exploring with tools. That keeps token use predictable, and it avoids the
    long tool loops that outgrow model context.
    """
    base = root or repo_dir(project_id)
    if not base.exists():
        return "(no repository)"
    chosen = paths or static_analysis.rank_files_for_review(base, _analysis(project_id), 40)
    parts, used = [], 0
    for path in chosen:
        try:
            text = redact(scan._read(safe_path(base, path)))
        except ValueError:
            continue
        if not text:
            continue
        numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(text.splitlines(), 1))
        block = f"--- FILE {path} ---\n{numbered}\n"
        if used + len(block) > limit:
            continue
        parts.append(block)
        used += len(block)
    return "\n".join(parts) or "(no readable source files)"


async def intake(rc: RunContext, state: dict) -> dict:
    a = _analysis(rc.project_id)
    rc.log(f"Mode {a['mode']}: {a['total_files']} files, runners {a['test_runners'] or 'none'}")
    return {"mode": a["mode"]}


def intake_gate(rc: RunContext, state: dict):
    if gates.is_approved(rc.project_id, 0):
        return None
    a = _analysis(rc.project_id)
    repo = ingest.get(rc.project_id)
    source = f"{repo['kind']} {repo['url']} at {repo['commit_sha'][:10]}" if repo else "no repository"
    return {"gate": 0, "title": "Gate 0: confirm intake scope",
            "summary": f"Mode: {a['mode']}. Source: {source}. Files: {a['total_files']}. Languages: {', '.join(a['languages']) or 'none'}. "
                       "Agents read this project's repository and documents only. Generated code lands on a separate branch.",
            "payload": {"analysis": {k: a.get(k) for k in ("mode", "languages", "frameworks", "test_runners", "total_files", "test_file_count")}}}
