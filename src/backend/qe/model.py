"""Structured QE artifacts and the plugin's validators, ported from TypeScript to Python."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

CASE_TYPES = ("Positive", "Negative", "Negative (Boundary)", "Exception")
ORACLES = ("specified", "derived", "metamorphic", "golden")


class Requirement(BaseModel):
    id: str
    title: str
    statement: str
    type: Literal["functional", "non-functional", "security", "data", "integration"] = "functional"
    priority: Literal["P0", "P1", "P2"] = "P1"
    tier: Literal["specified", "observed", "inferred"] = "observed"
    actor: str = "system"
    file: str = ""
    line: int = 0
    quote: str = ""


class RequirementSet(BaseModel):
    requirements: list[Requirement] = Field(min_length=1)


class PlanArea(BaseModel):
    id: str
    name: str
    requirement_ids: list[str] = Field(min_length=1)
    risk: Literal["P0", "P1", "P2"]
    level: Literal["Unit", "Integration", "E2E"]
    framework: str
    rationale: str


class TestPlan(BaseModel):
    __test__ = False
    strategy: str
    areas: list[PlanArea] = Field(min_length=1)
    skipped_levels: dict[str, str] = Field(default_factory=dict)


class ConfidenceReview(BaseModel):
    score: int = Field(ge=0, le=100)
    verdict: Literal["APPROVED", "REVISE", "REJECTED"]
    issues: list[str] = Field(default_factory=list)


class TestCase(BaseModel):
    __test__ = False
    id: str
    requirement_id: str
    area_id: str = ""
    scenario: str
    type: Literal["Positive", "Negative", "Negative (Boundary)", "Exception"]
    level: Literal["Unit", "Integration", "E2E"]
    precondition: str = ""
    test_data: str = ""
    steps: list[str] = Field(min_length=1)
    expected_result: str
    oracle: Literal["specified", "derived", "metamorphic", "golden"]
    priority: Literal["P1", "P2", "P3"] = "P2"

    @field_validator("expected_result")
    @classmethod
    def concrete(cls, value: str) -> str:
        if value.strip().lower() in {"works", "ok", "success", "passes", "as expected", "tbd"}:
            raise ValueError("Expected result must be concrete and checkable")
        return value


class CaseSet(BaseModel):
    cases: list[TestCase] = Field(min_length=1)


CASE_COLUMNS = ("TC ID", "Requirement", "Scenario", "Type", "Level", "Precondition", "Test Data", "Steps", "Expected Result", "Oracle", "Priority")
_FIELDS = ("id", "requirement_id", "scenario", "type", "level", "precondition", "test_data", "steps", "expected_result", "oracle", "priority")


def _steps(text: str) -> list[str]:
    """Reads "1. a 2. b" back into steps. ponytail: a step that itself contains the next number and a dot splits early."""
    found, start, number = [], 0, 1
    while True:
        mark = re.search(rf"(?:^|\s){number}\.\s", text[start:]) if number > 1 else re.match(r"1\.\s", text)
        if not mark:
            break
        found.append((start + mark.start(), start + mark.end()))
        start, number = start + mark.end(), number + 1
    if not found:
        return [text.strip()] if text.strip() else []
    ends = [s for s, _ in found[1:]] + [len(text)]
    return [text[e:end].strip() for (_, e), end in zip(found, ends)]


def cases_from_table(content: str, existing: list[dict]) -> list[dict]:
    """Parses the test case table back into cases and validates each with TestCase. Raises ValueError listing every problem.
    Columns the table does not show (area_id) come from the earlier case with the same id."""
    lines = [ln.strip() for ln in content.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 3:
        raise ValueError("The test case table is missing")
    split = lambda ln: [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", ln.strip().strip("|"))]
    header = split(lines[0])
    if header != list(CASE_COLUMNS):
        raise ValueError(f"The table columns must be: {' | '.join(CASE_COLUMNS)}")
    known = {c["id"]: c for c in existing}
    cases, problems = [], []
    for number, line in enumerate(lines[2:], 1):
        cells = split(line)
        if len(cells) != len(CASE_COLUMNS):
            problems.append(f"Row {number} has {len(cells)} cells, expected {len(CASE_COLUMNS)}")
            continue
        raw = dict(zip(_FIELDS, cells))
        raw["steps"] = _steps(raw["steps"])
        before = known.get(raw["id"], {})
        try:
            case = TestCase(**{"area_id": before.get("area_id", ""), **raw}).model_dump()
        except ValidationError as exc:
            problems += [f"Row {number} ({raw['id'] or 'no id'}) {'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
            continue
        # a row that still says what it said keeps its stored wording, which may differ only in spacing
        cases.append(before if before and _same(before, case) else case)
    ids = [c["id"] for c in cases]
    problems += [f"Duplicate test case id {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    if not cases and not problems:
        problems.append("The table has no test cases")
    if problems:
        raise ValueError("; ".join(problems))
    return cases


def _same(a: dict, b: dict) -> bool:
    norm = lambda c: {k: (" ".join(" ".join(v).split()) if isinstance(v, list) else " ".join(str(v).split())) for k, v in c.items()}
    return norm(a) == norm(b)


def coverage_gaps(requirements: list[dict], cases: list[dict]) -> list[str]:
    """Plugin rule: each P0/P1 requirement gets 1 Positive, 2 Negative (boundary counts) and 1 Exception."""
    gaps = []
    for requirement in requirements:
        if requirement.get("priority") == "P2":
            continue
        kinds = [c["type"] for c in cases if c["requirement_id"] == requirement["id"]]
        if "Positive" not in kinds:
            gaps.append(f"{requirement['id']}: no Positive case")
        if sum(k.startswith("Negative") for k in kinds) < 2:
            gaps.append(f"{requirement['id']}: needs 2 Negative cases")
        if "Exception" not in kinds:
            gaps.append(f"{requirement['id']}: no Exception case")
    return gaps


def duplicate_scenarios(cases: list[dict]) -> list[str]:
    seen, dupes = set(), []
    for case in cases:
        key = (case["requirement_id"], case["scenario"].strip().lower())
        if key in seen:
            dupes.append(case["id"])
        seen.add(key)
    return dupes


def plan_confidence(requirements: list[dict], plan: dict) -> dict:
    """Deterministic plan score, port of calculate-risk.ts: 100 approved, 70+ revise, lower rejected."""
    mapped = {r for area in plan["areas"] for r in area["requirement_ids"]}
    must = [r["id"] for r in requirements if r.get("priority") in ("P0", "P1")]
    missing = [r for r in must if r not in mapped]
    unknown = [r for r in mapped if r not in {x["id"] for x in requirements}]
    levels = {a["level"] for a in plan["areas"]} | set(plan.get("skipped_levels", {}))
    missing_levels = sorted({"Unit", "Integration", "E2E"} - levels)
    score = 100 - 40 * (len(missing) > 0) - min(30, 5 * len(missing)) - 15 * len(missing_levels) - 10 * (len(unknown) > 0)
    score = max(score, 0)
    verdict = "APPROVED" if score == 100 else "REVISE" if score >= 70 else "REJECTED"
    issues = [f"Requirement not planned: {r}" for r in missing] + [f"Level without area or reason: {l}" for l in missing_levels] + [f"Unknown requirement: {r}" for r in unknown]
    return {"score": score, "verdict": verdict, "issues": issues}
