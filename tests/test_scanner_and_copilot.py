import pytest
from fastapi.testclient import TestClient
from pathlib import Path
from backend.app import app
from backend.qe.scanner import RepoASTScanner
from backend.governance.stamp import MetadataStamper


@pytest.fixture
def client():
    return TestClient(app)


def test_repo_ast_scanner_static_analysis():
    files = ["package.json", ".github/workflows/ci.yml", "app/main.py", "src/index.ts"]
    findings = RepoASTScanner.scan_workspace_or_tree(
        workspace_dir=None,
        tree_files=files,
        languages={"python": 1000, "typescript": 500}
    )
    assert len(findings) >= 3
    finding_ids = [f["id"] for f in findings]
    assert "BUG-01" in finding_ids
    assert any("package.json" in f["file"] for f in findings)
    assert any("ci.yml" in f["file"] for f in findings)


def test_repo_ast_scanner_unified_diff_generation():
    finding = {
        "id": "BUG-01",
        "file": "app/service.py",
        "line": 15,
        "severity": "High",
        "title": "Missing payload validation",
    }
    diff_text, test_code = RepoASTScanner.generate_unified_diff("app/service.py", finding)
    assert "--- a/app/service.py" in diff_text
    assert "+++ b/app/service.py" in diff_text
    assert "def test_regression_bug_01" in test_code


def test_metadata_stamper_frontmatter_and_json():
    raw_md = "# Title\n\nSome body content."
    stamped_md = MetadataStamper.stamp_markdown(raw_md, doc_id="DOC-99", mode="autonomous")
    assert "---" in stamped_md
    assert "created_by: agentic-qe v1.4.0" in stamped_md
    assert "doc_id: DOC-99" in stamped_md
    assert "# Title" in stamped_md

    raw_data = {"key": "value"}
    stamped_data = MetadataStamper.stamp_json(raw_data, doc_id="DOC-99")
    assert "_meta" in stamped_data
    assert stamped_data["_meta"]["doc_id"] == "DOC-99"
    assert stamped_data["_meta"]["created_by"] == "agentic-qe v1.4.0"


def test_copilot_chat_directives(client):
    # 1. Test /gates
    res_gates = client.post("/api/projects/PRJ-001/copilot/chat", json={"message": "/gates"})
    assert res_gates.status_code == 200
    data = res_gates.json()
    assert data["action"] == "GATES"
    assert "Quality Gates Status" in data["text"]

    # 2. Test /verify
    res_verify = client.post("/api/projects/PRJ-001/copilot/chat", json={"message": "/verify"})
    assert res_verify.status_code == 200
    data = res_verify.json()
    assert data["action"] == "VERIFY"
    assert "Cryptographic Audit Ledger Verification" in data["text"]

    # 3. Test /scan
    res_scan = client.post("/api/projects/PRJ-001/copilot/chat", json={"message": "/scan"})
    assert res_scan.status_code == 200
    data = res_scan.json()
    assert data["action"] == "SCAN"
    assert len(data["data"]["findings"]) >= 1

    # 4. Test /fix BUG-01
    res_fix = client.post("/api/projects/PRJ-001/copilot/chat", json={"message": "/fix BUG-01"})
    assert res_fix.status_code == 200
    data = res_fix.json()
    assert data["action"] == "FIX"
    assert "--- a/" in data["text"]
    assert data["data"]["patch"]["verified"] is True

    # 5. Test /test
    res_test = client.post("/api/projects/PRJ-001/copilot/chat", json={"message": "/test"})
    assert res_test.status_code == 200
    data = res_test.json()
    assert data["action"] == "TEST"
    assert data["data"]["passed"] is True
