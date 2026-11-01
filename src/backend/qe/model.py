"""Structured QE artifacts and the plugin's validators, ported from TypeScript to Python."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

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
