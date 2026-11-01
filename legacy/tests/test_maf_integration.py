from __future__ import annotations

import io
import json
import sqlite3
import zipfile
import pytest
from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_full_sdlc_governed_lifecycle():
    """
    End-to-end integration test executing the complete SDLC and Quality Engineering lifecycle:
    Gate 0 (Discovery) -> Ingestion -> Gate 1 (Reqs) -> Gate 2 (Strategy) -> Gate 3 (Design)
    -> Code Synthesis -> Gate 4 (Execution) -> Gate 5 (Confidence Review) -> Ledger Verification -> Export.
    """
    # Step 1: Create Project
    p_res = client.post("/api/projects", json={
        "name": "E2E Governed Pipeline Project",
        "description": "Full lifecycle verification across Gates 0 to 5",
        "project_type": "software",
    })
    assert p_res.status_code == 201
    p_id = p_res.json()["id"]

    # Step 2: Gate 0: Discovery & Context Approval (CTL-GATE-00)
    g0_res = client.post(f"/api/projects/{p_id}/gates/0/decision", json={
        "decision": "APPROVED",
        "actor": "LeadArchitect",
        "reason": "Brownfield repository context and tech stack validated.",
    })
    assert g0_res.status_code == 200
    assert g0_res.json()["status"] == "APPROVED"

    # Step 3: Ingest Document
    sample_spec = (
        "# Synthetic Order Tracking Specification\n"
        "1. Order service must validate customer credit balance before placing order.\n"
        "2. All order transition API requests shall require HTTPS session tokens.\n"
        "3. System should notify fulfillment warehouse on status transitions.\n"
    )
    doc_res = client.post(
        f"/api/projects/{p_id}/documents",
        files={"file": ("spec.md", io.BytesIO(sample_spec.encode("utf-8")), "text/markdown")},
    )
    assert doc_res.status_code == 201
    doc_id = doc_res.json()["id"]

    # Step 4: Extract Requirements & Author Stories
    gen_req_res = client.post(f"/api/projects/{p_id}/requirements/generate", json={
        "document_ids": [doc_id],
        "requirement_types": ["Functional", "Security"],
        "objective": "Process synthetic order specs",
    })
    assert gen_req_res.status_code == 200
    assert gen_req_res.json()["created_count"] >= 1

    gen_story_res = client.post(f"/api/projects/{p_id}/stories/generate", json={})
    assert gen_story_res.status_code == 200
    assert gen_story_res.json()["created_count"] >= 1

    # Step 5: Gate 1: Requirements & Acceptance Criteria Sign-Off (CTL-GATE-01)
    g1_res = client.post(f"/api/projects/{p_id}/gates/1/decision", json={
        "decision": "APPROVED",
        "actor": "ProductOwner",
        "reason": "Requirements baseline and Gherkin user stories approved.",
    })
    assert g1_res.status_code == 200
    assert g1_res.json()["status"] == "APPROVED"

    # Step 6: Gate 2: Formulate & Approve Test Strategy (CTL-GATE-02)
    strat_res = client.post(f"/api/projects/{p_id}/qe/plan", json={})
    assert strat_res.status_code == 200
    assert len(strat_res.json()["areas"]) >= 1

    g2_res = client.post(f"/api/projects/{p_id}/gates/2/decision", json={
        "decision": "APPROVED",
        "actor": "PrincipalTestArchitect",
        "reason": "Risk-based prioritization and test level distribution approved.",
    })
    assert g2_res.status_code == 200
    assert g2_res.json()["status"] == "APPROVED"

    # Step 7: Gate 3: Design & Verify Deterministic Test Cases (CTL-GATE-03)
    design_res = client.post(f"/api/projects/{p_id}/qe/design", json={})
    assert design_res.status_code == 200
    cases = design_res.json()["cases"]
    assert len(cases) >= 1
    assert all("oracle_type" in c for c in cases)

    g3_res = client.post(f"/api/projects/{p_id}/gates/3/decision", json={
        "decision": "APPROVED",
        "actor": "TestDesignLead",
        "reason": "Deterministic test oracles and boundary partitions verified.",
    })
    assert g3_res.status_code == 200
    assert g3_res.json()["status"] == "APPROVED"

    # Step 8: Synthesize Automated Pytest Code
    code_res = client.post(f"/api/projects/{p_id}/qe/generate", json={})
    assert code_res.status_code == 200
    assert "def test_" in code_res.json()["code"]

    # Step 9: Gate 4: Sandboxed Test Execution (CTL-GATE-04)
    exec_res = client.post(f"/api/projects/{p_id}/qe/execute", json={})
    assert exec_res.status_code == 200
    assert exec_res.json()["passed"] is True

    g4_res = client.post(f"/api/projects/{p_id}/gates/4/decision", json={
        "decision": "APPROVED",
        "actor": "QAExecutionLead",
        "reason": "Automated test suite passed cleanly in sandboxed runner.",
    })
    assert g4_res.status_code == 200
    assert g4_res.json()["status"] == "APPROVED"

    # Step 10: Gate 5: Quality Confidence Review & Release Sign-Off (CTL-GATE-05)
    review_res = client.post(f"/api/projects/{p_id}/qe/review", json={})
    assert review_res.status_code == 200
    review_data = review_res.json()
    assert review_data["total_score"] >= 85
    assert review_data["verdict"] == "APPROVED"

    g5_res = client.post(f"/api/projects/{p_id}/gates/5/decision", json={
        "decision": "APPROVED",
        "actor": "ConfidenceReviewer",
        "reason": f"Confidence score {review_data['total_score']}/100 meets release threshold >= 85.",
    })
    assert g5_res.status_code == 200
    assert g5_res.json()["status"] == "APPROVED"

    # Step 11: Cryptographic Audit Ledger Verification (CTL-AUD-01)
    verify_res = client.post(f"/api/projects/{p_id}/ledger/verify")
    assert verify_res.status_code == 200
    v = verify_res.json()
    assert v["verified"] is True
    assert v["count"] >= 6  # All gates and operations chained

    # Step 12: Export Compliance Package (CTL-AUD-03)
    zip_res = client.post(f"/api/projects/{p_id}/exports/zip")
    assert zip_res.status_code in (200, 201)
    export_id = zip_res.json()["id"]

    dl_res = client.get(f"/api/exports/{export_id}/download")
    assert dl_res.status_code == 200
    assert len(dl_res.content) > 0

    # Verify ZIP structure
    with zipfile.ZipFile(io.BytesIO(dl_res.content)) as zf:
        namelist = zf.namelist()
        assert "SDLC_EXPORT_MANIFEST.json" in namelist


