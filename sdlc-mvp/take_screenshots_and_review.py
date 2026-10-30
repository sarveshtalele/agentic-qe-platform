import json
import os
import urllib.request
from playwright.sync_api import sync_playwright

NEXTJS_URL = "http://localhost:3000"
SCREENSHOT_DIR = "/Users/sarveshtalele/.gemini/antigravity/brain/f4db9224-39cd-4e31-a5df-6e49e8c99886/screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def run():
    # 0. Ensure default project exists
    try:
        req = urllib.request.Request(f"{NEXTJS_URL}/api/projects")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            if not data:
                create_req = urllib.request.Request(
                    f"{NEXTJS_URL}/api/projects",
                    data=json.dumps({
                        "name": "Enterprise Autonomous Banking QE",
                        "description": "High-throughput settlement and reconciliation gateway",
                    }).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(create_req)
    except Exception as e:
        print(f"Project ensure warning: {e}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1.5
        )
        page = context.new_page()

        print("[1/9] Capturing Repository Hub & GitHub Ingestion...")
        page.goto(NEXTJS_URL)
        page.wait_for_selector("text=Agentic QE", timeout=12000)
        page.wait_for_selector("header select option:not([value=''])", state="attached", timeout=8000)

        # Ingest GitHub repository
        page.fill("input[placeholder*='https://github.com/owner/repo']", "sarveshtalele/agentic-qe")
        page.click("button:has-text('Fetch Repository')")
        page.wait_for_selector("text=Ingested File Tree:", timeout=15000)
        page.wait_for_timeout(1000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/01_repository_hub_github.png")
        print("  -> Saved 01_repository_hub_github.png")

        print("[2/9] Capturing Greenfield BA Studio...")
        page.click("aside button:has-text('Greenfield BA Studio')")
        page.wait_for_selector("text=Business Requirements Definition", timeout=10000)
        page.click("button:has-text('Checkout Preset')")
        page.click("button:has-text('Generate Enterprise BRD')")
        page.wait_for_selector("text=Functional Business Rules", timeout=12000)
        page.click("button:has-text('Run Audit')")
        page.wait_for_selector("text=Verdict:", timeout=12000)
        page.click("button:has-text('Refine Document with Recommendations')")
        page.wait_for_selector("text=96 / 100", timeout=12000)
        page.wait_for_timeout(1000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/02_greenfield_ba_studio.png")
        print("  -> Saved 02_greenfield_ba_studio.png")

        print("[3/9] Capturing Feature Builder & Interactive Error Chat...")
        page.click("aside button:has-text('Feature Builder')")
        page.wait_for_selector("text=Feature Implementation & Branching", timeout=10000)
        page.click("button:has-text('Implement Feature Autonomously')")
        page.wait_for_selector("text=PASSED", timeout=12000)
        page.click("button:has-text('Paste Sample KeyError')")
        page.click("button:has-text('Analyze & Auto-Fix Error')")
        page.wait_for_selector("text=Fault Diagnosed & Patched!", timeout=12000)
        page.click("button:has-text('Create GitHub Pull Request')")
        page.wait_for_selector("text=Pull Request #", timeout=12000)
        page.wait_for_timeout(1000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/03_feature_builder_debugger.png")
        print("  -> Saved 03_feature_builder_debugger.png")

        print("[4/9] Capturing Codebase Bug Diagnostic & Auto-Fix...")
        page.click("aside button:has-text('Bug Diagnostic')")
        page.wait_for_selector("text=Repository Bug & Vulnerability Scan", timeout=10000)
        page.click("button:has-text('Scan Codebase')")
        page.wait_for_selector("text=BUG-01", timeout=12000)
        page.locator("button:has-text('Auto-Fix')").first.click()
        page.wait_for_selector("text=Regression Test Created:", timeout=12000)
        page.wait_for_timeout(1000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/04_bug_diagnostic.png")
        print("  -> Saved 04_bug_diagnostic.png")

        print("[5/9] Capturing Autonomous Quality Engineering Hub...")
        page.click("aside button:has-text('QE Test Studio')")
        page.wait_for_selector("text=Principal Test Architect", timeout=10000)
        page.click("button:has-text('Plan Strategy')")
        page.wait_for_selector("text=Test strategy planned!", timeout=8000)
        page.click("button:has-text('2. 4-Oracle Design')")
        page.click("button:has-text('Design Deterministic Cases')")
        page.wait_for_selector("text=TC-001", timeout=8000)
        page.click("button:has-text('3. Pytest Synthesizer')")
        page.click("button:has-text('Synthesize Pytest Code')")
        page.wait_for_selector("text=def test_", timeout=8000)
        page.click("button:has-text('4. Isolated Runner')")
        page.click("button:has-text('Run Sandboxed Test Suite')")
        page.wait_for_selector("text=passed in", timeout=8000)
        page.click("button:has-text('5. Confidence Review')")
        page.click("button:has-text('Evaluate Release Confidence')")
        page.wait_for_selector("text=/ 100", timeout=8000)
        page.wait_for_timeout(1000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/05_qe_testing_hub.png")
        print("  -> Saved 05_qe_testing_hub.png")

        print("[6/9] Capturing HITL Governance & Cryptographic Ledger...")
        page.click("aside button:has-text('HITL Governance')")
        page.wait_for_selector("text=Tamper-Evident SHA-256 Cryptographic Audit Ledger", timeout=10000)
        page.click("button:has-text('Verify Ledger Integrity')")
        page.wait_for_selector("text=Cryptographic Integrity Verified", timeout=8000)
        page.wait_for_timeout(1000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/06_hitl_governance_ledger.png")
        print("  -> Saved 06_hitl_governance_ledger.png")

        print("[7/9] Capturing Multi-Agent Observability & MAF Traces...")
        page.click("aside button:has-text('Observability & MAF')")
        page.wait_for_selector("text=Microsoft Agent Framework (MAF) Topology", timeout=10000)
        page.wait_for_timeout(1000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/07_multi_agent_observability.png")
        print("  -> Saved 07_multi_agent_observability.png")

        print("[8/9] Capturing Platform & Custom LLM Settings...")
        page.click("aside button:has-text('Platform Settings')")
        page.wait_for_selector("text=Custom LLM Configuration", timeout=10000)
        page.fill("input[placeholder*='https://api.openai.com/v1']", "https://api.openai.com/v1")
        page.fill("input[placeholder*='gpt-4o, claude-3-5-sonnet']", "gpt-4o")
        page.fill("input[placeholder='sk-...']", "sk-simulated-enterprise-token")
        page.click("button:has-text('Test Endpoint Connectivity')")
        page.wait_for_selector("text=Successfully connected", timeout=8000)
        page.wait_for_timeout(1000)
        page.screenshot(path=f"{SCREENSHOT_DIR}/08_platform_settings.png")
        print("  -> Saved 08_platform_settings.png")

        print("[9/9] Capturing Copilot Live Stream Drawer...")
        page.click("header button:has-text('Copilot Stream')")
        page.wait_for_selector("text=CopilotKit / AG-UI Live Stream", timeout=8000)
        page.fill("input[placeholder='Direct agents...']", "Verify all gate approvals before releasing to production")
        page.click("button:has(svg.lucide-send)")
        page.wait_for_selector("text=Verify all gate approvals before releasing to production", timeout=8000)
        page.wait_for_timeout(1500)
        page.screenshot(path=f"{SCREENSHOT_DIR}/09_copilot_stream_drawer.png")
        print("  -> Saved 09_copilot_stream_drawer.png")

        browser.close()
        print("ALL 9 SCREENSHOTS CAPTURED SUCCESSFULLY!")

if __name__ == "__main__":
    run()
