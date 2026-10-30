"""
Comprehensive End-to-End Headless Chromium Browser Test Suite via Playwright targeting Next.js.
Validates:
1. Collapsible sidebar rail (64px icons-only rail <-> 240px expanded).
2. Clean zero-mock data initial state & project workspace creation.
3. Real GitHub connection & Fetching real repository via API.
4. Greenfield BA Studio: Enterprise BRD generation (7 sections, business rules), Reviewer Agent scoring, 1-click refinement, .docx and .md exports.
5. Feature Builder: Isolated branch scaffolding, sandboxed tests, local test ZIP download, interactive error traceback chat & line diagnosis, automated code patching, GitHub PR creation & merge.
6. Codebase Bug Diagnostic & AST automated regression fix.
7. Quality Engineering Hub: 4 ISTQB deterministic test oracles (Strategy, Design, Code Generator, Runner, Confidence).
8. HITL Governance & Cryptographic Ledger: SHA-256 tamper-evident verification.
9. Observability & MAF Multi-Agent Visualizer: Traces, latency spans, and agent metrics.
10. Platform Settings: Custom LLM Base URL, Model Name, API Key configuration, and Test Connectivity.
11. Copilot Stream drawer live communication.
"""
from __future__ import annotations

import json
import re
import urllib.request
import pytest
from playwright.sync_api import Page, expect, sync_playwright

NEXTJS_URL = "http://localhost:3000"


@pytest.fixture(scope="module")
def browser_context():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        yield context
        browser.close()


@pytest.fixture(scope="function")
def page(browser_context):
    pg = browser_context.new_page()
    yield pg
    pg.close()


