"""Helpers every workflow uses: repository facts, the code pack, and the Gate 0 intake."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Awaitable, Callable

from backend.config import RUN_TOKEN_LIMIT, repo_dir
from backend.core import gates
from backend.core.errors import AllowanceError
from backend.core.security import (
    redact,
    safe_path,
)
from backend.maf.engine import RunContext
from backend.db import db
from backend.maf import runtime
from backend.maf.runtime import AgentCall
from backend.qe import confidence, model
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


def _window(numbered: list[str], lines: list[int], radius: int) -> str:
    """Only the numbered lines within `radius` of the given lines, with a gap marker between separate runs."""
    keep = sorted({n for line in lines for n in range(max(line - radius, 1), min(line + radius, len(numbered)) + 1)})
    out, last = [], 0
    for n in keep:
        out.append("..." if last and n > last + 1 else "")
        out.append(numbered[n - 1])
        last = n
    return "\n".join(x for x in out if x)


def code_pack(project_id: str, root: Path | None = None, paths: list[str] | None = None, limit: int = 40_000, around: dict[str, list[int]] | None = None, radius: int = 40) -> str:
    """Line-numbered source for one agent message, riskiest files first and bounded in size.

    `around` maps a path to cited lines: for those files only the lines within `radius` of a citation are sent, with their real line numbers.

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
        numbered = [f"{i}: {line}" for i, line in enumerate(text.splitlines(), 1)]
        shown = _window(numbered, around[path], radius) if around and around.get(path) else "\n".join(numbered)
        block = f"--- FILE {path} ---\n{shown}\n"
        if used + len(block) > limit:
            continue
        parts.append(block)
        used += len(block)
    return "\n".join(parts) or "(no readable source files)"


REVIEW_EVIDENCE_CHARS = 12_000  # one review batch's whole evidence; the rubric is in the agent's prompt and is never cut


def review_evidence(project_id: str, requirements: list[dict], root: Path | None = None, limit: int = REVIEW_EVIDENCE_CHARS) -> str:
    """What one review batch needs: the requirements its items cover with their quotes, and the source lines near each citation.

    The reviewer's own citations are still checked on disk by code, so a smaller view cannot make a case pass.
    """
    head = "REQUIREMENTS:\n" + json.dumps([{k: r.get(k, "") for k in ("id", "priority", "statement", "file", "line", "quote")} for r in requirements])
    around: dict[str, list[int]] = {}
    for r in requirements:
        if r.get("file"):
            around.setdefault(r["file"], []).append(int(r.get("line") or 1))
    code = code_pack(project_id, root, list(around), max(limit - len(head) - 200, 0), around) if around else "(the requirements cite no file)"
    return f"{head}\n\nCODE NEAR EACH CITATION (line numbers are before each line):\n{code}"[:limit]  # ponytail: a batch of very many requirements is cut at the end


LOW_CONFIDENCE = 70


async def review_artifact(rc: RunContext, name: str, artifact: str, evidence: str = "") -> dict:
    """An independent score before a person approves. If the review cannot run, the result says so and carries no score."""
    try:
        review = await AgentCall(rc.run_id, rc.project_id, "confidence-reviewer", skills=()).typed(f"Review type: evidence. Score this {name} from the evidence.\n\nWORK:\n{artifact[:30_000]}\n\nEVIDENCE:\n{evidence[:25_000]}", model.ConfidenceReview)
    except AllowanceError:
        raise
    except RuntimeError as exc:
        rc.log(f"Confidence review of {name} did not run: {str(exc)[:200]}", kind="warning")
        return {"score": None, "verdict": "NOT RUN", "issues": [str(exc)[:300]]}
    rc.log(f"Confidence review of {name}: {review.score} ({review.verdict})", {"issues": review.issues}, "review")
    return review.model_dump()


def _id_of(text: str) -> str:
    found = re.search(r'"id":\s*"([^"]+)"', text)
    return found.group(1) if found else ""


def _review_budget_left(rc: RunContext) -> bool:
    """Reviews stop first when tokens run low, so a run can still generate and run its tests. A third of the run's limit is kept for that."""
    with db() as con:
        found = con.execute("SELECT tokens_in+tokens_out FROM runs WHERE id=?", (rc.run_id,)).fetchone()
    return not found or found[0] < runtime.RUN_TOKEN_LIMIT * 2 // 3


NOT_REVIEWED = "Not reviewed: the token budget is kept for generating and running tests"


