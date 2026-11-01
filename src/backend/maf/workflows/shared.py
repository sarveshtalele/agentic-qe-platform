"""Helpers every workflow uses: repository facts, the code pack, and the Gate 0 intake."""
from __future__ import annotations

import json
import re
from pathlib import Path

from backend.config import repo_dir
from backend.core import gates
from backend.core.security import (
    redact,
    safe_path,
)
from backend.maf.engine import RunContext
from backend.maf.runtime import AgentCall
from backend.qe import model
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


LOW_CONFIDENCE = 70


async def review_artifact(rc: RunContext, name: str, artifact: str, evidence: str = "") -> dict:
    """An independent score before a person approves. If the review cannot run, the result says so and carries no score."""
    try:
        review = await AgentCall(rc.run_id, rc.project_id, "confidence-reviewer").typed(f"Review type: evidence. Score this {name} from the evidence.\n\nWORK:\n{artifact[:30_000]}\n\nEVIDENCE:\n{evidence[:25_000]}", model.ConfidenceReview)
    except RuntimeError as exc:
        rc.log(f"Confidence review of {name} did not run: {str(exc)[:200]}", kind="warning")
        return {"score": None, "verdict": "NOT RUN", "issues": [str(exc)[:300]]}
    rc.log(f"Confidence review of {name}: {review.score} ({review.verdict})", {"issues": review.issues}, "review")
    return review.model_dump()


def is_low(review: dict) -> bool:
    return review["score"] is not None and review["score"] < LOW_CONFIDENCE


def discovery_pack(project_id: str, limit: int = 70_000) -> str:
    """What explains a repository from end to end comes first: its readme, manifests, and entry points, then its riskiest code."""
    a = _analysis(project_id)
    root = repo_dir(project_id)
    files = scan.tree(root, limit=100_000)
    front = [f for f in files if "/" not in f and re.match(r"(?i)(readme|pyproject\.toml|package\.json|requirements.*\.txt|dockerfile|docker-compose|makefile)", f)]
    paths = list(dict.fromkeys([*front, *a.get("entrypoints", []), *{r["file"] for r in a.get("routes", [])}, *static_analysis.rank_files_for_review(root, a, 60)]))
    return code_pack(project_id, paths=paths, limit=limit)


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
