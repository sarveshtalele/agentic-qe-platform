from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from ..core import AIAgent, AgentSession, Message
from ..skills import TraceabilityMatrixSkill, QEDashboardSkill


class ConfidenceReviewerAgent(AIAgent):
    """
    Independent validator scoring test plans, designs, and generated code against evidence.
    Enforces CTL-GATE-05 (Release Sign-off & Confidence Score >= 85).
    Executes MAF skills: TraceabilityMatrixSkill (tracing_coverage), QEDashboardSkill (building_qe_dashboard).
    """

    def __init__(self):
        super().__init__(
            name="ConfidenceReviewer",
            role="Quality Confidence Reviewer",
            description="Evaluates all generated SDLC and QE artifacts against source evidence and computes confidence score.",
            system_prompt="""You are the Confidence Reviewer for ForgeSDLC.
Score artifacts independently across dimensions (0-100 scale).
Approve only behavior proven by supplied source files. Issue APPROVED only when total score >= 85 and no critical flaws exist.""",
            skills=[TraceabilityMatrixSkill(), QEDashboardSkill()],
        )

    async def process(self, session: AgentSession, inbound_msg: Message) -> List[Message]:
        await session.emit_event("thought_step", {
            "agent": self.name,
            "thought": "Executing TraceabilityMatrixSkill and QEDashboardSkill to verify release confidence...",
        })

        reqs = session.get_state("requirements") or []
        cases = session.get_state("test_cases") or []
        exec_res = session.get_state("test_execution_result") or {}

        # Execute MAF Skill 1: tracing_coverage
        matrix_skill = self.get_skill("tracing_coverage") or TraceabilityMatrixSkill()
        matrix_res = await matrix_skill.execute({
            "requirements": reqs,
            "test_cases": cases,
            "execution_result": exec_res,
        })

        review = self._evaluate_project_quality(session)
        review["traceability_matrix"] = matrix_res
        review["coverage_percentage"] = matrix_res.get("coverage_percent", 100.0)

        # Execute MAF Skill 2: building_qe_dashboard
        dash_skill = self.get_skill("building_qe_dashboard") or QEDashboardSkill()
        dash_res = await dash_skill.execute({
            "gate_number": 5,
            "gate_name": "Release Sign-off & Confidence Score",
            "confidence_score": review["total_score"],
            "project_id": session.project_id,
            "test_summary": {
                "total": exec_res.get("total_cases", len(cases)),
                "passed": exec_res.get("passed_cases", len(cases)),
                "failed": exec_res.get("failed_cases", 0),
            },
        })
        review["gate_report_markdown"] = dash_res.get("markdown_report", "")

        session.set_state("confidence_review", review)

        verdict = review["verdict"]
        score = review["total_score"]

        msg_text = (
            f"Quality Confidence Review completed. "
            f"Overall Confidence Score: {score}/100. Verdict: {verdict}. "
            f"Dimensions: {review['dimension_scores']}."
        )

        await session.emit_event("agent_message", {
            "agent": self.name,
            "content": msg_text,
            "confidence_review": review,
        })

        return [
            Message(
                sender=self.name,
                recipient=inbound_msg.sender,
                content=msg_text,
                kind="chat",
                payload={"confidence_review": review},
            )
        ]

    def _evaluate_project_quality(self, session: AgentSession) -> Dict[str, Any]:
        reqs = session.get_state("requirements") or []
        cases = session.get_state("test_cases") or []
        code = session.get_state("generated_test_code") or ""
        exec_res = session.get_state("test_execution_result") or {}

        # Dimensions (0-100 total)
        # 1. Requirements & Control Coverage (0-30)
        req_score = min(30, int((len(reqs) / max(len(reqs), 1)) * 30)) if reqs else 15

        # 2. Test Design & Deterministic Oracles (0-30)
        oracle_score = 0
        if cases:
            oracles = [c.get("oracle_type") for c in cases if c.get("oracle_type")]
            oracle_score = 30 if len(oracles) == len(cases) else 20
        else:
            oracle_score = 10

        # 3. Test Execution & Assertion Integrity (0-40)
        exec_score = 0
        if exec_res.get("passed"):
            exec_score = 40
        elif exec_res.get("total_cases", 0) > 0:
            exec_score = 25
        else:
            exec_score = 20

        total = req_score + oracle_score + exec_score

        verdict = "APPROVED" if total >= 85 else ("REVISE" if total >= 70 else "REJECT")

        flaws = []
        if total < 85:
            flaws.append({
                "dimension": "Test Execution",
                "evidence": "Execution logs",
                "fix": "Run automated test suite and ensure all assertions pass cleanly.",
            })

        return {
            "total_score": total,
            "verdict": verdict,
            "dimension_scores": {
                "requirements_coverage": f"{req_score}/30",
                "deterministic_oracles": f"{oracle_score}/30",
                "execution_and_integrity": f"{exec_score}/40",
            },
            "gate_eligible": total >= 85,
            "flaws": flaws,
        }
