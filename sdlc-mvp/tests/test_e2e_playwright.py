"""
Comprehensive End-to-End Headless Chromium Browser Test Suite via Playwright.
Validates all UI modules, collapsible sidebar rail, GitHub integration, Greenfield BA Studio,
Feature Builder with interactive error chat, Bug Fixer, 6-Gate Quality Ribbon, and SHA-256 Ledger.
"""
from __future__ import annotations

import re
import time
import pytest
from playwright.sync_api import Page, expect, sync_playwright

BASE_URL = "http://127.0.0.1:8000"


import json
import urllib.request

@pytest.fixture(scope="session", autouse=True)
def ensure_default_project():
    """Ensure at least one project exists in the database for port 8000 dashboard operations, then cleanly delete at teardown."""
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/projects")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            if not data:
                create_req = urllib.request.Request(
                    f"{BASE_URL}/api/projects",
                    data=json.dumps({
                        "name": "Default Enterprise QE Project",
                        "description": "Seeded session project for test execution",
                    }).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(create_req)
    except Exception:
        pass

    yield

    # Clean teardown
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/projects")
        with urllib.request.urlopen(req) as resp:
            projects = json.loads(resp.read().decode())
            for p in projects:
                if p["id"].startswith("PRJ-") or "E2E Retail" in p.get("name", ""):
                    del_req = urllib.request.Request(f"{BASE_URL}/api/projects/{p['id']}", method="DELETE")
                    try:
                        urllib.request.urlopen(del_req)
                    except Exception:
                        pass
    except Exception:
        pass


@pytest.fixture(scope="function")
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_page()
        yield pg
        browser.close()


def test_e2e_dashboard_and_navigation(page: Page):
    """
    E2E Test 1: Verifies app shell, branding, and SPA screen navigation.
    """
    page.goto(BASE_URL)
    page.wait_for_selector(".app-shell", timeout=10000)

    # 1. Branding Check
    expect(page.locator(".brand-name")).to_have_text("Agentic QE Platform")
    expect(page.locator(".brand-sub")).to_have_text("MAF + Agentic-QE")

    # 2. Navigate to Greenfield BA Studio
    page.click("button[data-view='ba_studio']")
    page.wait_for_selector(".top-title", timeout=5000)
    expect(page.locator(".top-title")).to_contain_text("Greenfield BA Document Studio")

    # 3. Navigate to Feature Builder
    page.click("button[data-view='feature_studio']")
    page.wait_for_selector(".top-title", timeout=5000)
    expect(page.locator(".top-title")).to_contain_text("Feature Builder")

    # 4. Navigate to QE & Testing Hub
    page.click("button[data-view='testing_hub']")
    page.wait_for_selector(".top-title", timeout=5000)
    expect(page.locator(".top-title")).to_have_text("Quality Engineering & Test Hub")

    # 5. Navigate to HITL Governance
    page.click("button[data-view='governance']")
    page.wait_for_selector(".top-title", timeout=5000)
    expect(page.locator(".top-title")).to_have_text("HITL Governance & Cryptographic Ledger")


def test_e2e_collapsible_sidebar_rail(page: Page):
    """
    E2E Test 2: Verifies collapsible sidebar rail toggle (64px icons-only vs 260px expanded).
    """
    page.goto(BASE_URL)
    page.wait_for_selector(".app-shell", timeout=8000)

    # Initial state: expanded
    expect(page.locator(".app-shell")).not_to_have_class(re.compile(r"sidebar-collapsed"))
    expect(page.locator(".brand-name")).to_be_visible()

    # Click collapse toggle
    page.click("button[data-action='toggle-sidebar']")
    expect(page.locator(".app-shell")).to_have_class(re.compile(r"sidebar-collapsed"))

    # In collapsed state, text labels are hidden via CSS
    expect(page.locator(".sidebar-toggle-btn")).to_have_text("▶")

    # Click again to restore
    page.click("button[data-action='toggle-sidebar']")
    expect(page.locator(".app-shell")).not_to_have_class(re.compile(r"sidebar-collapsed"))
    expect(page.locator(".sidebar-toggle-btn")).to_have_text("◀")


def test_e2e_home_github_connect_and_switchboard(page: Page):
    """
    E2E Test 3: Verifies Home Hub GitHub connection and 4-action switchboard routing.
    """
    page.goto(BASE_URL)
    page.wait_for_selector(".github-card", timeout=8000)

    # Click Quick Demo connect
    page.click("button[data-action='github-quick-connect']")
    page.wait_for_selector(".github-avatar", timeout=6000)
    expect(page.locator(".github-card")).to_contain_text("Connected to GitHub as")

    # Verify 4 action switchboard cards
    cards = page.locator(".switchboard-card")
    expect(cards).to_have_count(4)

    # Click "Add a Feature" switchboard card
    cards.first.click()
    page.wait_for_selector(".top-title", timeout=5000)
    expect(page.locator(".top-title")).to_contain_text("Feature Builder")


def test_e2e_greenfield_ba_document_studio(page: Page):
    """
    E2E Test 4: Verifies BRD synthesis, autonomous Reviewer Agent scoring, and refinement.
    """
    page.goto(BASE_URL)
    page.click("button[data-view='ba_studio']")
    page.wait_for_selector("#ba-prompt-input", timeout=8000)

    # 1. Synthesize Enterprise BRD
    page.click("button[data-action='ba-preset-checkout']")
    page.click("button[data-action='ba-generate-brd']")
    page.wait_for_selector(".doc-viewer", timeout=8000)
    expect(page.locator(".doc-viewer")).to_contain_text("Executive Summary")
    expect(page.locator(".doc-viewer")).to_contain_text("Functional Business Rules")

    # 2. Run Autonomous Reviewer Agent
    page.click("button[data-action='ba-review-doc']")
    page.wait_for_selector(".doc-score-banner", timeout=8000)
    expect(page.locator(".score-circle")).to_contain_text("/ 100")
    expect(page.locator(".critique-card").first).to_be_visible()

    # 3. Refine Document with Recommendations
    page.click("button[data-action='ba-refine-doc']")
    page.wait_for_selector(".toast.success", timeout=6000)
    expect(page.locator(".doc-score-banner")).to_contain_text("96 / 100")


def test_e2e_feature_builder_and_interactive_error_chat(page: Page):
    """
    E2E Test 5: Verifies feature scaffolding, error log pasting, auto-patching, and PR button.
    """
    page.goto(BASE_URL)
    page.click("button[data-view='feature_studio']")
    page.wait_for_selector("#feat-name-input", timeout=8000)

    # 1. Implement Feature
    page.click("button[data-action='feature-implement']")
    page.wait_for_selector(".terminal-window", timeout=8000)
    expect(page.locator(".terminal-window")).to_contain_text("PASSED", ignore_case=True)

    # 2. Paste Error into Interactive Chat Window
    page.click("button[data-action='feature-paste-sample-error']")
    page.click("button[data-action='feature-fix-error']")
    page.wait_for_selector(".diff-viewer", timeout=8000)
    expect(page.locator(".diff-viewer")).to_contain_text("KeyError")

    # 3. Create GitHub Pull Request
    page.click("button[data-action='github-create-pr']")
    page.wait_for_selector(".toast.success", timeout=6000)
    expect(page.locator(".text-link")).to_contain_text("View on GitHub")


def test_e2e_bug_diagnostic_and_fixer(page: Page):
    """
    E2E Test 6: Verifies codebase bug scanner and automated regression fix.
    """
    page.goto(BASE_URL)
    page.click("button[data-view='bug_studio']")
    page.wait_for_selector(".panel-head", timeout=8000)

    # Scan
    page.click("button[data-action='bugs-scan']")
    page.wait_for_selector(".badge.high", timeout=6000)
    expect(page.locator(".badge.high").first).to_be_visible()

    # Auto-Fix Bug
    page.click("button[data-action='bugs-fix']")
    page.wait_for_selector(".callout", timeout=6000)
    expect(page.locator(".callout")).to_contain_text("Fixed & Verified")


def test_e2e_qe_hub_lifecycle(page: Page):
    """
    E2E Test 7: Verifies Quality Engineering Hub: Strategy, Design, Generator, Runner, Confidence.
    """
    page.goto(BASE_URL)
    page.click("button[data-view='testing_hub']")
    page.wait_for_selector(".qe-nav", timeout=8000)

    # Tab 1: Strategy
    page.click("button[data-tab='strategy']")
    page.click("button[data-action='qe-plan-strategy']")
    page.wait_for_selector(".toast.success", timeout=6000)

    # Tab 2: Design
    page.click("button[data-tab='design']")
    page.click("button[data-action='qe-design-cases']")
    page.wait_for_selector(".toast.success", timeout=6000)
    expect(page.locator(".badge.completed").first).to_be_visible()

    # Tab 3: Code Generator
    page.click("button[data-tab='generator']")
    page.click("button[data-action='qe-generate-code']")
    page.wait_for_selector(".toast.success", timeout=6000)
    expect(page.locator("#qe-code-preview")).to_contain_text("def test_")

    # Tab 4: Execution Runner
    page.click("button[data-tab='runner']")
    page.click("button[data-action='qe-execute-suite']")
    page.wait_for_selector(".toast.success", timeout=6000)
    expect(page.locator(".terminal-window")).to_contain_text("passed in")

    # Tab 5: Confidence Review
    page.click("button[data-tab='confidence']")
    page.click("button[data-action='qe-review-confidence']")
    page.wait_for_selector(".toast.success", timeout=6000)
    expect(page.locator("#conf-total-score")).to_contain_text("92 / 100")
    expect(page.locator("#conf-verdict")).to_have_text("APPROVED")


def test_e2e_hitl_governance_and_ledger_verification(page: Page):
    """
    E2E Test 8: Verifies HITL Governance view and SHA-256 Cryptographic Ledger integrity verification.
    """
    page.goto(BASE_URL)
    page.click("button[data-view='governance']")
    page.wait_for_selector(".panel-head", timeout=8000)

    # Click Verify Ledger Integrity
    page.click("button[data-action='verify-ledger']")
    page.wait_for_selector(".verifier-seal", timeout=6000)
    expect(page.locator(".verifier-seal")).to_contain_text("SHA-256 Ledger Verified")
    expect(page.locator(".verifier-seal")).to_contain_text("ZERO tampering")


def test_e2e_agui_live_stream_drawer(page: Page):
    """
    E2E Test 9: Verifies AG-UI Live Streaming drawer toggle and chat message dispatch.
    """
    page.goto(BASE_URL)
    page.wait_for_selector(".agui-toggle-btn", timeout=8000)

    # Open Drawer
    page.click(".agui-toggle-btn")
    expect(page.locator("#agui-drawer")).to_have_class("agui-drawer open")

    # Send Directive
    page.fill("#agui-input", "Focus test design on checkout edge cases")
    page.click("form[data-form='agui-chat'] button[type='submit']")

    # Verify user message appears in feed
    expect(page.locator(".agui-msg.user").last).to_contain_text("Focus test design on checkout edge cases")
