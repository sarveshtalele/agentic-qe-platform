"""End-to-end: real FastAPI, real Next.js build, real browser, real model, real git and pytest. Nothing is mocked.

Tests run in file order and share one project. Screenshots go to docs/evidence as test evidence.
"""
import base64
import io
import os
import re
import time
import zipfile
from pathlib import Path

import pytest
from docx import Document
from playwright.sync_api import expect

from tests.e2e.conftest import api_get, state

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs" / "evidence"
UI = "http://127.0.0.1:3010"
API = "http://127.0.0.1:8010"
LLM_TIMEOUT = 420_000

APP_ZIP = {
    "shop-main/inventory.py": '"""Stock keeping."""\n\n\ndef reserve(stock: int, quantity: int) -> int:\n    """Return stock left after reserving. Quantity must be positive and not exceed stock."""\n    if quantity <= 0:\n        raise ValueError("quantity must be positive")\n    if quantity > stock:\n        raise ValueError("not enough stock")\n    return stock - quantity\n\n\ndef restock(stock: int, quantity: int) -> int:\n    return stock - quantity\n',
    "shop-main/admin.py": 'import subprocess\n\n\ndef backup(path):\n    return subprocess.call("tar -czf backup.tgz " + path, shell=True)\n',
    "shop-main/tests/test_inventory.py": 'from inventory import reserve\n\n\ndef test_reserve():\n    assert reserve(5, 2) == 3\n',
    "shop-main/conftest.py": "",
    "shop-main/requirements.txt": "pytest\n",
}


def shot(page, name: str) -> None:
    page.screenshot(path=str(EVIDENCE / f"{name}.png"), full_page=True)


def wait_card(page, title_part: str):
    """Wait for an approval, or stop at once with the real error if the run failed."""
    card = page.get_by_test_id("approval-card")
    deadline = time.time() + LLM_TIMEOUT / 1000
    while time.time() < deadline:
        if card.count() and title_part in card.first.inner_text():
            return card
        status = page.get_by_test_id("run-status")
        if status.count() and "failed" in status.inner_text():
            raise AssertionError(f"Run failed: {page.locator('p[role=alert]').first.inner_text()}")
        page.wait_for_timeout(1000)
    raise AssertionError(f"Timed out waiting for {title_part}")


def approve_next(page, title_part: str) -> None:
    card = wait_card(page, title_part)
    card.get_by_role("button", name="Approve").click()
    expect(card.filter(has_text=title_part)).to_have_count(0, timeout=30_000)


def test_01_projects_page_replaces_the_dropdown(page):
    page.goto(UI)
    expect(page.get_by_role("heading", name="Projects")).to_be_visible()
    expect(page.get_by_text("No projects yet")).to_be_visible()
    assert page.locator("header select").count() == 0, "no project dropdown"
    shot(page, "01-projects-empty")


def test_02_create_project_with_zip_upload(page, tmp_path):
    archive = tmp_path / "shop.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for name, body in APP_ZIP.items():
            bundle.writestr(name, body)
    page.get_by_role("button", name="New project").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Name").fill("Shop Inventory")
    dialog.get_by_label("Description").fill("Inventory service for the online shop")
    dialog.locator('input[type="file"]').set_input_files(archive)
    dialog.get_by_role("button", name=re.compile("Create project|Cloning")).click()
    page.wait_for_url(re.compile(r"/projects/prj_"), timeout=60_000)
    state["base"] = page.url
    state["id"] = page.url.rsplit("/", 1)[-1]
    expect(page.get_by_text("Next:")).to_be_visible()
    expect(page.get_by_text("shop.zip")).to_be_visible()
    shot(page, "02-project-overview")


def test_03_repository_scan_shows_real_facts(page):
    page.goto(f"{state['base']}/repository")
    details = page.get_by_test_id("repo-details")
    expect(details).to_contain_text("pytest")
    expect(details).to_contain_text("Python")
    details.get_by_role("button", name="inventory.py", exact=True).click()
    expect(details.locator("pre")).to_contain_text("def reserve")
    shot(page, "03-repository-zip")


