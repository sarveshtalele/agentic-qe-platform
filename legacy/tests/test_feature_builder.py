"""
Unit and Integration Tests for Autonomous Feature Builder and Interactive Debugger.
Enforces CTL-FEAT-01 (Feature Implementation), CTL-FEAT-02 (Error Pasting), CTL-FEAT-03 (ZIP Export).
"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient
from backend.app import app
from backend.maf.core import AgentSession, Message
from backend.maf.agents.feature_builder import FeatureBuilderAgent, InteractiveDebuggerAgent

client = TestClient(app)


def test_feature_builder_agent_synthesis(tmp_path):
    builder = FeatureBuilderAgent(workspace_root=str(tmp_path))
    session = AgentSession("test-feat-sess", "PRJ-TEST-01")

    files = builder._synthesize_feature_code(
        feat_name="Order Retries",
        spec_text="Exponential backoff retry with idempotency cache",
        project_id="PRJ-TEST-01",
    )
    assert "app/order_retries.py" in files
    assert "tests/test_order_retries.py" in files
    assert "OrderRetriesService" in files["app/order_retries.py"]
    assert "def test_order_retries_nominal_execution" in files["tests/test_order_retries.py"]


def test_interactive_debugger_diagnosis_and_patch(tmp_path):
    debugger = InteractiveDebuggerAgent(workspace_root=str(tmp_path))
    sample_traceback = """
Traceback (most recent call last):
  File "app/order_service.py", line 45, in execute
    item_id = payload['id']
KeyError: 'id'
"""
    diagnosis = debugger.diagnose_error(sample_traceback)
    assert diagnosis["exception_type"] == "KeyError"
    assert diagnosis["line_number"] == 45
    assert "order_service.py" in diagnosis["file"]

    patch_res = debugger.apply_patch("PRJ-TEST-01", diagnosis)
    assert patch_res["verified"] is True
    assert "diff" in patch_res
    assert patch_res["exit_code"] == 0


def test_feature_api_workflow_lifecycle():
    # 1. Create project
    proj_res = client.post("/api/projects", json={"name": "Feature Test Project", "description": "Testing feature builder"})
    assert proj_res.status_code in (200, 201)
    pid = proj_res.json()["id"]

    # 2. Implement Feature
    feat_res = client.post(
        f"/api/projects/{pid}/features/implement",
        json={"feature_name": "Checkout Backoff", "spec_text": "Implement retry logic with idempotency"},
    )
    assert feat_res.status_code == 200
    data = feat_res.json()
    assert data["status"] == "COMPLETED"
    assert "feature/checkout-backoff" in data["branch"]
    assert len(data["files"]) >= 2
    assert data["test_results"]["passed"] is True

    # 3. Interactive Error Fixing
    err_res = client.post(
        f"/api/projects/{pid}/features/fix-error",
        json={
            "error_log": 'File "app/service.py", line 33, in process\nKeyError: "token"\nAssertionError: Token missing'
        },
    )
    assert err_res.status_code == 200
    assert err_res.json()["status"] == "RESOLVED"
    assert "service.py" in err_res.json()["patch"]["patched_file"]

    # 4. Download Feature ZIP
    zip_res = client.get(f"/api/projects/{pid}/features/download-zip")
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"
    assert len(zip_res.content) > 500

    # 5. Bug Scan
    scan_res = client.post(f"/api/projects/{pid}/bugs/scan")
    assert scan_res.status_code == 200
    assert scan_res.json()["count"] >= 3

    # 6. Bug Fix
    fix_res = client.post(f"/api/projects/{pid}/bugs/fix", json={"bug_id": "BUG-01"})
    assert fix_res.status_code == 200
    assert fix_res.json()["status"] == "FIXED"
    assert fix_res.json()["patch"]["verified"] is True
