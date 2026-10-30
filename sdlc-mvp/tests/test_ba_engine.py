"""
Unit and Integration Tests for Greenfield BA Document Engine and Reviewer Agent.
Enforces CTL-DOC-01 (BRD/PRD), CTL-DOC-02 (Reviewer Agent), CTL-DOC-03 (.docx & .md Exporter).
"""
from __future__ import annotations

import io
import zipfile
import pytest
from starlette.testclient import TestClient
from backend.app import app
from backend.ba.doc_generator import BADocumentGenerator
from backend.maf.agents.doc_reviewer import DocumentReviewerAgent

client = TestClient(app)


def test_brd_and_prd_generation():
    # 1. BRD Generation
    brd = BADocumentGenerator.generate_brd(
        project_name="Synthetic Order Tracking",
        business_prompt="Automated checkout pipeline with idempotency and audit ledger verification.",
        author="Taylor BA",
    )
    assert brd["document_type"] == "BRD"
    assert len(brd["sections"]) == 7
    sec_titles = [s["title"] for s in brd["sections"]]
    assert any("Executive Summary" in t for t in sec_titles)
    assert any("Functional Business Rules" in t for t in sec_titles)

    # 2. PRD Generation
    prd = BADocumentGenerator.generate_prd(
        project_name="Synthetic Order Tracking",
        business_prompt="Product capabilities and API schemas.",
        author="Alex PM",
    )
    assert prd["document_type"] == "PRD"
    assert len(prd["sections"]) == 6


def test_reviewer_agent_critique_and_refinement():
    brd = BADocumentGenerator.generate_brd(
        project_name="Order Service",
        business_prompt="Core checkout flow.",
    )
    reviewer = DocumentReviewerAgent()

    # Initial Review
    review = reviewer.review_document(brd)
    assert review["total_score"] >= 75
    assert len(review["critiques"]) > 0
    assert len(review["missing_edge_cases"]) > 0

    # Refine Document
    refined = reviewer.refine_document(brd, review)
    assert refined["version"] == "1.1.0"
    assert refined["status"] == "REFINED_APPROVED"

    # Re-review refined document
    re_review = reviewer.review_document(refined)
    assert re_review["total_score"] >= review["total_score"]


def test_real_docx_and_md_binary_export():
    brd = BADocumentGenerator.generate_brd("Payment Gateway", "PCI compliance requirements.")

    # 1. Word .docx generation
    docx_bytes = BADocumentGenerator.to_docx_bytes(brd)
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 2000  # Non-trivial Word binary
    assert docx_bytes.startswith(b"PK")  # Valid zip-based DOCX file header

    # 2. Markdown generation
    md_text = BADocumentGenerator.to_markdown(brd)
    assert "# Business Requirements Document (BRD)" in md_text
    assert "## 1. Executive Summary" in md_text

    # 3. ZIP package generation
    zip_bytes = BADocumentGenerator.package_feature_zip(
        "PRJ-001",
        "Checkout Retries",
        {"app/service.py": "# service", "tests/test_service.py": "# tests"},
    )
    assert isinstance(zip_bytes, bytes)
    assert zip_bytes.startswith(b"PK")

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        namelist = zf.namelist()
        assert "MANIFEST.json" in namelist
        assert "app/service.py" in namelist
        assert "tests/test_service.py" in namelist


def test_ba_studio_api_lifecycle():
    # Create project
    proj_res = client.post("/api/projects", json={"name": "BA Test Project", "description": "Greenfield testing"})
    assert proj_res.status_code in (200, 201)
    pid = proj_res.json()["id"]

    # Generate BRD
    brd_res = client.post(
        f"/api/projects/{pid}/ba/generate-brd",
        json={"business_prompt": "Real-time order state transition with Kafka", "author": "Alice BA"},
    )
    assert brd_res.status_code == 200
    assert brd_res.json()["document_type"] == "BRD"

    # Review Document
    rev_res = client.post(f"/api/projects/{pid}/ba/review")
    assert rev_res.status_code == 200
    assert "review" in rev_res.json()
    assert rev_res.json()["review"]["total_score"] > 60

    # Refine Document
    refine_res = client.post(f"/api/projects/{pid}/ba/refine")
    assert refine_res.status_code == 200
    assert refine_res.json()["refined_document"]["version"] == "1.1.0"

    # Export .docx
    docx_res = client.get(f"/api/projects/{pid}/ba/export/docx")
    assert docx_res.status_code == 200
    assert docx_res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert len(docx_res.content) > 1000

    # Export .md
    md_res = client.get(f"/api/projects/{pid}/ba/export/md")
    assert md_res.status_code == 200
    assert "text/markdown" in md_res.headers["content-type"]
    assert b"# Business Requirements Document" in md_res.content
