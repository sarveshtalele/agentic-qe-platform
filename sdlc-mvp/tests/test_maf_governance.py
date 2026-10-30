from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app import app, db
from backend.governance import (
    AuditLedger,
    GateController,
    HITLManager,
    guard_bash,
    guard_write,
    scan_for_secrets,
)
from backend.maf import (
    AgentSession,
    ConcurrentBuilder,
    HandoffBuilder,
    MagenticBuilder,
    Message,
    PregelEngine,
    SequentialBuilder,
)
from backend.maf.agents import (
    ConfidenceReviewerAgent,
    MagenticOrchestratorAgent,
    PrincipalTestArchitectAgent,
    QAExecutionEngineerAgent,
    RepoIntelligenceAgent,
    RequirementsAnalystAgent,
    TestAutomationEngineerAgent,
    TestDesignEngineerAgent,
)
from backend.agui import apply_patch, make_patch

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Governance & Guardrail Tests (CTL-HITL-01, CTL-HITL-02, CTL-SEC-01, CTL-SEC-02)
# ---------------------------------------------------------------------------
def test_secret_scanner_detects_api_keys():
    """CTL-SEC-01: Detects API keys and private keys."""
    text_with_key = "Authorization: Bearer sk-1234567890abcdef1234567890abcdef"
    findings = scan_for_secrets(text_with_key)
    assert len(findings) > 0
    assert findings[0]["type"] == "OpenAI API Key"

    clean_text = "Standard order tracking payload with order_id=ORD-992"
    assert len(scan_for_secrets(clean_text)) == 0


def test_guard_write_path_traversal_prevention(tmp_path):
    """CTL-SEC-02: Prevents directory traversal outside workspace root."""
    ws = tmp_path / "workspace"
    ws.mkdir()

    # Attempt path escape
    res = guard_write(ws, "../../../etc/passwd", "malicious content")
    assert res["allowed"] is False
    assert res["control_id"] == "CTL-SEC-02"

    # Valid write inside workspace
    res_valid = guard_write(ws, "docs/reqs.md", "Safe requirement notes")
    assert res_valid["allowed"] is True


def test_guard_bash_blocks_destructive_commands(tmp_path):
    """CTL-HITL-02: Blocks banned destructive shell commands."""
    res_rm = guard_bash("rm -rf /", commands_enabled=True, workspace_root=tmp_path)
    assert res_rm["allowed"] is False
    assert res_rm["control_id"] == "CTL-HITL-02"

    res_safe = guard_bash("pytest tests/ -v", commands_enabled=True, workspace_root=tmp_path)
    assert res_safe["allowed"] is True


# ---------------------------------------------------------------------------
# 2. Cryptographic Audit Ledger Tests (CTL-AUD-01)
# ---------------------------------------------------------------------------
def test_audit_ledger_hash_chaining_and_verification(tmp_path):
    """CTL-AUD-01: Verifies SHA-256 cryptographic chain and detects simulated tampering."""
    con = sqlite3.connect(":memory:", check_same_thread=False)
    con.row_factory = sqlite3.Row
    ledger_file = tmp_path / "ledger.jsonl"
    ledger = AuditLedger(con, ledger_file)

    p_id = "test-project-001"
    # Append 3 entries
    e1 = ledger.append(p_id, "User", "CREATE_PROJECT", "CTL-GATE-00", {"name": "Test"})
    e2 = ledger.append(p_id, "RequirementsAnalyst", "EXTRACT_REQS", "CTL-GATE-01", {"count": 5})
    e3 = ledger.append(p_id, "User", "GATE_APPROVED", "CTL-GATE-01", {"gate": 1})

    assert e1["sequence_id"] == 1
    assert e2["sequence_id"] == 2
    assert e3["sequence_id"] == 3
    assert e2["prev_hash"] == e1["entry_hash"]
    assert e3["prev_hash"] == e2["entry_hash"]

    # Verify integrity passes
    ver = ledger.verify_integrity(p_id)
    assert ver["verified"] is True
    assert ver["count"] == 3

    # Simulate tampering in SQLite
    con.execute("UPDATE audit_ledger SET actor = 'Mallory' WHERE sequence_id = 2")
    con.commit()

    ver_tampered = ledger.verify_integrity(p_id)
    assert ver_tampered["verified"] is False
    assert ver_tampered["flaw_at_seq"] == 2


# ---------------------------------------------------------------------------
# 3. Quality Gate Controller Tests (CTL-GATE-00 to CTL-GATE-05)
# ---------------------------------------------------------------------------
def test_gate_controller_prerequisites_enforcement(tmp_path):
    """CTL-GATE-01 to CTL-GATE-05: Enforces sequential gate approvals."""
    con = sqlite3.connect(":memory:", check_same_thread=False)
    con.row_factory = sqlite3.Row
    ledger = AuditLedger(con, tmp_path / "ledger.jsonl")
    controller = GateController(con, ledger)

    p_id = "proj-gates-test"
    gates = controller.get_gates(p_id)
    assert len(gates) == 6
    assert all(g["status"] == "PENDING" for g in gates)

    # Approve Gate 0 (Discovery) -> Sould succeed
    g0 = controller.record_decision(p_id, 0, "APPROVED", "Lead", "Discovery complete")
    assert g0["status"] == "APPROVED"

    # Attempting to approve Gate 2 directly without Gate 1 -> Must raise ValueError
    with pytest.raises(ValueError, match="Prerequisite failure: Gate 1 must be APPROVED"):
        controller.record_decision(p_id, 2, "APPROVED", "Lead", "Skipping Gate 1")

    # Approve Gate 1
    g1 = controller.record_decision(p_id, 1, "APPROVED", "ProductOwner", "Requirements signed")
    assert g1["status"] == "APPROVED"

    # Now Gate 2 can be approved
    g2 = controller.record_decision(p_id, 2, "APPROVED", "Architect", "Architecture approved")
    assert g2["status"] == "APPROVED"