def test_04_real_public_github_clone(page):
    page.goto(UI)
    page.get_by_role("button", name="New project").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Name").fill("Agentic QE plugin")
    dialog.get_by_label("Git URL").fill("https://github.com/sarveshtalele/agentic-qe")
    dialog.get_by_role("button", name=re.compile("Create project|Cloning")).click()
    page.wait_for_url(re.compile(r"/projects/prj_"), timeout=240_000)
    page.goto(f"{page.url}/repository")
    details = page.get_by_test_id("repo-details")
    expect(details).to_contain_text("TypeScript", timeout=30_000)
    expect(details).to_contain_text("Recent commits")
    shot(page, "04-repository-github")
    page.goto(UI)
    expect(page.get_by_test_id("project-card")).to_have_count(2)
    shot(page, "05-projects-list")


def test_04b_rename_project_docs_and_brand(page):
    page.goto(UI)
    expect(page.get_by_text("Governed requirements, code changes, and test engineering for BAs and developers.")).to_have_count(0)
    page.once("dialog", lambda d: d.accept("Agentic QE repository"))
    page.get_by_role("button", name="Rename Agentic QE plugin").click()
    expect(page.get_by_role("heading", name="Agentic QE repository")).to_be_visible()
    page.get_by_role("link", name="Documentation").click()
    expect(page).to_have_url(re.compile("/docs/introduction"))
    expect(page.get_by_role("heading", level=1, name="Introduction")).to_be_visible()
    shot(page, "05b-documentation")
    page.get_by_role("navigation", name="Documentation").get_by_role("link", name="QE Studio").click()
    expect(page.get_by_role("heading", level=1, name="QE Studio")).to_be_visible()
    expect(page.get_by_test_id("docs-toc")).to_contain_text("The gates")
    page.get_by_role("navigation", name="Previous and next pages").get_by_role("link", name=re.compile("Copilot")).click()
    expect(page.get_by_role("heading", level=1, name="Copilot")).to_be_visible()
    page.get_by_label("Search documentation").fill("traceback")
    expect(page.get_by_test_id("docs-search-results")).to_contain_text("Bug Scan")
    page.get_by_role("link", name="Open app").click()
    expect(page.get_by_test_id("stat-projects")).to_be_visible()
    page.get_by_test_id("card-bugs").first.click()
    expect(page.get_by_role("heading", name="Bug Scan")).to_be_visible()
    expect(page.locator('ol[aria-label="Quality gates"]')).to_have_count(0)
    page.goto(UI)
    page.get_by_test_id("stat-findings").click()
    expect(page.get_by_role("heading", name="Open findings")).to_be_visible()
    page.goto(UI)
    page.get_by_test_id("stat-documents").click()
    expect(page.get_by_role("heading", level=1, name="Documents")).to_be_visible()


def test_05_settings_connection_is_real(page):
    page.goto(f"{UI}/settings")
    page.get_by_role("button", name="Test connection").click()
    expect(page.get_by_test_id("llm-ok")).to_contain_text("Connected to", timeout=90_000)
    assert "sk-" not in page.content()
    shot(page, "06-settings")


def test_06_ba_workflow_with_template_gherkin_and_gates(page):
    page.goto(f"{state['base']}/ba")
    page.locator('textarea[name="brief"]').fill("Warehouse staff need to reserve and restock inventory. Reservations must never exceed available stock. Quantities must be positive. Managers want an audit of every stock change.")
    page.locator('input[name="doc-title"]').fill("Inventory BRD")
    page.get_by_role("button", name="Generate document").click()
    wait_card(page, "Gate 0")
    page.goto(UI)
    expect(page.get_by_test_id("stat-need-approval")).to_contain_text("1")
    page.get_by_role("link", name=re.compile("^Approvals")).click()
    expect(page.get_by_test_id("approvals-summary")).to_contain_text("1 project needs your approval")
    shot(page, "06b-approvals-page")
    approve_next(page, "Gate 0")
    expect(page.get_by_text("Nothing needs your approval")).to_be_visible(timeout=15_000)
    page.goto(f"{state['base']}/runs")
    page.get_by_role("link", name="ba", exact=True).first.click()
    card = wait_card(page, "Gate 1")
    shot(page, "07-ba-gate1")
    links = card.get_by_role("link").evaluate_all("items => items.map(a => a.getAttribute('href'))")
    state["brd"], state["gherkin"] = links
    approve_next(page, "Gate 1")
    expect(page.get_by_test_id("run-status")).to_contain_text("completed", timeout=60_000)


