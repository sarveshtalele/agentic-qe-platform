"""API-level integration tests for the local-first ForgeSDLC MVP."""
from __future__ import annotations

import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

# Configure isolated state before importing the API module.
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="forgesdlc-test-"))
os.environ["SDLC_DATA_DIR"] = str(_TEST_ROOT / "data")
os.environ["SDLC_WORKSPACE_ROOT"] = str(_TEST_ROOT / "workspaces")
os.environ["SDLC_ENABLE_REPO_COMMANDS"] = "false"

from fastapi.testclient import TestClient
import importlib
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

backend_module = importlib.import_module("backend.app")
client = TestClient(backend_module.app)


def create_project(name: str = "Test project") -> str:
    response = client.post("/api/projects", json={"name": name, "description": "An integration test project", "project_type": "software"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_health_and_persistent_project_creation():
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    project_id = create_project()
    found = client.get(f"/api/projects/{project_id}")
    assert found.status_code == 200
    assert found.json()["name"] == "Test project"
    assert found.json()["id"] == project_id
    assert Path(backend_module.DB_PATH).exists()


def test_document_upload_extraction_duplicate_and_requirement_generation():
    project_id = create_project("Requirements test")
    source = (
        "# Report export requirements\n"
        "The system shall allow a signed-in user to export a report as a CSV file.\n"
        "The system must preserve the selected date range in the exported report.\n"
        "Report generation should respond quickly for normal workloads.\n"
    ).encode()
    first = client.post(f"/api/projects/{project_id}/documents", files={"file": ("requirements.txt", source, "text/plain")})
    assert first.status_code == 201, first.text
    doc_id = first.json()["id"]
    assert first.json()["extracted_characters"] > 30
    duplicate = client.post(f"/api/projects/{project_id}/documents", files={"file": ("requirements.txt", source, "text/plain")})
    assert duplicate.status_code == 201
    assert duplicate.json()["duplicate"] is True
    content = client.get(f"/api/documents/{doc_id}/content")
    assert "date range" in content.json()["extracted_text"]

    generated = client.post(f"/api/projects/{project_id}/requirements/generate", json={"document_ids": [doc_id], "requirement_types": ["Functional", "Non-functional"]})
    assert generated.status_code == 200, generated.text
    assert generated.json()["created_count"] >= 2
    requirements = client.get(f"/api/projects/{project_id}/requirements").json()
    assert any("CSV file" in r["statement"] for r in requirements)
    assert all(r["status"] == "Draft" for r in requirements)
    assert generated.json()["method"] == "local heuristic extraction"


def test_story_test_case_traceability_and_exports():
    project_id = create_project("Traceability test")
    req = client.post(f"/api/projects/{project_id}/requirements", json={
        "title": "Export reports", "type": "Functional", "statement": "The system shall export a report as CSV.", "source_excerpt": "The system shall export a report as CSV.", "evidence_type": "user-edited", "confidence": 0.75
    })
    assert req.status_code == 201
    req_id = req.json()["id"]
    # Artefact identifiers are globally unique across projects, not reused per workspace.
    other_project = create_project("Second project for global ID check")
    other_req = client.post(f"/api/projects/{other_project}/requirements", json={"title": "Other requirement", "type": "Functional", "statement": "The system shall keep a stable requirement ID."})
    assert other_req.status_code == 201
    assert other_req.json()["id"] != req_id
    story_result = client.post(f"/api/projects/{project_id}/stories/generate", json={"requirement_ids": [req_id]})
    assert story_result.status_code == 200
    assert story_result.json()["created_count"] == 1
    tc_result = client.post(f"/api/projects/{project_id}/test-cases/generate", json={"requirement_ids": [req_id]})
    assert tc_result.status_code == 200
    assert tc_result.json()["created_count"] == 1
    trace = client.get(f"/api/projects/{project_id}/traceability").json()
    assert trace["coverage"]["requirements_with_stories"] == 1
    assert trace["coverage"]["requirements_with_tests"] == 1
    assert trace["items"][0]["requirement"]["id"] == req_id
    md = client.get(f"/api/projects/{project_id}/exports/requirements.md")
    assert md.status_code == 200 and req_id in md.text
    csv_response = client.get(f"/api/projects/{project_id}/exports/backlog.csv")
    assert csv_response.status_code == 200 and "US-" in csv_response.text and "Export reports" in csv_response.text


def test_repository_analysis_security_scan_and_safe_zip_export():
    project_id = create_project("Repository test")
    root = Path(backend_module.WORKSPACE_ROOT) / "fixtures" / project_id
    (root / "tests").mkdir(parents=True)
    (root / "app.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n@app.get('/health')\ndef health(): return {'status': 'ok'}\n", encoding="utf-8")
    (root / "tests" / "test_sample.py").write_text("def test_math():\n    assert 2 + 2 == 4\n", encoding="utf-8")
    (root / "README.md").write_text("# Fixture\nA tiny test repository.\n", encoding="utf-8")
    (root / ".env").write_text("API_KEY='this-is-a-fake-test-secret-value'\n", encoding="utf-8")
    (root / ".env.example").write_text("# Placeholder only\nAPI_KEY=replace-me\n", encoding="utf-8")

    connect = client.post(f"/api/projects/{project_id}/repository/connect", json={"path": str(root)})
    assert connect.status_code == 200, connect.text
    analysis = client.post(f"/api/projects/{project_id}/repository/analyze")
    assert analysis.status_code == 200, analysis.text
    report = analysis.json()["analysis"]
    assert report["file_count"] >= 3
    assert report["test_file_count"] >= 1
    assert "Python" in report["languages"]
    assert report["api_hints"]

    findings = client.get(f"/api/projects/{project_id}/security/findings").json()
    assert any(f["path"] == ".env" for f in findings)
    assert not any(f["path"] == ".env.example" for f in findings)
    assert all("this-is-a-fake-test-secret-value" not in f["evidence"] for f in findings)

    export = client.post(f"/api/projects/{project_id}/exports/zip")
    assert export.status_code == 201, export.text
    download = client.get(export.json()["download_url"])
    assert download.status_code == 200
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert "project/app.py" in names
        assert "project/.env" not in names
        assert "project/.env.example" in names
        assert "SDLC_EXPORT_MANIFEST.json" in names
        manifest = json.loads(archive.read("SDLC_EXPORT_MANIFEST.json"))
        assert any(item["path"] == ".env" for item in manifest["excluded_files"])


def test_repository_path_boundary_and_zip_traversal_protection():
    project_id = create_project("Safety test")
    outside = _TEST_ROOT / "outside"
    outside.mkdir(parents=True)
    response = client.post(f"/api/projects/{project_id}/repository/connect", json={"path": str(outside)})
    assert response.status_code == 400

    malicious = io.BytesIO()
    with zipfile.ZipFile(malicious, "w") as archive:
        archive.writestr("../escaped.txt", "should not extract")
        archive.writestr("app.py", "print('hello')")
    response = client.post(f"/api/projects/{project_id}/repository/upload", files={"file": ("unsafe.zip", malicious.getvalue(), "application/zip")})
    assert response.status_code == 400
    assert not (_TEST_ROOT / "escaped.txt").exists()


def test_scaffold_is_real_and_command_execution_records_truthfully():
    project_id = create_project("Scaffold test")
    result = client.post(f"/api/projects/{project_id}/workflows", json={"workflow_type": "new-app"})
    assert result.status_code == 200, result.text
    root = Path(result.json()["repo_path"])
    assert (root / "app" / "main.py").exists()
    assert (root / "tests" / "test_app.py").exists()
    assert (root / "README.md").exists()

    # Default is blocked and explicitly recorded as not executed.
    blocked = client.post(f"/api/projects/{project_id}/tests/run")
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "Blocked"
    assert blocked.json()["executed"] is False

    # This is a trusted fixture generated by this test. Exercise the genuine command runner and capture its exit status.
    backend_module.COMMANDS_ENABLED = True
    try:
        executed = client.post(f"/api/projects/{project_id}/tests/run")
        assert executed.status_code == 200, executed.text
        assert executed.json()["executed"] is True
        assert executed.json()["status"] == "Passed", executed.text
        assert executed.json()["exit_code"] == 0
        assert "passed" in executed.json()["stdout"].lower()
    finally:
        backend_module.COMMANDS_ENABLED = False


def test_static_frontend_and_settings_endpoint():
    root = client.get("/")
    assert root.status_code == 200
    assert "ForgeSDLC" in root.text
    asset = client.get("/static/styles.css")
    assert asset.status_code == 200 and "--accent" in asset.text
    settings = client.get("/api/settings")
    assert settings.status_code == 200
    assert settings.json()["repository_commands_enabled"] is False


def test_command_output_redaction():
    sample = 'API_KEY="super-secret-value"\nAuthorization: Bearer abc123\nsk-' + 'A' * 30 + '\n'
    redacted = backend_module.redact_output(sample)
    assert "super-secret-value" not in redacted
    assert "abc123" not in redacted
    assert "sk-" + "A" * 30 not in redacted
    assert "[REDACTED]" in redacted
