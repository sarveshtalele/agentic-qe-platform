"""Bug scan workflow: fan-out static and agent review, fan-in with evidence checks."""
from __future__ import annotations

import asyncio

from pydantic import BaseModel

from backend.config import repo_dir
from backend.db import db, new_id, now
from backend.maf.engine import REGISTRY, Definition, FanOut, RunContext, StageSpec
from backend.maf.runtime import AgentCall
from backend.maf.workflows.shared import (
    _analysis,
    code_pack,
)
from backend.repos import git, static_analysis


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
    rc.log(f"Scanning commit {git.head(root)[:10] or 'snapshot'}")
    return {}


async def scan_static(rc: RunContext, state: dict) -> dict:
    found = await asyncio.to_thread(static_analysis.run_all, repo_dir(rc.project_id))
    rc.log(f"Static analysis produced {len(found)} findings", {"sources": sorted({f['source'] for f in found})})
    return {"static": found}


async def scan_llm(rc: RunContext, state: dict) -> dict:
    root = repo_dir(rc.project_id)
    targets = static_analysis.rank_files_for_review(root, _analysis(rc.project_id), int(state.get("review_files", 8)))
    rc.log(f"Agent review of {len(targets)} highest-risk files", {"files": targets})
    gate = asyncio.Semaphore(4)

    async def review(path: str) -> list[dict]:
        async with gate:
            try:
                result = await AgentCall(rc.run_id, rc.project_id, "bug_reviewer").typed(f"Review {path} for real defects.\n\n{code_pack(rc.project_id, paths=[path], limit=25_000)}", ReviewFindings)
            except RuntimeError as exc:
                rc.log(f"Review of {path} produced no usable result: {exc}", kind="warning")
                return []
        return [{**f.model_dump(), "file": f.file or path} for f in result.findings]

    batches = await asyncio.gather(*(review(p) for p in targets))
    return {"llm": [f for batch in batches for f in batch], "reviewed_files": targets}


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
    rc.log(f"{len(static)} static and {len(verified)} verified agent findings; {rejected} agent claims rejected for missing evidence; {added} new", kind="artifact")
    return {**base, "static_count": len(static), "agent_verified": len(verified), "agent_rejected": rejected, "new_findings": added, "reviewed_files": next((b.get("reviewed_files") for b in branches if "reviewed_files" in b), [])}


def bug_scan_definition() -> Definition:
    return Definition("bug_scan", [
        StageSpec("prepare", scan_prepare, "Prepare scan", forward=True),
        StageSpec("static", scan_static, "Static analyzers", forward=True),
        StageSpec("agent_review", scan_llm, "Agent code review", forward=True),
    ], fan_out=FanOut("prepare", ["static", "agent_review"], "merge", scan_merge))


REGISTRY["bug_scan"] = bug_scan_definition
