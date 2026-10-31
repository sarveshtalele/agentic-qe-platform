from __future__ import annotations

from typing import Any, Dict, List
from .base import AgentSkill, maf_skill


@maf_skill(name="planning_tests", description="Calculates ISO 25010 risk profile and test plan confidence")
class RiskCalculationSkill(AgentSkill):
    """
    Ported from sarveshtalele/agentic-qe skills/planning-tests/scripts/calculate-risk.ts.
    Calculates plan confidence score across controlsCovered (0-40), levelFit (0-30), scenariosDerivable (0-30).
    """

    def __init__(self):
        super().__init__(
            name="planning_tests",
            description="Computes risk scoring and gate readiness verdict.",
            category="TestPlanning"
        )

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        controls_covered = int(context.get("controls_covered", 35))
        level_fit = int(context.get("level_fit", 28))
        scenarios_derivable = int(context.get("scenarios_derivable", 27))

        score = max(0, min(100, controls_covered + level_fit + scenarios_derivable))
        verdict = "REJECT"
        if score >= 90:
            verdict = "APPROVED"
        elif score >= 70:
            verdict = "REVISE"

        return {
            "score": score,
            "verdict": verdict,
            "controls_covered": controls_covered,
            "level_fit": level_fit,
            "scenarios_derivable": scenarios_derivable,
            "ready_for_gate_2": verdict == "APPROVED",
        }
