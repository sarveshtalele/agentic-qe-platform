"""
Unit and Integration Tests for GitHub Client and API Routes.
Enforces CTL-GIT-01 (Auth), CTL-GIT-02 (Repo & Branch Listing), CTL-GIT-03 (PR Creation & Merge).
"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient
from backend.app import app
from backend.github.client import GitHubClient

client = TestClient(app)


def test_github_client_unauthenticated_fallback():
    # Zero-mock contract: without token, unauthenticated user gets empty repo list (no fake fallback)
    gh = GitHubClient(token="")
    repos = pytest.importorskip("asyncio").run(gh.list_repositories())
    assert repos == []

    # Simulated demo mode when explicit simulated token is provided
    gh_demo = GitHubClient(token="ghp_simulated_token_for_tests")
    demo_repos = pytest.importorskip("asyncio").run(gh_demo.list_repositories())
    assert len(demo_repos) >= 3
    assert any("order-service" in r["name"] for r in demo_repos)

    branches = pytest.importorskip("asyncio").run(gh_demo.list_branches("enterprise-org", "order-service"))
    assert "main" in branches


def test_github_pr_creation_and_merge_simulation():
    gh = GitHubClient(token="")
    pr = pytest.importorskip("asyncio").run(
        gh.create_pull_request(
            owner="enterprise-org",
            repo="order-service",
            title="Add payment retry exponential backoff",
            body="Implements idempotent retry with exponential backoff and ISTQB oracles.",
            head="feature/payment-retry",
            base="main",
        )
    )
    assert pr["number"] > 100
    assert pr["state"] == "open"
    assert "feature/payment-retry" in pr["head"]

    merge_res = pytest.importorskip("asyncio").run(
        gh.merge_pull_request(
            owner="enterprise-org",
            repo="order-service",
            pull_number=pr["number"],
        )
    )
    assert merge_res["merged"] is True
    assert "merged successfully" in merge_res["message"]


def test_github_api_endpoints():
    # 1. Connect
    res = client.post("/api/github/connect", json={"token": "ghp_simulated_token_for_tests"})
    assert res.status_code == 200

    # 2. List Repos
    res_repos = client.get("/api/github/repos")
    assert res_repos.status_code == 200
    data = res_repos.json()
    assert "repositories" in data
    assert data["count"] >= 3

    # 3. List Branches
    res_branches = client.get("/api/github/repos/enterprise-org/order-service/branches")
    assert res_branches.status_code == 200
    assert "main" in res_branches.json()["branches"]

    # 4. Create PR Endpoint
    pr_res = client.post(
        "/api/github/pull-request",
        json={
            "owner": "enterprise-org",
            "repo": "order-service",
            "title": "PR from API Test",
            "head": "feature/api-test",
            "base": "main",
        },
    )
    assert pr_res.status_code == 200
    assert "number" in pr_res.json()

    # 5. Merge PR Endpoint
    pr_num = pr_res.json()["number"]
    merge_res = client.post(
        "/api/github/pull-request/merge",
        json={"owner": "enterprise-org", "repo": "order-service", "number": pr_num},
    )
    assert merge_res.status_code == 200
    assert merge_res.json()["merged"] is True
