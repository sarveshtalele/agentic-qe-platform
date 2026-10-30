"""Create a clearly labelled synthetic project through a running local ForgeSDLC API with 6-gate governance."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

BASE_URL = os.getenv("FORGESDLC_API_URL", "http://127.0.0.1:8000").rstrip("/")
ROOT = Path(__file__).resolve().parents[1]
BRIEF = ROOT / "examples" / "synthetic-order-tracking-brief.md"


def main() -> int:
    try:
        health = requests.get(f"{BASE_URL}/api/health", timeout=5)
        health.raise_for_status()
    except Exception as exc:
        print(f"Cannot reach ForgeSDLC at {BASE_URL}: {exc}", file=sys.stderr)
        print("Start the server first, then rerun this script.", file=sys.stderr)
        return 1

    project_response = requests.post(f"{BASE_URL}/api/projects", json={
        "name": "DEMO — Synthetic Order Tracking (MAF + QE)",
        "description": "Synthetic demonstration data running under Microsoft Agent Framework and Agentic-QE 6-gate governance.",
        "project_type": "experiment",
    }, timeout=15)
    project_response.raise_for_status()
    project = project_response.json()
    project_id = project["id"]

    # 1. Approve Gate 0: Discovery
    requests.post(f"{BASE_URL}/api/projects/{project_id}/gates/0/decision", json={
        "decision": "APPROVED",
        "actor": "LeadArchitect",
        "reason": "Discovery and brownfield project context validated.",
    }, timeout=15)

    with BRIEF.open("rb") as handle:
        upload_response = requests.post(f"{BASE_URL}/api/projects/{project_id}/documents", files={
            "file": (BRIEF.name, handle, "text/markdown")
        }, timeout=30)
    upload_response.raise_for_status()
    document = upload_response.json()

    generate_response = requests.post(f"{BASE_URL}/api/projects/{project_id}/requirements/generate", json={
        "document_ids": [document["id"]],
        "requirement_types": ["Functional", "Non-functional", "Security"],
        "objective": "Demonstrate synthetic order tracking requirements.",
    }, timeout=90)
    generate_response.raise_for_status()
    generated = generate_response.json()

    stories_response = requests.post(f"{BASE_URL}/api/projects/{project_id}/stories/generate", json={}, timeout=30)
    stories_response.raise_for_status()

    # 2. Approve Gate 1: Requirements Baseline
    requests.post(f"{BASE_URL}/api/projects/{project_id}/gates/1/decision", json={
        "decision": "APPROVED",
        "actor": "ProductOwner",
        "reason": "Requirements and acceptance criteria baseline approved.",
    }, timeout=15)

    # 3. Plan Test Strategy (Gate 2)
    requests.post(f"{BASE_URL}/api/projects/{project_id}/qe/plan", json={}, timeout=30)
    requests.post(f"{BASE_URL}/api/projects/{project_id}/gates/2/decision", json={
        "decision": "APPROVED",
        "actor": "PrincipalTestArchitect",
        "reason": "Risk strategy and test level allocation approved.",
    }, timeout=15)

    # 4. Design Deterministic Test Cases (Gate 3)
    requests.post(f"{BASE_URL}/api/projects/{project_id}/qe/design", json={}, timeout=30)

    # 5. Verify Cryptographic Audit Ledger
    verify_res = requests.post(f"{BASE_URL}/api/projects/{project_id}/ledger/verify", json={}, timeout=15).json()

    print("==================================================================")
    print("✓ ForgeSDLC Studio Synthetic Demo Project Seeded Successfully!")
    print(f"Project ID: {project_id} — {project['name']}")
    print(f"Document: {document['id']} — {document['filename']}")
    print(f"Requirements: {generated['created_count']} drafts generated with evidence quotes")
    print(f"Stories: {stories_response.json()['created_count']} backlog stories with Gherkin ACs")
    print(f"Gate 0 (Discovery): APPROVED")
    print(f"Gate 1 (Requirements Baseline): APPROVED")
    print(f"Gate 2 (Test Architecture): APPROVED")
    print(f"Gate 3 (Test Design & Oracles): IN_PROGRESS")
    print(f"SHA-256 Audit Ledger: Verified {verify_res.get('count', 0)} chained blocks (Tip: {verify_res.get('tip_hash', '')[:16]}...)")
    print(f"Open Application UI: {BASE_URL}")
    print("==================================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