def test_07_gherkin_is_editable_valid_and_downloadable(page):
    page.goto(UI + state["gherkin"])
    expect(page.get_by_test_id("gherkin-status")).to_contain_text("Valid Gherkin")
    expect(page.locator("pre").filter(has_text="Feature:")).to_be_visible()
    page.get_by_role("tab", name="source").click()
    box = page.get_by_label("Document content")
    original = box.input_value()
    assert original.lstrip().startswith(("Feature:", "@"))
    box.fill("this is not gherkin")
    page.get_by_role("button", name="Save version").click()
    expect(page.locator("p[role=alert]")).to_contain_text("Invalid Gherkin")
    box.fill(original + "\n  Scenario: Manager reviews audit\n    Given a stock change\n    When the manager opens the audit\n    Then the change is listed\n")
    page.get_by_label("Change note").fill("Added audit scenario")
    page.get_by_role("button", name="Save version").click()
    expect(page.get_by_test_id("doc-version")).to_have_text("v2")
    shot(page, "08-gherkin-editor")
    with page.expect_download() as info:
        page.get_by_role("link", name=".feature").click()
    assert info.value.suggested_filename.endswith(".feature") and "Manager reviews audit" in Path(info.value.path()).read_text()


def test_07b_gherkin_examples_are_an_editable_table(page):
    page.goto(UI + state["gherkin"])
    page.get_by_role("tab", name="source").click()
    box = page.get_by_label("Document content")
    box.fill(box.input_value() + "\n  Scenario Outline: Reserve quantities\n    Given stock of <stock>\n    When I reserve <wanted>\n    Then the result is <left>\n\n    Examples:\n      | stock | wanted | left |\n      | 5 | 2 | 3 |\n")
    page.get_by_role("tab", name="document").click()
    grid = page.get_by_test_id("table-block").last
    grid.get_by_label("row 2, column 1").fill("9")
    grid.get_by_role("button", name="Add row").click()
    grid.get_by_label("row 3, column 1").fill("4")
    grid.get_by_label("row 3, column 2").fill("1")
    grid.get_by_label("row 3, column 3").fill("3")
    page.get_by_role("button", name="Save version").click()
    expect(page.get_by_text("Saved as a new version")).to_be_visible(timeout=15_000)
    expect(page.get_by_test_id("gherkin-status")).to_contain_text("Valid Gherkin")
    page.get_by_role("tab", name="source").click()
    assert re.search(r"\| 9 +\| 2 +\| 3 +\|\n +\| 4 +\| 1 +\| 3 +\|", page.get_by_label("Document content").input_value())
    shot(page, "08c-gherkin-table")