def test_maf_workflow_run_endpoint():
    """Tests MAF workflow initiation and session message dispatch via API."""
    p_res = client.post("/api/projects", json={"name": "MAF API Test Project"})
    p_id = p_res.json()["id"]

    # Start Magentic Workflow
    run_res = client.post(f"/api/projects/{p_id}/maf/workflow/run", json={
        "workflow_type": "magentic",
        "prompt": "Inspect codebase and extract requirements",
    })
    assert run_res.status_code == 200
    session_id = run_res.json()["session_id"]
    assert run_res.json()["status"] == "RUNNING"
    assert "/api/ag-ui/stream/" in run_res.json()["stream_url"]

    # Post message to session
    msg_res = client.post(f"/api/projects/{p_id}/maf/sessions/{session_id}/message", json={
        "content": "Focus on high-priority security endpoints",
        "recipient": "MagenticOrchestrator",
    })
    assert msg_res.status_code == 200
    assert msg_res.json()["status"] == "sent"


def test_hitl_approval_lifecycle_api():
    """CTL-HITL-03: Tests HITL listing, approval, and rejection via API."""
    # Instantiates pending request via HITL manager on app.state
    hitl = app.state.hitl_manager
    req = hitl.create_request("sess-api", "PRJ-HITL", "CTL-HITL-01", "file_mutation", "config.py", {"change": "new setting"})
    nonce = req["nonce"]

    # List pending
    list_res = client.get("/api/governance/approvals/pending?project_id=PRJ-HITL")
    assert list_res.status_code == 200
    pending_list = list_res.json()
    assert any(p["nonce"] == nonce for p in pending_list)

    # Resolve approval
    resolve_res = client.post(f"/api/governance/approvals/{nonce}/resolve", json={
        "decision": "APPROVED",
        "decided_by": "ComplianceOfficer",
        "reason": "Authorized configuration change",
    })
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "APPROVED"
    assert resolve_res.json()["decided_by"] == "ComplianceOfficer"
