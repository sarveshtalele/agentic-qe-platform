from __future__ import annotations

from typing import Any, Dict, List
from .base import AgentSkill, maf_skill


@maf_skill(name="tracing_coverage", description="Builds bidirectional requirement-to-testcase traceability matrix")
class TraceabilityMatrixSkill(AgentSkill):
    """
    Ported from sarveshtalele/agentic-qe skills/tracing-coverage/scripts/build-matrix.ts.
    Calculates coverage percentage, maps requirement IDs to test case IDs, and surfaces uncovered contracts.
    """

    def __init__(self):
        super().__init__(
            name="tracing_coverage",
            description="Constructs ISO 29119 requirements-to-testcase coverage matrix.",
            category="Traceability"
        )

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        requirements = context.get("requirements", [])
        test_cases = context.get("test_cases", [])

        req_ids = [r.get("id") for r in requirements if r.get("id")]
        if not req_ids:
            req_ids = ["REQ-001", "REQ-002", "REQ-003"]

        entries: List[Dict[str, Any]] = []
        covered_count = 0

        for r_id in req_ids:
            matching = [
                tc.get("caseId") or tc.get("id")
                for tc in test_cases
                if tc.get("requirementId") == r_id or tc.get("requirement_id") == r_id
            ]
            is_covered = len(matching) > 0
            if is_covered:
                covered_count += 1
            entries.append({
                "requirementId": r_id,
                "testCaseIds": matching,
                "covered": is_covered,
            })

        coverage_pct = round((covered_count / max(len(req_ids), 1)) * 100, 1)

        return {
            "entries": entries,
            "total_requirements": len(req_ids),
            "covered_requirements": covered_count,
            "uncovered_requirements": len(req_ids) - covered_count,
            "coverage_percent": coverage_pct,
            "meets_gate_criteria": coverage_pct >= 90.0,
        }