def test_07c_edit_document_in_place_with_tables_and_images(page):
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAEBgIApD5fRAAAAABJRU5ErkJggg==")
    page.goto(UI + state["brd"])
    bar = page.get_by_test_id("save-bar")
    expect(bar.get_by_role("button", name="Save version")).to_be_disabled()
    block = page.get_by_test_id("text-block").nth(1)
    block.click()
    editor = page.get_by_label("Edit this block")
    editor.fill(editor.input_value() + " Added in place.")
    expect(page.get_by_test_id("live-preview")).to_contain_text("Added in place.")
    editor.blur()
    tools = page.get_by_test_id("doc-toolbar")
    tools.get_by_role("button", name="Add table").click()
    grid = page.get_by_test_id("table-block").last
    grid.get_by_label("row 1, column 1").fill("Owner")
    grid.get_by_label("row 2, column 1").fill("Priya | Ops")
    grid.get_by_role("button", name="Add column").click()
    grid.get_by_label("row 2, column 3").fill("Reviewed")
    tools.get_by_label("Add image").set_input_files({"name": "diagram.png", "mimeType": "image/png", "buffer": png})
    image = page.get_by_test_id("document-page").locator('img[alt="diagram.png"]')
    expect(image).to_be_visible(timeout=15_000)
    assert image.evaluate("i => i.naturalWidth") == 1
    page.get_by_label("Change note").fill("Edited in place")
    bar.get_by_role("button", name="Save version").click()
    expect(page.get_by_text("Saved as a new version")).to_be_visible(timeout=15_000)
    shot(page, "08d-document-edited-in-place")
    page.reload()
    assert page.get_by_test_id("table-block").last.get_by_label("row 2, column 1").input_value() == "Priya | Ops"
    expect(page.get_by_test_id("document-page").locator('img[alt="diagram.png"]')).to_be_visible()
    page.get_by_role("tab", name="source").click()
    text = page.get_by_label("Document content").input_value()
    assert "Added in place." in text and r"Priya \| Ops" in text and "](/api/documents/" in text
    page.get_by_label("Document content").fill(text + "\n\nTyped in source.\n")
    expect(page.get_by_test_id("source-preview")).to_contain_text("Typed in source.")
    page.get_by_role("button", name="Discard changes").click()
    expect(page.get_by_test_id("source-preview")).not_to_contain_text("Typed in source.")
    with page.expect_download() as info:
        page.get_by_role("link", name=".docx").click()
    assert len(Document(io.BytesIO(Path(info.value.path()).read_bytes())).inline_shapes) == 1


def test_08_document_edit_history_restore_and_exports(page):
    page.goto(UI + state["brd"])
    expect(page.locator(".prose-atlas h2").first).to_be_visible()  # opens formatted, not as raw markdown
    shot(page, "08b-document-formatted")
    page.get_by_role("tab", name="source").click()
    box = page.get_by_label("Document content")
    original = box.input_value()
    for heading in ("Executive Summary", "Functional Requirements", "Open Questions"):
        assert heading in original, "template headings are kept"
    box.fill(original + "\n\nEdited by a human reviewer.\n")
    page.get_by_role("button", name="Save version").click()
    version = page.get_by_test_id("doc-version")
    expect(version).not_to_have_text(re.compile(r"v1$"))
    edited = int(version.inner_text()[1:])
    with page.expect_download() as info:
        page.get_by_role("link", name=".docx").click()
    text = "\n".join(p.text for p in Document(io.BytesIO(Path(info.value.path()).read_bytes())).paragraphs)
    assert "Edited by a human reviewer." in text
    with page.expect_download() as info:
        page.get_by_role("link", name=".md").click()
    assert "Edited by a human reviewer." in Path(info.value.path()).read_text()
    page.get_by_role("tab", name=re.compile("history")).click()
    page.get_by_role("button", name=re.compile("Diff with")).first.click()
    expect(page.locator("pre")).to_contain_text("Edited by a human reviewer.")
    shot(page, "09-document-history")
    page.get_by_role("button", name="Restore").first.click()
    expect(version).to_have_text(f"v{edited + 1}")


def test_09_bug_scan_finds_real_issues(page):
    page.goto(f"{state['base']}/bugs")
    page.get_by_role("button", name="Scan repository").click()
    expect(page.get_by_test_id("run-status")).to_contain_text("completed", timeout=LLM_TIMEOUT)
    findings = page.get_by_test_id("findings")
    expect(findings).to_contain_text("admin.py", timeout=20_000)
    expect(findings).to_contain_text("shell=True")
    shot(page, "10-bug-scan")


