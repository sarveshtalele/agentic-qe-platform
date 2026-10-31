from __future__ import annotations

import hashlib
import uuid
from typing import Any, Dict
from .base import AgentSkill, maf_skill


@maf_skill(name="generating_test_data", description="Synthesizes deterministic mock users, security tokens, and payloads")
class TestDataSynthesisSkill(AgentSkill):
    """
    Ported from sarveshtalele/agentic-qe skills/generating-test-data/scripts/synthesize-data.ts.
    Synthesizes valid and boundary persona fixtures and payload matrices for deterministic execution.
    """
    __test__ = False

    def __init__(self):
        super().__init__(
            name="generating_test_data",
            description="Synthesizes structured nominal and boundary test fixtures.",
            category="TestData"
        )

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        role = context.get("role", "customer")
        is_valid = context.get("is_valid", True)
        schema_type = context.get("schema_type", "user")

        if schema_type == "user":
            data = self._synthesize_user(role, is_valid)
        elif schema_type == "order":
            data = self._synthesize_order(is_valid)
        else:
            data = {"id": f"fixture_{uuid.uuid4().hex[:6]}", "valid": is_valid}

        return {
            "schema_type": schema_type,
            "fixture": data,
            "is_valid": is_valid,
        }

    def _synthesize_user(self, role: str, is_valid: bool) -> Dict[str, Any]:
        if not is_valid:
            return {
                "id": "invalid-id",
                "email": "not-an-email",
                "role": "unauthorized-role",
                "is_authenticated": False,
            }
        return {
            "id": f"usr_{role}_001",
            "email": f"testuser_{role}@example.com",
            "role": role,
            "token": f"bearer_{hashlib.sha256(role.encode()).hexdigest()[:16]}",
            "is_authenticated": True,
        }

    def _synthesize_order(self, is_valid: bool) -> Dict[str, Any]:
        if not is_valid:
            return {
                "order_id": "ERR-INVALID",
                "amount": -50.0,
                "items": [],
            }
        return {
            "order_id": f"ORD-{uuid.uuid4().hex[:6].upper()}",
            "amount": 149.99,
            "currency": "USD",
            "items": [{"item_id": "ITM-01", "qty": 2, "unit_price": 74.99}],
        }
