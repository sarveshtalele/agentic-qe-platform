"""Every feature on a real repository, sarveshtalele/personal-finance-mcp, adding a new MCP tool. Nothing is mocked."""
import json
import re
import urllib.request

import pytest
from playwright.sync_api import expect

from tests.e2e.test_app import API, SIGNER, UI, approve_next, shot, wait_card

pytestmark = pytest.mark.e2e
run: dict = {}
TOOL_SPEC = "Add a new MCP tool calculate_savings_goal(target_amount, current_savings, annual_return_rate, years) that returns the monthly contribution needed to reach the target. Follow how existing tools in src/tools are written and registered in the server, and reject negative amounts and non-positive years. Add pytest tests in tests/."


def get(path: str):
    with urllib.request.urlopen(f"{API}/api{path}") as response:
        return json.load(response)


def test_f1_clone_repo_by_shorthand(page):
    page.goto(UI)
    page.get_by_role("button", name="New project").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Name").fill("Personal Finance MCP")
    dialog.get_by_label("Description").fill("MCP server for personal finance calculations")
    dialog.get_by_label("Git URL").fill("sarveshtalele/personal-finance-mcp")
    dialog.get_by_role("button", name=re.compile("Create project|Cloning")).click()
    page.wait_for_url(re.compile(r"/projects/prj_"), timeout=240_000)
    run["base"], run["id"] = page.url, page.url.rsplit("/", 1)[-1]
    page.goto(f"{run['base']}/repository")
    details = page.get_by_test_id("repo-details")
    expect(details).to_contain_text("Python", timeout=30_000)
    expect(details).to_contain_text("pytest")
    shot(page, "f1-finance-repository")


def test_f2_ba_writes_requirements_for_the_new_tool(page):
    page.goto(f"{run['base']}/ba")
    page.locator('textarea[name="brief"]').fill(TOOL_SPEC)
    page.locator('input[name="doc-title"]').fill("Savings goal tool BRD")
    page.get_by_role("button", name="Generate document").click()
    approve_next(page, "Gate 0")
    card = wait_card(page, "Gate 1")
    links = card.get_by_role("link").evaluate_all("items => items.map(a => a.getAttribute('href'))")
    shot(page, "f2-finance-ba-gate")
    approve_next(page, "Gate 1")
    expect(page.get_by_test_id("run-status")).to_contain_text("completed", timeout=60_000)
    page.goto(UI + links[0])
    expect(page.locator(".prose-atlas h2", has_text=re.compile("^Functional Requirements"))).to_be_visible()
    shot(page, "f2-finance-brd-formatted")
    page.goto(UI + links[1])
    expect(page.get_by_test_id("gherkin-status")).to_contain_text("Valid Gherkin")
    shot(page, "f2-finance-gherkin")


def test_f3_bug_scan_real_repo(page):
    page.goto(f"{run['base']}/bugs")
    page.get_by_role("button", name="Scan repository").click()
    expect(page.get_by_test_id("run-status")).to_contain_text("completed", timeout=420_000)
    shot(page, "f3-finance-bug-scan")
    assert get(f"/projects/{run['id']}/runs")[0]["tokens_in"] < 300_000


def test_f4_feature_builder_adds_the_tool(page):
    page.goto(f"{run['base']}/feature")
    page.locator('input[name="feature-title"]').fill("Add savings goal tool")
    page.locator('textarea[name="feature-spec"]').fill(TOOL_SPEC)
    page.get_by_label(re.compile("Install repository dependencies")).check()
    page.get_by_role("button", name="Build feature").click()
    card = wait_card(page, "Review change")
    expect(card).to_contain_text("calculate_savings_goal")
    run["feature_verdict"] = card.inner_text()[:400]
    assert "undefined" not in page.get_by_test_id("run-metrics").locator("xpath=..").inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "a long diff must not widen the page"
    shot(page, "f4-finance-feature-diff")
    card.get_by_placeholder("Name recorded in the audit ledger").fill(SIGNER)
    card.get_by_role("button", name="Approve").click()
    expect(page.get_by_test_id("run-status")).to_contain_text("completed", timeout=60_000)
    assert re.search("PASS|NO NEW FAILURES", run["feature_verdict"]), run["feature_verdict"]


def test_f5_fix_a_real_finding(page):
    findings = get(f"/projects/{run['id']}/findings")
    if not findings:
        pytest.skip("The scan found nothing to fix in this repository")
    target = findings[0]
    page.goto(f"{run['base']}/bugs")
    row = page.get_by_test_id("findings").locator("li").filter(has_text=f"{target['file']}:{target['line']}").first
    row.get_by_role("button", name="Fix on a branch").click()
    card = wait_card(page, "Review change")
    expect(card).to_contain_text(f"diff --git a/{target['file']}")
    shot(page, "f5-finance-fix-diff")
    card.get_by_placeholder("Name recorded in the audit ledger").fill(SIGNER)
    card.get_by_role("button", name="Approve").click()
    expect(page.get_by_test_id("run-status")).to_contain_text("completed", timeout=60_000)


def test_f6_qe_lifecycle_live(page):
    page.goto(f"{run['base']}/qe")
    page.get_by_label(re.compile("Install repository dependencies")).check()
    page.get_by_role("button", name="Start QE lifecycle").click()
    expect(page.get_by_test_id("run-stages")).to_be_visible(timeout=30_000)
    for gate in range(1, 5):
        approve_next(page, f"Gate {gate}")
        if gate == 1:
            expect(page.locator('[data-testid="run-stages"] .animate-spin')).to_be_visible(timeout=30_000)
            shot(page, "f6-finance-qe-live")
    card = wait_card(page, "Gate 5")
    summary = card.inner_text()
    shot(page, "f6-finance-qe-gate5")
    assert re.search(r"Verdict (PASS|FAIL): \d+/[1-9]\d* tests passed", summary), summary
    approve_next(page, "Gate 5")
    expect(page.get_by_test_id("run-status")).to_contain_text("completed", timeout=60_000)


def test_f7_chat_answers_about_this_repo_and_its_documents(page):
    page.goto(f"{run['base']}/chat")
    page.get_by_role("button", name="New chat").click()
    pane = page.get_by_test_id("chat-pane")
    box = pane.locator("textarea")
    box.fill("Which saved document describes the savings goal tool, and what MCP tool does it add?")
    box.press("Enter")
    expect(pane).to_contain_text("calculate_savings_goal", timeout=180_000)
    shot(page, "f7-finance-chat")


def test_f8_record_token_use(page):
    from tests.e2e.conftest import EVIDENCE

    runs = get(f"/projects/{run['id']}/runs")
    rows = [{k: r[k] for k in ("workflow", "status", "tokens_in", "tokens_out", "started_at", "ended_at")} for r in runs]
    (EVIDENCE / "finance-runs.json").write_text(json.dumps(rows, indent=2))
    assert all(r["tokens_in"] + r["tokens_out"] < 300_000 for r in runs), rows
    assert get(f"/projects/{run['id']}/ledger")["verification"]["valid"]
    page.goto(f"{run['base']}/governance")
    shot(page, "f8-finance-governance")