def test_10_feature_builder_runs_real_tests_on_a_branch(page):
    page.goto(f"{state['base']}/feature")
    page.locator('input[name="feature-title"]').fill("Fix restock")
    page.locator('textarea[name="feature-spec"]').fill("In inventory.py, restock(stock, quantity) wrongly subtracts. It must return stock + quantity and raise ValueError when quantity is not positive. Add tests in tests/test_inventory.py.")
    page.get_by_role("button", name="Build feature").click()
    card = wait_card(page, "Review change")
    expect(card).to_contain_text("stock + quantity")
    expect(card).to_contain_text("PASS")
    shot(page, "11-feature-diff")
    card.get_by_role("button", name="Approve").click()
    expect(page.get_by_test_id("run-status")).to_contain_text("completed", timeout=60_000)
    expect(page.get_by_text("Commit", exact=False).first).to_be_visible()
    shot(page, "12-feature-committed")


def test_10b_fix_a_finding_on_a_branch(page):
    page.goto(f"{state['base']}/bugs")
    row = page.get_by_test_id("findings").locator("li").filter(has_text="admin.py").first
    row.get_by_role("button", name="Fix on a branch").click()
    card = wait_card(page, "Review change")
    expect(card).to_contain_text("diff --git a/admin.py")
    shot(page, "12b-bug-fix-diff")
    card.get_by_role("button", name="Approve").click()
    expect(page.get_by_test_id("run-status")).to_contain_text("completed", timeout=60_000)


def test_11_qe_lifecycle_real_model_real_pytest(page):
    page.goto(f"{state['base']}/qe")
    page.get_by_role("button", name="Start QE lifecycle").click()
    expect(page.get_by_test_id("run-stages")).to_be_visible(timeout=30_000)
    expect(page.get_by_test_id("run-metrics")).to_contain_text("Elapsed")
    for gate in range(1, 5):
        approve_next(page, f"Gate {gate}")
        if gate == 3:
            shot(page, "13-qe-progress")
    card = wait_card(page, "Gate 5")
    summary = card.inner_text()
    assert re.search(r"Verdict (PASS|FAIL): \d+/[1-9]\d* tests passed", summary), f"tests must really execute: {summary}"
    state["qe_tokens"] = page.get_by_test_id("run-metrics").inner_text()
    shot(page, "14-qe-gate5")
    approve_next(page, "Gate 5")
    expect(page.get_by_test_id("run-status")).to_contain_text("completed", timeout=60_000)
    shot(page, "15-qe-complete")


def test_12_chat_answers_from_real_documents_and_persists(page):
    page.goto(f"{state['base']}/chat")
    page.get_by_role("button", name="New chat").click()
    pane = page.get_by_test_id("chat-pane")
    box = pane.locator("textarea")
    box.fill("List the saved documents in this project with their kinds. Use your tools.")
    box.press("Enter")
    expect(pane).to_contain_text("Inventory BRD", timeout=180_000)
    shot(page, "16-chat-documents")
    page.wait_for_timeout(3000)
    page.reload()
    saved = page.get_by_role("list", name="Saved chats").get_by_role("button", name=re.compile("^List the saved documents"))
    expect(saved).to_be_visible(timeout=15_000)
    saved.click()
    expect(page.get_by_test_id("chat-pane")).to_contain_text("Inventory BRD", timeout=15_000)
    shot(page, "17-chat-reopened")


def test_13_chat_memory_new_window_and_specialist_agent(page):
    with page.expect_popup() as popup:
        page.get_by_role("link", name="Open in new window").click()
    window = popup.value
    window.wait_for_load_state()
    window.get_by_label("Agent for new chat").select_option("project-copilot")
    window.get_by_role("button", name="New chat").click()
    pane = window.get_by_test_id("chat-pane")
    box = pane.locator("textarea")
    box.fill("Remember this for the project: the release freeze starts on Friday.")
    box.press("Enter")
    deadline = time.time() + 180
    while time.time() < deadline:
        if b"freeze" in api_get(f"/projects/{state['id']}/memories"):
            break
        time.sleep(2)
    else:
        raise AssertionError("the agent did not store the memory")
    expect(window.get_by_text(re.compile(r"Project memory \(1\)"))).to_be_visible(timeout=30_000)
    window.get_by_label("Agent for new chat").select_option("principal-test-architect")
    window.get_by_role("button", name="New chat").click()
    messages = window.get_by_test_id("chat-messages")
    expect(messages).to_contain_text("Ask about this project", timeout=15_000)  # a truly empty chat
    expect(messages).not_to_contain_text("Friday")
    box = window.get_by_test_id("chat-pane").locator("textarea")
    box.fill("When does the release freeze start, according to what you remember for this project?")
    box.press("Enter")
    expect(messages.locator('[data-role="assistant"]').last).to_contain_text("Friday", timeout=180_000)
    window.set_viewport_size({"width": 1100, "height": 800})
    window.screenshot(path=str(EVIDENCE / "18-chat-new-window.png"))
    window.close()


