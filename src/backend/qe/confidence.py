"""Per-case confidence, ported from the plugin's confidence.ts. The reviewer model scores; this code decides.

The total is the sum of the scores, the verdict follows the rule, and every cited file:line must exist in the repository
under test. A score whose evidence cannot be found is a REJECT, so an invented review cannot pass a weak case.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.core.security import PathEscape, safe_path

RUBRIC: dict[str, dict[str, int]] = {
    "design": {"source_proven": 30, "correct_target": 25, "expected_derivable": 25, "fixture_validity": 20},
    "code": {"compilable": 30, "assertion_integrity": 30, "import_safety": 20, "traceability_present": 20},
    "plan": {"controls_covered": 40, "level_fit": 30, "scenarios_derivable": 30},
}
THRESHOLD = 70  # under this total a case is low confidence
ASSERTION_FLOOR = 20  # a test whose assertions score under this can pass with the code under test removed, so it is low at any total
MAX_FILE_BYTES = 5 * 1024 * 1024
TEST_FAIL_CAP = 60  # a reviewed test that failed in execution cannot show more than this
RANK = {"APPROVED": 0, "REVISE": 1, "REJECT": 2}


class Component(BaseModel):
    file: str = ""
    line: int = 0
    symbol: str = ""


class Flaw(BaseModel):
    dimension: str = ""
    evidence: str = ""
    fix: str = ""


class Item(BaseModel):
    tc_id: str
    file: str = ""
    component: Component | None = None
    scores: dict[str, int | float | str] = Field(default_factory=dict)
    total: int | float | str | None = 0
    verdict: str = ""
    flaws: list[Flaw] = Field(default_factory=list)


class Review(BaseModel):
    """What the reviewer returns. Every number in it is a claim that `check_item` verifies."""

    kind: str = ""
    items: list[Item] = Field(min_length=1)


def verdict_for(total: int) -> str:
    return "APPROVED" if total == 100 else "REVISE" if total >= THRESHOLD else "REJECT"


def worst(*verdicts: str) -> str:
    return max(verdicts, key=lambda v: RANK.get(v, 2))


def parse_cite(text: Any) -> tuple[str, int, int] | None:
    """`path:line` or `path:line-line`, relative to the repository root; None when it has another shape."""
    found = re.fullmatch(r"([^:\s][^:]*):(\d+)(?:-(\d+))?", str(text or "").strip())
    return (found.group(1), int(found.group(2)), int(found.group(3) or found.group(2))) if found else None


def _whole(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def cite_status(root: Path, file: str, line: int | None = None) -> str:
    """"ok", "escape" (outside the repository), or "missing" (no such regular file of at most 5 MB, or the line is past its end)."""
    try:
        target = safe_path(root, file)
    except (PathEscape, OSError, ValueError):
        return "escape"
    try:
        if not target.is_file() or target.stat().st_size > MAX_FILE_BYTES:
            return "missing"
        if line is None:
            return "ok"
        data = target.read_bytes()
    except OSError:
        return "missing"
    lines = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
    return "ok" if 1 <= line <= lines else "missing"


def check_item(item: dict, kind: str, source: Path | None, strict: bool = True) -> dict:
    """One review record, checked. `source` is the folder the citations point into; None means there is nothing to check against.

    Returns the record with `total` (the sum, by code), `verdict` (computed), `effective` (after the evidence checks), `evidence`,
    `low`, `low_reason`, `problems`, and flaws with their file and line split out.
    """
    rubric, problems = RUBRIC[kind], []
    scores = item.get("scores") if isinstance(item.get("scores"), dict) else {}
    total = 0
    for dimension, top in rubric.items():
        value = scores.get(dimension)
        if not _whole(value) or not 0 <= value <= top:
            problems.append(f"{dimension} must be a whole number from 0 to {top} (got {value if value is not None else 'nothing'})")
        else:
            total += value
    problems += [f"unknown dimension {name}" for name in scores if name not in rubric]
    claimed = item.get("total")
    if claimed != total:
        problems.append(f"total {claimed} does not equal the sum of the scores ({total}); the sum is used")
    computed = verdict_for(total)
    if item.get("verdict") != computed:
        problems.append(f"verdict {item.get('verdict')} does not follow the rule for {total} ({computed}); the rule is used")
    flaws = []
    for flaw in item.get("flaws") or []:
        cite = parse_cite(flaw.get("evidence"))
        if not cite or not str(flaw.get("fix", "")).strip():
            problems.append(f"flaw \"{flaw.get('dimension') or '?'}\" needs evidence as path:line and a fix")
        flaws.append({**flaw, "file": cite[0] if cite else "", "line": cite[1] if cite else None})
    if computed != "APPROVED" and not flaws:
        problems.append("a score below 100 must name each flaw with its evidence and fix")
    component = item.get("component") or {}
    reject = False
    if kind == "design" and (not component.get("file") or not _whole(component.get("line")) or component["line"] < 1):
        problems.append("the component under test (file, line, symbol) is missing")
        reject = True
    if kind == "code" and not item.get("file"):
        problems.append("the test file is missing")
        reject = True
    evidence, missing = "not-checked", []
    if source is not None and source.exists():
        cites: list[tuple[str, int | None]] = []
        if kind == "design" and component.get("file"):
            cites.append((component["file"], component.get("line") if _whole(component.get("line")) else None))
        if kind == "code" and item.get("file"):
            cites.append((item["file"], None))
        for flaw in flaws:
            cite = parse_cite(flaw["evidence"])
            if cite:
                cites += [(cite[0], cite[1]), (cite[0], cite[2])]
        escaped = False
        for file, line in cites:
            state = cite_status(source, file, line)
            escaped |= state == "escape"
            if state != "ok" and (label := f"{file}:{line}" if line else file) not in missing:
                missing.append(label)
        evidence = "verified" if not missing else "missing" if strict else "not-checked"
        if missing and strict:
            problems.append(("cited path is outside the repository: " if escaped else "cited evidence not found in the repository: ") + ", ".join(missing[:3]) + (f" (+{len(missing) - 3})" if len(missing) > 3 else ""))
    effective = "REJECT" if evidence == "missing" or reject else computed
    assertion = scores.get("assertion_integrity") if kind == "code" else None
    if effective == "REJECT":
        low_reason = "verdict REJECT"
    elif total < THRESHOLD:
        low_reason = f"total {total} is under {THRESHOLD}"
    elif _whole(assertion) and assertion < ASSERTION_FLOOR:
        low_reason = f"assertion integrity {assertion}/30 is under {ASSERTION_FLOOR}: the test may pass without proving the behaviour"
    else:
        low_reason = ""
    return {"tc_id": item.get("tc_id", ""), "kind": kind, "file": item.get("file", ""), "component": component or None, "scores": scores, "claimed_total": claimed, "total": total,
            "verdict": effective, "scored_verdict": computed, "evidence": evidence, "low": bool(low_reason), "low_reason": low_reason, "flaws": flaws, "problems": problems, "status": "reviewed"}


def not_run(tc_id: str, kind: str, reason: str) -> dict:
    """The honest result of a review that could not run: no score, never a pass."""
    return {"tc_id": tc_id, "kind": kind, "status": "NOT RUN", "verdict": "NOT RUN", "total": None, "evidence": "not-checked", "low": True, "low_reason": "review did not run", "flaws": [], "problems": [reason[:300]], "scores": {}}


def check_doc(review: dict, kind: str, source: Path | None, strict: bool = True) -> dict:
    """Checks every record of a review ({items}) and summarises it."""
    records = [check_item(item, kind, source, strict) for item in review.get("items", []) if item.get("tc_id")]
    return {"items": records, "summary": summarise(records)}


def summarise(records: list[dict], tokens: dict | None = None) -> dict:
    """The roll-up kept under `cases_review`, `tests_review` and `plan_review`. Verdict by the worst rule; a case that did not run counts as REVISE, never APPROVED."""
    done = [r for r in records if r.get("status") == "reviewed"]
    verdicts = [r["verdict"] for r in records]
    if not done:
        verdict = "NOT RUN"
    elif "REJECT" in verdicts:
        verdict = "REJECT"
    elif "REVISE" in verdicts or len(done) < len(records):
        verdict = "REVISE"
    else:
        verdict = "APPROVED"
    issues = [f"{r['tc_id']}: {f.get('dimension') or 'flaw'} at {f['evidence']}. Fix: {f['fix']}" for r in records for f in r.get("flaws", [])][:30]
    issues += [f"{r['tc_id']}: NOT RUN. {r['problems'][0] if r.get('problems') else ''}" for r in records if r.get("status") == "NOT RUN"][:10]
    return {"score": round(sum(r["total"] for r in done) / len(done)) if done else None, "verdict": verdict, "issues": issues[:40],
            "counts": {"cases": len(records), "approved": verdicts.count("APPROVED"), "revise": verdicts.count("REVISE"), "reject": verdicts.count("REJECT"), "not_run": len(records) - len(done),
                       "low": sum(1 for r in records if r.get("low")), "evidence_missing": sum(1 for r in records if r.get("evidence") == "missing")},
            "tokens": tokens or {}, "records": records}


def cap_failed(records: list[dict], executed: dict[str, str]) -> dict:
    """After execution: a reviewed test that FAILED shows at most TEST_FAIL_CAP. `executed` maps a case id to passed, failed, skipped or not run."""
    capped = []
    for record in records:
        if record.get("status") == "reviewed" and executed.get(record["tc_id"]) == "failed":
            total = min(record["total"], TEST_FAIL_CAP)
            capped.append({**record, "total_before": record["total"], "total": total, "capped": True, "verdict": worst(record["verdict"], verdict_for(total)),
                           "low": True, "low_reason": f"the test failed when it ran, so its score is capped at {TEST_FAIL_CAP}"})
        else:
            capped.append({**record, "capped": False})
    before = summarise(records)
    summary = summarise(capped)
    return {**summary, "score_before": before["score"], "capped": sum(1 for r in capped if r["capped"]), "failed": sum(1 for r in records if executed.get(r["tc_id"]) == "failed"),
            "executed": sum(1 for r in records if executed.get(r["tc_id"]) in {"passed", "failed"})}


def reject_ids(payload: dict) -> list[str]:
    """Ids of the records on a gate that code judged REJECT, for the rule that a person approving them must give a reason."""
    review = payload.get("confidence") or {}
    return [r.get("tc_id", "?") for r in review.get("records", []) if r.get("verdict") == "REJECT"]


def flaw_lines(record: dict) -> str:
    """The flaws and fixes of one record, as the text an agent receives when its item is sent back."""
    return "\n".join(f"- {f.get('dimension') or 'flaw'} at {f['evidence']}. Fix: {f['fix']}" for f in record.get("flaws", [])) or "- " + "; ".join(record.get("problems", [])[:3])