# ---------------------------------------------------------------------------
# 4. Human-In-The-Loop Manager Tests (CTL-HITL-03)
# ---------------------------------------------------------------------------
def test_hitl_nonce_validation_and_resolution(tmp_path):
    """CTL-HITL-03: Validates one-time nonces and resolves approval requests."""
    con = sqlite3.connect(":memory:", check_same_thread=False)
    con.row_factory = sqlite3.Row
    ledger = AuditLedger(con, tmp_path / "ledger.jsonl")
    hitl = HITLManager(con, ledger)

    req = hitl.create_request(
        session_id="sess-123",
        project_id="proj-hitl",
        control_id="CTL-HITL-01",
        action_type="file_mutation",
        target="backend/main.py",
        details={"diff": "+ print('hello')"},
    )
    assert req["status"] == "PENDING"
    nonce = req["nonce"]

    # Invalid nonce fails
    with pytest.raises(ValueError, match="Invalid or unknown approval nonce"):
        hitl.resolve_request("fake-nonce-000", "APPROVED", "User")

    # Valid nonce succeeds
    res = hitl.resolve_request(nonce, "APPROVED", "AdminUser", "Approved modification")
    assert res["status"] == "APPROVED"
    assert res["decided_by"] == "AdminUser"

    # Double resolution fails
    with pytest.raises(ValueError, match="already resolved"):
        hitl.resolve_request(nonce, "APPROVED", "AdminUser")


# ---------------------------------------------------------------------------
# 5. MAF Pregel Engine & Workflows Tests
# ---------------------------------------------------------------------------
@pytest.mark.anyio
async def test_maf_sequential_workflow_execution():
    """Tests MAF Sequential pipeline execution across specialist agents."""
    session = AgentSession("test-seq-sess", "proj-maf-test")
    session.set_state("requirements", [{"id": "REQ-001", "title": "Order Auth", "type": "Security", "priority": "High"}])

    req_agent = RequirementsAnalystAgent()
    arch_agent = PrincipalTestArchitectAgent()
    design_agent = TestDesignEngineerAgent()

    engine = SequentialBuilder.build(
        session=session,
        nodes=[
            ("RequirementsAnalyst", req_agent),
            ("PrincipalTestArchitect", arch_agent),
            ("TestDesignEngineer", design_agent),
        ],
    )

    init_msg = Message(sender="user", recipient="RequirementsAnalyst", content="Run analysis")
    await engine.run("RequirementsAnalyst", init_msg)

    assert session.status == "COMPLETED"
    assert session.superstep_index >= 3
    assert len(session.get_state("test_cases")) > 0


# ---------------------------------------------------------------------------
# 6. AG-UI State Delta Synchronization (RFC 6902)
# ---------------------------------------------------------------------------
def test_rfc6902_json_patch_generation_and_apply():
    """CTL-AUD-02: Generates and applies RFC 6902 JSON Patch state deltas."""
    state_a = {"project": "alpha", "gate": 0, "agents": {"analyst": "idle"}}
    state_b = {"project": "alpha", "gate": 1, "agents": {"analyst": "executing", "qe": "idle"}}

    patch = make_patch(state_a, state_b)
    assert len(patch) >= 2

    # Apply patch to state_a
    reconstructed = apply_patch(state_a, patch)
    assert reconstructed == state_b


# ---------------------------------------------------------------------------
# 7. End-to-End API Integration Tests
# ---------------------------------------------------------------------------
def test_api_gates_and_ledger_endpoints():
    """Tests REST endpoints for quality gates, audit ledger, and ledger verification."""
    # Create project
    p_res = client.post("/api/projects", json={"name": "Gov Test Project", "description": "Testing MAF"})
    assert p_res.status_code == 201
    p_id = p_res.json()["id"]

    # 1. Get Gates
    g_res = client.get(f"/api/projects/{p_id}/gates")
    assert g_res.status_code == 200
    gates = g_res.json()
    assert len(gates) == 6

    # 2. Record Gate 0 Decision
    d_res = client.post(f"/api/projects/{p_id}/gates/0/decision", json={"decision": "APPROVED", "actor": "TestUser", "reason": "Scope confirmed"})
    assert d_res.status_code == 200
    assert d_res.json()["status"] == "APPROVED"

    # 3. Fetch Audit Ledger
    l_res = client.get(f"/api/projects/{p_id}/ledger")
    assert l_res.status_code == 200
    records = l_res.json()
    assert len(records) >= 1

    # 4. Verify Ledger Cryptographic Hash Chain
    v_res = client.post(f"/api/projects/{p_id}/ledger/verify")
    assert v_res.status_code == 200
    assert v_res.json()["verified"] is True

    # 5. QE Summary
    q_res = client.get(f"/api/projects/{p_id}/qe/summary")
    assert q_res.status_code == 200
    assert "readiness_score" in q_res.json()
