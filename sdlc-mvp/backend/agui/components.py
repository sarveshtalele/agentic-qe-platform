from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def render_approval_card(
    request_id: str,
    nonce: str,
    control_id: str,
    action_type: str,
    target: str,
    details: Dict[str, Any],
    reason: str = "",
) -> Dict[str, Any]:
    """Generates an AG-UI Generative UI card for HITL approvals (CTL-HITL-01, CTL-HITL-03)."""
    return {
        "component_type": "approval_card",
        "props": {
            "request_id": request_id,
            "nonce": nonce,
            "control_id": control_id,
            "action_type": action_type,
            "target": target,
            "reason": reason or f"Security/Governance checkpoint triggered by {control_id}",
            "details": details,
            "actions": [
                {"label": "Approve", "action": "approve", "style": "primary"},
                {"label": "Reject", "action": "reject", "style": "danger"},
            ],
        },
    }


def render_test_execution_card(execution: Dict[str, Any]) -> Dict[str, Any]:
    """Generates an AG-UI Generative UI card for live test execution results."""
    return {
        "component_type": "test_execution_card",
        "props": {
            "passed": execution.get("passed", False),
            "total_cases": execution.get("total_cases", 0),
            "passed_cases": execution.get("passed_cases", 0),
            "failed_cases": execution.get("failed_cases", 0),
            "duration_sec": execution.get("duration_sec", 0.0),
            "output_log": execution.get("output_log", ""),
        },
    }


def render_confidence_score_card(review: Dict[str, Any]) -> Dict[str, Any]:
    """Generates an AG-UI Generative UI card for Gate 5 confidence review."""
    return {
        "component_type": "confidence_score_card",
        "props": {
            "total_score": review.get("total_score", 0),
            "verdict": review.get("verdict", "PENDING"),
            "dimension_scores": review.get("dimension_scores", {}),
            "flaws": review.get("flaws", []),
            "gate_eligible": review.get("gate_eligible", False),
        },
    }