async def review_cases(rc: RunContext, kind: str, label: str, entries: list[tuple[str, str]], evidence: str | Callable[[list[str]], str], source: Path | None, batch: int = 8) -> tuple[list[dict], int]:
    """Scores each item separately. Batches run together within the model limit. Code checks every record and recomputes totals and verdicts.

    `evidence` is a text, or a function of a batch's item keys. Returns one record per entry, in order, and the tokens used.
    A reply that cannot be used splits its batch in half, each half asked once more; items still unanswered are NOT RUN, with no score and no pass.
    """
    batches = [entries[i : i + batch] for i in range(0, len(entries), batch)]
    calls: list[AgentCall] = []
    norm = lambda key: re.sub(r"[\s\[\]]", "", str(key)).lower()

    async def ask(chunk: list[tuple[str, str]]) -> dict[str, dict]:
        """The checked records of the items the reviewer answered, by item key. An answer names the key, or the case's own id."""
        call = AgentCall(rc.run_id, rc.project_id, "confidence-reviewer", skills=())
        calls.append(call)
        shown = "\n\n".join(f"[{key}]\n{text}" for key, text in chunk)
        seen = evidence([key for key, _ in chunk]) if callable(evidence) else evidence
        review = await call.typed(f"Review type: {label}.\nScore each item below separately against the rubric for this review type. Send one record for every item, with the item's id (the text in square brackets, such as C1) as tc_id.\n\nITEMS:\n{shown}\n\nEVIDENCE:\n{seen[:40_000]}", confidence.Review, attempts=2)
        sent: dict[str, dict] = {}
        for item in review.items:
            sent.setdefault(norm(item.tc_id), item.model_dump())
        found = {}
        for key, text in chunk:
            raw = sent.get(norm(key)) or (sent.get(norm(own)) if (own := _id_of(text)) else None)
            if raw:
                found[key] = confidence.check_item({**raw, "tc_id": key}, kind, source)
        return found

    async def one(chunk: list[tuple[str, str]]) -> list[dict]:
        if not _review_budget_left(rc):
            rc.log(f"Confidence review of {label}: {NOT_REVIEWED}", {"items": [key for key, _ in chunk]}, "warning")
            return [confidence.not_run(key, kind, NOT_REVIEWED) for key, _ in chunk]
        try:
            found = await ask(chunk)
        except AllowanceError:
            raise
        except Exception as exc:
            if len(chunk) < 2:
                raise
            rc.log(f"Confidence review of {label}: a reply for {len(chunk)} items was unusable ({str(exc)[:160]}). Asking again in two halves", kind="warning")
            half = len(chunk) // 2
            parts = await asyncio.gather(ask(chunk[:half]), ask(chunk[half:]), return_exceptions=True)
            found = {}
            for part, sub in zip(parts, (chunk[:half], chunk[half:])):
                if isinstance(part, BaseException) and not isinstance(part, Exception):
                    raise part
                if isinstance(part, AllowanceError):
                    raise part
                if isinstance(part, Exception):  # only this half is lost
                    rc.log(f"Confidence review of {label} did not run for {len(sub)} items: {str(part)[:200]}", {"items": [key for key, _ in sub]}, "warning")
                    found |= {key: confidence.not_run(key, kind, str(part)) for key, _ in sub}
                else:
                    found |= part
        if missing := [(key, text) for key, text in chunk if key not in found]:
            try:  # a reviewer that leaves items out of a large batch is asked once more for just those
                found |= await ask(missing)
            except AllowanceError:
                raise
            except Exception as exc:
                rc.log(f"Confidence review of {label}: {len(missing)} items had no record and the second ask failed: {str(exc)[:160]}", kind="warning")
        return [found.get(key) or confidence.not_run(key, kind, "The reviewer sent no record for this item") for key, _ in chunk]

    outcomes = await asyncio.gather(*(one(chunk) for chunk in batches), return_exceptions=True)
    records: list[dict] = []
    for chunk, outcome in zip(batches, outcomes):
        if isinstance(outcome, BaseException) and not isinstance(outcome, Exception):
            raise outcome  # cancellation
        if isinstance(outcome, AllowanceError):
            raise outcome  # a limit is not a bad reply
        if isinstance(outcome, Exception):
            rc.log(f"Confidence review of {label} did not run for {len(chunk)} items: {str(outcome)[:200]}", {"items": [key for key, _ in chunk]}, "warning")
            records += [confidence.not_run(key, kind, str(outcome)) for key, _ in chunk]
        else:
            records += outcome
    return records, sum(call.tokens for call in calls)