@pytest.fixture(scope="session", autouse=True)
def ensure_default_project():
    """Ensure at least one project exists in the database for studio operations, then cleanly delete at teardown."""
    created_ids = []
    try:
        req = urllib.request.Request(f"{NEXTJS_URL}/api/projects")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            if not data:
                create_req = urllib.request.Request(
                    f"{NEXTJS_URL}/api/projects",
                    data=json.dumps({
                        "name": "Default Enterprise QE Project",
                        "description": "Seeded session project for test execution",
                    }).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(create_req) as create_resp:
                    pdata = json.loads(create_resp.read().decode())
                    if pdata.get("id"):
                        created_ids.append(pdata["id"])
    except Exception:
        pass

    yield

    # Clean teardown: purge test workspaces created during test session
    try:
        req = urllib.request.Request(f"{NEXTJS_URL}/api/projects")
        with urllib.request.urlopen(req) as resp:
            projects = json.loads(resp.read().decode())
            for p in projects:
                if p["id"].startswith("PRJ-") or "E2E Retail" in p.get("name", ""):
                    del_req = urllib.request.Request(f"{NEXTJS_URL}/api/projects/{p['id']}", method="DELETE")
                    try:
                        urllib.request.urlopen(del_req)
                    except Exception:
                        pass
    except Exception:
        pass


def test_nextjs_branding_and_collapsible_sidebar(page: Page):
    """
    Test 1: Verifies Next.js app loading, branding, and collapsible sidebar rail toggle.
    """
    page.goto(NEXTJS_URL)
    page.wait_for_selector("text=Agentic QE", timeout=10000)

    # 1. Check branding
    expect(page.locator("text=Agentic QE").first).to_be_visible()

    # 2. Check sidebar is initially expanded (w-60)
    aside = page.locator("aside")
    expect(aside).to_have_class(re.compile(r"w-60"))
    expect(page.locator("text=Repository Hub").first).to_be_visible()

    # 3. Click collapse toggle button
    page.click("button[title='Collapse sidebar']")
    expect(aside).to_have_class(re.compile(r"w-16"))

    # 4. Click expand toggle button to restore
    page.click("button[title='Expand sidebar']")
    expect(aside).to_have_class(re.compile(r"w-60"))
    expect(page.locator("text=Repository Hub").first).to_be_visible()


def test_nextjs_project_creation_and_zero_mock(page: Page):
    """
    Test 2: Verifies project creation modal and dynamic updates in SQLite.
    """
    page.goto(NEXTJS_URL)
    page.wait_for_selector("header", timeout=10000)

    # Click "New Project" button in header
    page.click("header button:has-text('New Project')")

    # Fill in modal form using exact placeholders
    page.wait_for_selector("text=Create Workspace Project", timeout=5000)
    page.fill("input[placeholder='e.g. order-tracking-service']", "E2E Retail Test Project")
    page.fill("textarea[placeholder='Project purpose, scope, and objectives...']", "Validating full autonomous QE lifecycle")
    page.click("button:has-text('Create Project')")

    # Verify project is created and becomes active in selector
    page.wait_for_selector("header select", timeout=6000)
    expect(page.locator("header select")).to_contain_text("E2E Retail Test Project")

    # Verify Quality Gates appear in ribbon
    expect(page.locator("button:has-text('G1:')").first).to_be_visible()
    expect(page.locator("button:has-text('G5:')").first).to_be_visible()


def test_nextjs_fetch_real_github_repository(page: Page):
    """
    Test 3: Verifies real GitHub fetching via /api/github/fetch-repo and repository dossier display.
    """
    page.goto(NEXTJS_URL)
    page.wait_for_selector("text=Real GitHub Repository Ingestion", timeout=10000)

    # 1. Fill in repo URL / identifier with real public repository
    page.fill("input[placeholder*='https://github.com/owner/repo']", "fastapi/fastapi")
    page.click("button:has-text('Fetch Repository')")

    # 2. Verify Ingested Dossier renders real repo details
    page.wait_for_selector("text=Default Branch", timeout=15000)
    expect(page.locator("text=Default Branch").first).to_be_visible()
    expect(page.locator("text=Total Analyzed Files").first).to_be_visible()
    expect(page.locator("text=Ingested File Tree:").first).to_be_visible()


def test_nextjs_greenfield_ba_studio(page: Page):
    """
    Test 4: Verifies Greenfield BA Studio BRD generation, Document Reviewer Agent scoring,
    1-click refinement, and real binary .docx download.
    """
    page.goto(NEXTJS_URL)
    page.wait_for_selector("header select option:not([value=''])", state="attached", timeout=8000)
    page.wait_for_selector("aside button:has-text('Greenfield BA Studio')", timeout=10000)
    page.click("aside button:has-text('Greenfield BA Studio')")
    page.wait_for_selector("text=Business Requirements Definition", timeout=10000)

    # 1. Use Checkout Preset
    page.click("button:has-text('Checkout Preset')")

    # 2. Click Generate Enterprise BRD
    page.click("button:has-text('Generate Enterprise BRD')")
    page.wait_for_selector("text=Executive Summary", timeout=8000)

    # Verify structured enterprise sections
    expect(page.locator("text=Executive Summary").first).to_be_visible()
    expect(page.locator("text=Functional Business Rules").first).to_be_visible()
    expect(page.locator("text=BR-001").first).to_be_visible()

    # 3. Run Autonomous Document Reviewer Agent
    page.click("button:has-text('Run Audit')")
    page.wait_for_selector("text=Verdict:", timeout=8000)
    expect(page.locator("text=88 / 100")).to_be_visible()
    expect(page.locator("text=Verdict: APPROVED")).to_be_visible()

    # 4. Refine Document with recommendations
    page.click("button:has-text('Refine Document with Recommendations')")
    page.wait_for_selector("text=96 / 100", timeout=8000)
    expect(page.locator("text=96 / 100")).to_be_visible()

    # 5. Verify Word .docx download endpoint produces genuine Office Open XML binary
    docx_btn = page.locator("a:has-text('Download .docx (Word)')")
    expect(docx_btn).to_be_visible()
    docx_url = docx_btn.get_attribute("href")
    assert docx_url is not None

    req = urllib.request.Request(f"{NEXTJS_URL}{docx_url}")
    with urllib.request.urlopen(req) as resp:
        content = resp.read()
        assert resp.status == 200
        # Check ZIP / Office Open XML magic bytes (PK\x03\x04)
        assert content.startswith(b"PK\x03\x04")


def test_nextjs_feature_builder_and_interactive_error_chat(page: Page):
    """
    Test 5: Verifies Feature Builder scaffolding, sandboxed test execution,
    local test ZIP download, interactive error chat diagnosis & patch, and PR creation.
    """
    page.goto(NEXTJS_URL)
    page.wait_for_selector("header select option:not([value=''])", state="attached", timeout=8000)
    page.wait_for_selector("aside button:has-text('Feature Builder')", timeout=10000)
    page.click("aside button:has-text('Feature Builder')")
    page.wait_for_selector("text=Feature Implementation & Branching", timeout=10000)

    # 1. Click Implement Feature Autonomously
    page.click("button:has-text('Implement Feature Autonomously')")
    page.wait_for_selector("text=Workspace Feature Files", timeout=8000)

    # Verify branch name and files
    expect(page.locator("text=Branch: feature/").first).to_be_visible()
    expect(page.locator("text=✓ app/").first).to_be_visible()
    expect(page.locator("text=PASSED").first).to_be_visible()

    # 2. Verify Local Test ZIP download link
    zip_btn = page.locator("a:has-text('Download Local Test ZIP')")
    expect(zip_btn).to_be_visible()
    zip_url = zip_btn.get_attribute("href")
    assert zip_url is not None

    req = urllib.request.Request(f"{NEXTJS_URL}{zip_url}")
    with urllib.request.urlopen(req) as resp:
        zip_bytes = resp.read()
        assert resp.status == 200
        assert zip_bytes.startswith(b"PK\x03\x04")

    # 3. Interactive Error Chat: Paste Sample Error
    page.click("button:has-text('Paste Sample KeyError')")
    page.click("button:has-text('Analyze & Auto-Fix Error')")

    # Verify line diagnosis and patch diff
    page.wait_for_selector("text=Fault Diagnosed & Patched!", timeout=8000)
    expect(page.locator("text=Fault Diagnosed & Patched!")).to_be_visible()
    expect(page.locator("text=Applied Patch Diff:")).to_be_visible()
    expect(page.locator("text=KeyError").first).to_be_visible()

    # 4. GitHub PR Automation: Create PR
    page.click("button:has-text('Create GitHub Pull Request')")
    page.wait_for_selector("text=Pull Request #", timeout=8000)
    expect(page.locator("text=View on GitHub →")).to_be_visible()

    # 5. Merge PR
    page.click("button:has-text('Merge Pull Request into Main')")
    page.wait_for_selector("text=Pull Request Merged into Mainline", timeout=8000)
    expect(page.locator("text=Pull Request Merged into Mainline")).to_be_visible()


def test_nextjs_bug_diagnostic(page: Page):
    """
    Test 6: Verifies Bug Diagnostic scan, regression test generation, and auto-fix.
    """
    page.goto(NEXTJS_URL)
    page.wait_for_selector("header select option:not([value=''])", state="attached", timeout=8000)
    page.wait_for_selector("aside button:has-text('Bug Diagnostic')", timeout=10000)
    page.click("aside button:has-text('Bug Diagnostic')")
    page.wait_for_selector("text=Repository Bug & Vulnerability Scan", timeout=10000)

    # Click Scan Codebase
    page.click("button:has-text('Scan Codebase')")
    page.wait_for_selector("text=BUG-01", timeout=8000)
    expect(page.locator("text=BUG-01").first).to_be_visible()

    # Click Auto-Fix
    page.locator("button:has-text('Auto-Fix')").first.click()
    page.wait_for_selector("text=Regression Test Created:", timeout=8000)
    expect(page.locator("text=Regression Test Created:")).to_be_visible()


def test_nextjs_qe_testing_hub(page: Page):
    """
    Test 7: Verifies Quality Engineering Hub: Strategy, Design, Generator, Runner, Confidence.
    """
    page.goto(NEXTJS_URL)
    page.wait_for_selector("header select option:not([value=''])", state="attached", timeout=8000)
    page.wait_for_selector("aside button:has-text('QE Test Studio')", timeout=10000)
    page.click("aside button:has-text('QE Test Studio')")
    page.wait_for_selector("text=Principal Test Architect", timeout=10000)

    # Tab 1: Strategy
    page.click("button:has-text('Plan Strategy')")
    page.wait_for_selector("text=Test strategy planned!", timeout=6000)

    # Tab 2: Design
    page.click("button:has-text('2. 4-Oracle Design')")
    page.click("button:has-text('Design Deterministic Cases')")
    page.wait_for_selector("text=TC-001", timeout=6000)
    expect(page.locator("text=TC-001").first).to_be_visible()

    # Tab 3: Generator
    page.click("button:has-text('3. Pytest Synthesizer')")
    page.click("button:has-text('Synthesize Pytest Code')")
    page.wait_for_selector("text=def test_", timeout=6000)
    expect(page.locator("text=def test_").first).to_be_visible()

    # Tab 4: Runner
    page.click("button:has-text('4. Isolated Runner')")
    page.click("button:has-text('Run Sandboxed Test Suite')")
    page.wait_for_selector("text=passed in", timeout=6000)
    expect(page.locator("text=passed in").first).to_be_visible()

    # Tab 5: Confidence
    page.click("button:has-text('5. Confidence Review')")
    page.click("button:has-text('Evaluate Release Confidence')")
    page.wait_for_selector("text=/ 100", timeout=6000)
    expect(page.locator("text=/ 100").first).to_be_visible()


def test_nextjs_hitl_governance_and_cryptographic_ledger(page: Page):
    """
    Test 8: Verifies HITL Governance and SHA-256 Ledger cryptographic verification.
    """
    page.goto(NEXTJS_URL)
    page.wait_for_selector("aside button:has-text('HITL Governance')", timeout=10000)
    page.click("aside button:has-text('HITL Governance')")
    page.wait_for_selector("text=Tamper-Evident SHA-256 Cryptographic Audit Ledger", timeout=10000)

    # Click Verify Ledger Integrity
    page.click("button:has-text('Verify Ledger Integrity')")
    page.wait_for_selector("text=Cryptographic Integrity Verified", timeout=6000)
    expect(page.locator("text=Cryptographic Integrity Verified").first).to_be_visible()


def test_nextjs_observability_and_traces(page: Page):
    """
    Test 9: Verifies Multi-Agent Observability, MAF execution traces, and telemetry metrics.
    """
    page.goto(NEXTJS_URL)
    page.wait_for_selector("aside button:has-text('Observability & MAF')", timeout=10000)
    page.click("aside button:has-text('Observability & MAF')")
    page.wait_for_selector("text=Microsoft Agent Framework (MAF) Topology", timeout=10000)

    # Verify metrics and agent nodes
    expect(page.locator("text=Total Multi-Agent Invocations")).to_be_visible()
    expect(page.locator("text=DocumentReviewerAgent").first).to_be_visible()
    expect(page.locator("text=Execution Traces & Latency Spans")).to_be_visible()


def test_nextjs_platform_and_custom_llm_settings(page: Page):
    """
    Test 10: Verifies Custom LLM settings (Base URL, API Key, Model Name) and connectivity test.
    """
    page.goto(NEXTJS_URL)
    page.wait_for_selector("aside button:has-text('Platform Settings')", timeout=10000)
    page.click("aside button:has-text('Platform Settings')")
    page.wait_for_selector("text=Custom LLM Configuration", timeout=10000)

    # Fill custom settings
    page.fill("input[placeholder*='https://api.openai.com/v1']", "https://litellm-proxy-app-gfajczbbf7fjfyfw.eastus2-01.azurewebsites.net/v1")
    page.fill("input[placeholder*='gpt-4o, claude-3-5-sonnet']", "deepseek-v4-flash-global")
    page.fill("input[placeholder='sk-...']", "sk-custom-9758d7426d03c92fb1a9310777d08584")

    # Test endpoint connectivity
    page.click("button:has-text('Test Endpoint Connectivity')")
    page.wait_for_selector("text=Successfully connected", timeout=8000)
    expect(page.locator("text=Successfully connected")).to_be_visible()

    # Save Settings
    page.click("button:has-text('Save Settings')")
    page.wait_for_selector("text=Platform & custom LLM settings saved!", timeout=6000)
    expect(page.locator("text=Platform & custom LLM settings saved!")).to_be_visible()


def test_nextjs_copilot_stream_drawer(page: Page):
    """
    Test 11: Verifies Copilot Stream drawer toggle and message send.
    """
    page.goto(NEXTJS_URL)
    page.wait_for_selector("header", timeout=10000)

    # Click Copilot Stream button in header
    page.click("header button:has-text('Copilot Stream')")
    page.wait_for_selector("text=CopilotKit / AG-UI Live Stream", timeout=5000)

    # Fill input and send
    page.fill("input[placeholder='Direct agents...']", "Verify all quality gates before release")
    page.click("button:has(svg.lucide-send)")

    # Verify directive appears in chat stream
    page.wait_for_selector("text=Verify all quality gates before release", timeout=5000)
    expect(page.locator("text=Verify all quality gates before release")).to_be_visible()