def test_14_governance_ledger_and_metrics_are_real(page):
    page.goto(f"{state['base']}/governance")
    expect(page.get_by_test_id("ledger-valid")).to_contain_text("Chain valid")
    expect(page.get_by_text("Administrator").first).to_be_visible()  # the ledger names the signed-in account
    shot(page, "19-governance")
    page.goto(f"{state['base']}/runs")
    expect(page.get_by_role("heading", name="Agent calls")).to_be_visible()
    expect(page.get_by_text("business-analyst").first).to_be_visible()
    expect(page.get_by_role("cell", name="Avg ms").or_(page.get_by_text("Avg ms")).first).to_be_visible()
    shot(page, "20-metrics")


def test_15_prompt_version_and_real_eval(page):
    page.goto(f"{state['base']}/prompts")
    page.get_by_role("button", name=re.compile("business.analyst", re.I)).click()
    page.get_by_role("button", name="Run with the real model").click()
    expect(page.get_by_text(re.compile(r"\d/5 passed"))).to_be_visible(timeout=180_000)
    box = page.get_by_label("Prompt body")
    box.fill(box.input_value() + "\nPrefer short scenario names.")
    page.get_by_label("Reason for change").fill("Shorter names")
    page.get_by_role("button", name="Save new version").click()
    expect(page.get_by_text("active v2")).to_be_visible()
    page.get_by_role("button", name="Activate").click()
    expect(page.get_by_text("active v1")).to_be_visible()
    shot(page, "21-prompts")


def test_15b_agents_page_evals_kill_switch_and_real_numbers(page):
    page.goto(f"{UI}/agents")
    cards = page.get_by_test_id("agent-card")
    expect(cards).to_have_count(11)  # doc_reviewer and gherkin_author merged into their plugin-named agents
    expect(page.get_by_test_id("risk-legend")).to_contain_text("can change code")
    page.get_by_role("button", name="Run all evaluations").click()
    expect(page.get_by_role("button", name="Running evaluations")).to_be_visible()
    expect(page.get_by_role("button", name="Run all evaluations")).to_be_enabled(timeout=420_000)
    expect(page.get_by_test_id("agent-cards")).not_to_contain_text("evals not run")
    state["eval_summary"] = page.get_by_test_id("agent-stats").inner_text()
    (EVIDENCE / "eval-summary.txt").write_text(page.get_by_test_id("agent-cards").inner_text())
    shot(page, "21b-agents")
    cards.filter(has_text=re.compile("confidence.reviewer", re.I)).click()
    expect(page).to_have_url(re.compile("/agents/confidence-reviewer"))
    detail = page.get_by_test_id("agent-detail")
    expect(page.get_by_test_id("agent-details-table")).to_contain_text("Tokens per model call")
    expect(detail).to_contain_text("scores weak doc low")
    detail.get_by_label("Reason").fill("Temporarily off for the test")
    detail.get_by_role("button", name="Disable agent").click()
    expect(page.get_by_test_id("agent-details-table")).to_contain_text("Disabled")
    shot(page, "21c-agent-disabled")
    page.get_by_test_id("agent-detail").get_by_role("button", name="Enable agent").click()
    expect(page.get_by_test_id("agent-detail").get_by_role("button", name="Disable agent")).to_be_visible()


