"""Bug scan workflow: fan-out static and agent review, fan-in with evidence checks."""
from __future__ import annotations

import asyncio

from pydantic import BaseModel

from backend.config import repo_dir
from backend.db import db, new_id, now
from backend.maf.engine import REGISTRY, Definition, FanOut, RunContext, StageSpec
from backend.maf.runtime import AgentCall
from backend.maf.workflows.shared import _analysis, review_artifact
from backend.core.errors import AllowanceError
from backend.core.security import redact, safe_path
from backend.repos import git, sandbox, scan, static_analysis


class ReviewFinding(BaseModel):
    title: str
    severity: str = "medium"
    file: str
    line: int
    quote: str
    explanation: str


class ReviewFindings(BaseModel):
    findings: list[ReviewFinding] = []


async def scan_prepare(rc: RunContext, state: dict) -> dict:
    root = repo_dir(rc.project_id)
    if not root.exists():
        raise ValueError("Connect a repository or upload a ZIP before scanning")
    if await asyncio.to_thread(sandbox.complete_history, rc.project_id):
        rc.log("Fetched the complete history for this project's sandbox")
    rc.log(f"Scanning commit {git.head(root)[:10] or 'snapshot'} in the project sandbox")
    return {}


async def scan_static(rc: RunContext, state: dict) -> dict:
    found = await asyncio.to_thread(static_analysis.run_all, repo_dir(rc.project_id))
    rc.log(f"Static analysis produced {len(found)} findings", {"sources": sorted({f['source'] for f in found})})
    return {"static": found}


PART_CHARS = 20_000


def file_parts(path: str, text: str) -> list[str]:
    """Numbered blocks for one file. A large file is split on line breaks, and its parts keep the real line numbers."""
    parts, block, size = [], [], 0
    for number, line in enumerate(text.splitlines(), 1):
        numbered = f"{number}: {line}"
        if block and size + len(numbered) > PART_CHARS:
            parts.append(block)
            block, size = [], 0
        block.append(numbered[:PART_CHARS])
        size += len(numbered) + 1
    if block:
        parts.append(block)
    return [f"--- FILE {path} ---\n" + "\n".join(lines) for lines in parts]


async def scan_llm(rc: RunContext, state: dict) -> dict:
    root = repo_dir(rc.project_id)
    limit = state.get("review_files")  # a limit is only for quick API checks: the normal scan reads every source file
    targets = static_analysis.rank_files_for_review(root, _analysis(rc.project_id), int(limit)) if limit else static_analysis.review_targets(root)
    rc.log(f"Agent review of all {len(targets)} source files" if not limit else f"Agent review of {len(targets)} files", {"files": targets[:500]})
    gate = asyncio.Semaphore(4)
    reviewed: list[str] = []
    missed: list[str] = []

    async def review(path: str) -> list[dict]:
        found: list[dict] = []
        parts = file_parts(path, redact(scan._read(safe_path(root, path))))
        try:
            for index, part in enumerate(parts, 1):
                note = f" This is part {index} of {len(parts)}, and its line numbers are the file's real ones." if len(parts) > 1 else ""
                async with gate:
                    result = await AgentCall(rc.run_id, rc.project_id, "bug-reviewer").typed(f"Review {path} for real defects.{note}\n\n{part}", ReviewFindings)
                found += [{**f.model_dump(), "file": f.file or path} for f in result.findings]
        except AllowanceError:
            raise
        except RuntimeError as exc:
            missed.append(path)
            rc.log(f"Review of {path} did not finish: {exc}", kind="warning")
            return found
        reviewed.append(path)
        rc.log(f"Reviewed {len(reviewed)} of {len(targets)}: {path}")
        return found

    batches = await asyncio.gather(*(review(p) for p in targets))
    return {"llm": [f for batch in batches for f in batch], "reviewed_files": sorted(reviewed), "unreviewed_files": sorted(missed), "source_files": len(targets)}


async def scan_merge(rc: RunContext, branches: list[dict]) -> dict:
    base = {k: v for b in branches for k, v in b.items() if k not in {"static", "llm", "_to"}}
    static = next((b["static"] for b in branches if "static" in b), [])
    llm = next((b["llm"] for b in branches if "llm" in b), [])
    root = repo_dir(rc.project_id)
    verified, rejected = [], 0
    for item in llm:  # a model claim only becomes a finding if its quote exists in the file
        ok, line = static_analysis.verify_quote(root, item["file"], item["line"], item["quote"])
        if ok:
            verified.append({"source": "agent", "rule": "REVIEW", "severity": item["severity"].lower(), "title": item["title"], "file": item["file"], "line": line, "evidence": item["quote"][:300], "explanation": item["explanation"]})
        else:
            rejected += 1
    added = 0
    with db() as con:
        for finding in static + verified:
            fingerprint = f"{finding['rule']}|{finding['file']}|{finding['evidence']}|{finding['line'] if not finding['evidence'] else ''}"
            cur = con.execute(
                "INSERT OR IGNORE INTO findings (id, project_id, run_id, source, rule, severity, title, file, line, evidence, explanation, fingerprint, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (new_id("bug"), rc.project_id, rc.run_id, finding["source"], finding["rule"], finding["severity"], finding["title"], finding["file"], finding["line"], finding["evidence"], finding["explanation"], fingerprint, now()),
            )
            added += cur.rowcount
    coverage = next(({k: b[k] for k in ("reviewed_files", "unreviewed_files", "source_files")} for b in branches if "reviewed_files" in b), {"reviewed_files": [], "unreviewed_files": [], "source_files": 0})
    rc.log(f"Reviewed {len(coverage['reviewed_files'])} of {coverage['source_files']} source files" + (f". Not reviewed: {coverage['unreviewed_files'][:20]}" if coverage["unreviewed_files"] else ""), kind="warning" if coverage["unreviewed_files"] else "artifact")
    rc.log(f"{len(static)} static and {len(verified)} verified agent findings; {rejected} agent claims rejected for missing evidence; {added} new", kind="artifact")
    review = await review_artifact(rc, "agent findings", "\n".join(f"{f['severity']} {f['file']}:{f['line']} {f['title']}. Quote: {f['evidence']}" for f in verified[:60]), f"{rejected} other claims were dropped because their quotes are not in the code") if verified else None
    return {**base, "findings_review": review, "static_count": len(static), "agent_verified": len(verified), "agent_rejected": rejected, "new_findings": added, **coverage}


def bug_scan_definition() -> Definition:
    return Definition("bug_scan", [
        StageSpec("prepare", scan_prepare, "Prepare scan", forward=True),
        StageSpec("static", scan_static, "Static analyzers", forward=True),
        StageSpec("agent_review", scan_llm, "Agent code review", forward=True),
    ], fan_out=FanOut("prepare", ["static", "agent_review"], "merge", scan_merge))


REGISTRY["bug_scan"] = bug_scan_definition