async def review_with_send_back(rc: RunContext, kind: str, label: str, entries: list[tuple[str, str]], evidence_for: Callable[[list[int]], str], source: Path | None,
                                revise: Callable[[int, dict, list[AgentCall]], Awaitable[str]], batch: int = 8) -> tuple[list[dict], dict]:
    """Reviews every item, sends each REJECT back alone to its agent, once, and reviews only those again. REVISE is never sent back, to control tokens.

    `revise(index, record, calls)` returns the new text of that item, or raises, and appends every AgentCall it makes to `calls` so failed attempts are counted too. A failed revision leaves the item as it was, still REJECT and shown.
    """
    index = {key: i for i, (key, _) in enumerate(entries)}
    records, spent = await review_cases(rc, kind, label, entries, lambda keys: evidence_for([index[k] for k in keys]), source, batch)
    tokens = {"review": spent, "revise": 0}
    rejected = [i for i, record in enumerate(records) if record["verdict"] == "REJECT"] if _review_budget_left(rc) else []
    revised: dict[int, str] = {}
    revise_calls: list[AgentCall] = []
    if rejected:
        outcomes = await asyncio.gather(*(revise(i, records[i], revise_calls) for i in rejected), return_exceptions=True)
        for i, outcome in zip(rejected, outcomes):
            if isinstance(outcome, BaseException) and not isinstance(outcome, Exception):
                raise outcome
            if isinstance(outcome, AllowanceError):
                raise outcome
            if isinstance(outcome, Exception):
                rc.log(f"{entries[i][0]} could not be revised after review: {str(outcome)[:200]}", kind="warning")
                records[i]["problems"] = [*records[i].get("problems", []), f"Sent back once, but the revision failed: {str(outcome)[:200]}"]
                records[i]["round"] = 1
            else:
                revised[i] = outcome
        if revised:
            again = [(entries[i][0], text) for i, text in revised.items()]
            second, spent = await review_cases(rc, kind, label, again, lambda keys: evidence_for([index[k] for k in keys]), source, batch)
            tokens["review"] += spent
            for i, record in zip(revised, second):
                first = records[i]
                if record["status"] == "NOT RUN":  # the first REJECT stays visible rather than turning into a blank
                    first["problems"] = [*first.get("problems", []), "Revised once, but the second review did not run, so this is the first review"]
                    continue
                records[i] = {**record, "round": 2, "first_round": {"total": first.get("total"), "verdict": first["verdict"], "flaws": first.get("flaws", [])}}
    tokens["revise"] = sum(call.tokens for call in revise_calls)
    for record in records:
        record.setdefault("round", 1)
    tokens["total"] = tokens["review"] + tokens["revise"]
    sent = len(rejected)
    rc.log(f"Confidence review of {label}: {len(records)} items, {sent} sent back once, {sum(1 for r in records if r['verdict'] == 'REJECT')} still REJECT, {tokens['total']} tokens ({tokens['review']} review, {tokens['revise']} revision)",
           {"tokens": tokens, "sent_back": [entries[i][0] for i in rejected]}, "review")
    return records, tokens


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


def token_line(run_id: str) -> dict:
    """Tokens this run has used against its limit, for the gate."""
    with db() as con:
        row = con.execute("SELECT tokens_in+tokens_out FROM runs WHERE id=?", (run_id,)).fetchone()
    used = row[0] if row else 0
    return {"used": used, "limit": RUN_TOKEN_LIMIT, "left": max(RUN_TOKEN_LIMIT - used, 0), "text": f"Tokens: {used:,} used of {RUN_TOKEN_LIMIT:,}, {max(RUN_TOKEN_LIMIT - used, 0):,} left."}


def token_estimate(run_id: str, agent: str | None, calls: int, next_step: str, basis: str) -> dict:
    """What the next step will probably cost, from model calls this run has already made. Nothing is invented: with no recorded call to average, the estimate is null and says why.

    `agent` limits the average to one agent's calls; None averages every call in the run.
    """
    with db() as con:
        used = con.execute("SELECT tokens_in+tokens_out FROM runs WHERE id=?", (run_id,)).fetchone()
        count, total = con.execute(f"SELECT COUNT(*), COALESCE(SUM(tokens_in+tokens_out), 0) FROM agent_calls WHERE run_id=? AND status='ok' AND tokens_in+tokens_out>0{' AND agent=?' if agent else ''}",
                                   (run_id, agent) if agent else (run_id,)).fetchone()
    average = round(total / count) if count else None
    return {"used_so_far": used[0] if used else 0, "run_limit": RUN_TOKEN_LIMIT, "next_step": next_step, "average_agent": agent or "all agents", "recorded_calls": count,
            "average_tokens_per_call": average, "expected_calls": calls, "estimated_tokens": average * calls if average is not None else None,
            "basis": basis if average is not None else f"No call by {agent or 'any agent'} is recorded in this run yet, so there is nothing to base an estimate on."}