def test_15e_admin_creates_user_who_sees_only_their_own_work(page):
    name, secret = f"qa.user{int(time.time())}", base64.urlsafe_b64encode(os.urandom(15)).decode()
    page.goto(f"{UI}/users")
    page.locator('input[name="new-username"]').fill(name)
    page.locator('input[name="new-password"]').fill(secret)
    page.get_by_label("Allow deepseek-v4-flash-global").check()  # the configured model is in the list; a user can run only ticked models
    page.locator('input[name="new-tokens"]').fill("50000")
    page.locator('input[name="new-until"]').fill("2099-01-31")
    page.get_by_role("button", name="Create user").click()
    card = page.get_by_test_id("user-card").filter(has_text="50,000")
    expect(card).to_be_visible(timeout=15_000)
    assert secret not in page.content()
    shot(page, "22b-users")
    guest = page.context.browser.new_context(viewport={"width": 1440, "height": 900})
    tab = guest.new_page()
    tab.goto(UI)
    expect(tab).to_have_url(re.compile("/login"), timeout=15_000)
    shot(tab, "22a-login")
    tab.get_by_label("Username").fill(name)
    tab.get_by_label("Password").fill("not-the-right-one")
    tab.get_by_role("button", name="Sign in").click()
    expect(tab.locator("p[role=alert]")).to_contain_text("not correct")
    tab.get_by_label("Password").fill(secret)
    tab.get_by_role("button", name="Sign in").click()
    expect(tab.get_by_test_id("signed-in-user")).to_contain_text(name, timeout=30_000)
    expect(tab.get_by_text("No projects yet")).to_be_visible(timeout=15_000)
    expect(tab.get_by_role("link", name="Users")).to_have_count(0)
    tab.goto(f"{state['base']}")
    expect(tab.get_by_text("Not found")).to_be_visible(timeout=15_000)
    guest.close()
    log = (EVIDENCE / "server.log").read_text(errors="replace")
    assert secret not in log and name not in log and os.environ["ATLAS_ADMIN_PASSWORD"] not in log


def test_15c_observability_across_projects_and_per_run(page):
    page.goto(f"{UI}/observability")
    expect(page.get_by_role("heading", name="Observability")).to_be_visible()
    log = page.get_by_test_id("observability-log")
    expect(log).to_be_visible(timeout=15_000)
    expect(page.get_by_test_id("ledger-integrity")).to_contain_text("Audit ledger verified")
    expect(page.get_by_test_id("mcp-note")).to_contain_text("no MCP server")
    page.get_by_role("tab", name=re.compile("^Skills")).click()
    expect(log.locator('[data-kind="skill"]').first).to_be_visible(timeout=10_000)
    expect(log.locator('[data-testid="log-entry"]:not([data-kind="skill"])')).to_have_count(0, timeout=10_000)
    expect(log).to_contain_text("planning-tests")
    page.get_by_role("tab", name=re.compile("^Agents")).click()
    expect(log.locator('[data-kind="agent"]').first).to_be_visible(timeout=10_000)
    log.locator('[data-kind="agent"] button').first.click()
    expect(log).to_contain_text("prompt_ref")
    shot(page, "21d-observability-all")
    page.get_by_role("tab", name=re.compile("^Tools")).click()
    expect(log.locator('[data-kind="tool"]').first).to_be_visible(timeout=10_000)
    page.goto(f"{state['base']}/observability")
    first_run = page.get_by_label("Run").locator("option").nth(1).get_attribute("value")
    page.get_by_label("Run").select_option(first_run)
    expect(page.get_by_test_id("observability-log")).to_be_visible(timeout=10_000)
    shot(page, "21e-observability-run")
    with page.expect_download() as download:
        page.get_by_role("link", name="Download JSON").click()
    assert download.value.suggested_filename == "agentic-qe-observability.json"


def test_16_light_theme_and_no_page_errors(page):
    page.goto(state["base"])
    page.get_by_role("button", name="Switch to light mode").click()
    shot(page, "22-light-theme")
    page.get_by_role("button", name="Switch to dark mode").click()
    assert state["console_errors"] == [], state["console_errors"]
