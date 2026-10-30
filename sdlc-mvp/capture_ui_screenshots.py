import asyncio
import os
import sys
from playwright.async_api import async_playwright

SCREENSHOT_DIR = "/Users/sarveshtalele/.gemini/antigravity/brain/f4db9224-39cd-4e31-a5df-6e49e8c99886/screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

async def capture_all():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1600, "height": 1000},
            device_scale_factor=2  # High-DPI crisp screenshots
        )
        page = await context.new_page()

        print("1. Navigating to http://localhost:3000...")
        await page.goto("http://localhost:3000", wait_until="networkidle")
        await page.wait_for_selector("aside")

        # Create or select project
        select = page.locator("header select")
        options = await select.locator("option").all()
        has_project = False
        for opt in options:
            val = await opt.get_attribute("value")
            if val and val.strip():
                await select.select_option(val)
                has_project = True
                break

        if not has_project:
            # Click New Project
            await page.click("button:has-text('New Project')")
            await page.wait_for_timeout(1000)

        # Ensure project is selected
        await page.wait_for_selector("header select option:not([value=''])", state="attached", timeout=8000)

        # ----------------------------------------------------
        # VIEW 1: Home View with Real GitHub Repository Fetch
        # ----------------------------------------------------
        print("2. Fetching real GitHub repository on Home view...")
        await page.click("nav button:has-text('Home')")
        await page.wait_for_timeout(500)

        repo_input = page.locator("input[placeholder*='owner/repo']")
        await repo_input.fill("sarveshtalele/agentic-qe")
        fetch_btn = page.locator("button:has-text('Fetch Repository')")
        await fetch_btn.click()

        # Wait for repo dossier
        await page.wait_for_selector("text=Repository Dossier", timeout=12000)
        await page.wait_for_timeout(1000)
        await page.screenshot(path=f"{SCREENSHOT_DIR}/01_home_github_dossier.png")
        print("Captured 01_home_github_dossier.png")

        # ----------------------------------------------------
        # VIEW 2: Greenfield BA Studio
        # ----------------------------------------------------
        print("3. Executing Greenfield BA Studio...")
        await page.click("nav button:has-text('BA Studio')")
        await page.wait_for_selector("h2:has-text('Greenfield Requirements Studio')")

        ba_textarea = page.locator("textarea[placeholder*='Paste raw business requirements']")
        await ba_textarea.fill(
            "Enterprise Real-Time Settlement Engine: The platform shall process multi-currency payment "
            "transactions adhering to ISO 20022 message standards. It must reconcile balances every 60 seconds, "
            "trigger automated rollback upon settlement mismatch exceeding $0.01, and enforce cryptographic SHA-256 "
            "ledger immutability for all financial journal entries."
        )

        # Generate BRD & PRD
        await page.click("button:has-text('Generate BRD & PRD')")
        await page.wait_for_selector("button:has-text('Audit with Reviewer Agent')", timeout=15000)

        # Audit with Reviewer Agent
        await page.click("button:has-text('Audit with Reviewer Agent')")
        await page.wait_for_selector("button:has-text('Apply 1-Click Refinement')", timeout=15000)

        # 1-Click Refine
        await page.click("button:has-text('Apply 1-Click Refinement')")
        await page.wait_for_selector("span:has-text('96/100')", timeout=15000)
        await page.wait_for_timeout(1000)

        await page.screenshot(path=f"{SCREENSHOT_DIR}/02_greenfield_ba_studio.png")
        print("Captured 02_greenfield_ba_studio.png")

        # ----------------------------------------------------
        # VIEW 3: Brownfield Feature Studio & Error Debugger
        # ----------------------------------------------------
        print("4. Executing Brownfield Feature Studio...")
        await page.click("nav button:has-text('Feature Studio')")
        await page.wait_for_selector("h2:has-text('Brownfield Feature Builder')")

        feat_textarea = page.locator("textarea[placeholder*='e.g. Add webhook retry policy']")
        await feat_textarea.fill("Implement ISO 20022 PAC008 Settlement Validation Gateway with dead-letter queue")

        # Synthesize & Scaffolding
        await page.click("button:has-text('Synthesize & Scaffold Feature')")
        await page.wait_for_selector("button:has-text('Run Sandboxed Tests')", timeout=15000)

        # Run Tests
        await page.click("button:has-text('Run Sandboxed Tests')")
        await page.wait_for_selector("text=PASSED", timeout=15000)

        # Interactive Traceback Chat
        error_chat = page.locator("textarea[placeholder*='Paste terminal traceback or error message']")
        await error_chat.fill("ValueError: Invalid currency precision for JPY. Expected 0 decimals, received 2 in settlement_router.py line 88")
        await page.click("button:has-text('Diagnose & Auto-Patch')")
        await page.wait_for_selector("text=Diagnostic Diagnosis", timeout=15000)

        # Create PR
        await page.click("button:has-text('Create GitHub Pull Request')")
        await page.wait_for_selector("button:has-text('Merge PR to main')", timeout=15000)
        await page.wait_for_timeout(1000)

        await page.screenshot(path=f"{SCREENSHOT_DIR}/03_feature_studio_debugger.png")
        print("Captured 03_feature_studio_debugger.png")

        # ----------------------------------------------------
        # VIEW 4: Codebase Bug Diagnostic & Auto-Fix
        # ----------------------------------------------------
        print("5. Executing Bug Diagnostic...")
        await page.click("nav button:has-text('Bug Diagnostic')")
        await page.wait_for_selector("h2:has-text('Codebase Bug Diagnostic & Auto-Fix')")

        bug_textarea = page.locator("textarea[placeholder*='Describe the bug or paste error stacktrace']")
        await bug_textarea.fill("ZeroDivisionError: division by zero in calculate_risk_ratio when total_exposure is zero")
        await page.click("button:has-text('Run Codebase Scan & Diagnostic')")
        await page.wait_for_selector("button:has-text('Generate & Apply Regression Fix')", timeout=15000)

        # Apply fix
        await page.click("button:has-text('Generate & Apply Regression Fix')")
        await page.wait_for_selector("text=All Regression Tests Passed", timeout=15000)
        await page.wait_for_timeout(1000)

        await page.screenshot(path=f"{SCREENSHOT_DIR}/04_bug_diagnostic_fix.png")
        print("Captured 04_bug_diagnostic_fix.png")

        # ----------------------------------------------------
        # VIEW 5: Quality Engineering Hub
        # ----------------------------------------------------
        print("6. Executing QE Testing Hub...")
        await page.click("nav button:has-text('QE Testing Hub')")
        await page.wait_for_selector("h2:has-text('Autonomous Quality Engineering Hub')")

        # Strategy
        await page.click("button:has-text('Generate Test Plan & Strategy')")
        await page.wait_for_selector("text=Strategy Formulated", timeout=15000)

        # Synthesize Tests
        await page.click("button:has-text('Synthesize Test Cases')")
        await page.wait_for_selector("text=Synthesized", timeout=15000)

        # Run Suite
        await page.click("button:has-text('Execute Test Suite')")
        await page.wait_for_selector("text=Executed", timeout=15000)

        # Confidence
        await page.click("button:has-text('Run Release Confidence Review')")
        await page.wait_for_selector("text=Confidence Review", timeout=15000)
        await page.wait_for_timeout(1000)

        await page.screenshot(path=f"{SCREENSHOT_DIR}/05_qe_testing_hub.png")
        print("Captured 05_qe_testing_hub.png")

        # ----------------------------------------------------
        # VIEW 6: HITL Governance & Cryptographic Ledger
        # ----------------------------------------------------
        print("7. Executing HITL Governance & Cryptographic Ledger...")
        await page.click("nav button:has-text('HITL Governance')")
        await page.wait_for_selector("h2:has-text('Human-in-the-Loop Governance')")

        # Inspect Gate G3
        await page.click("text=G3")
        await page.wait_for_selector("text=Quality Gate G3 Inspection", timeout=10000)

        # Verify ledger
        await page.click("button:has-text('Verify Cryptographic Ledger')")
        await page.wait_for_selector("text=Verified", timeout=10000)
        await page.wait_for_timeout(1000)

        await page.screenshot(path=f"{SCREENSHOT_DIR}/06_governance_ledger.png")
        print("Captured 06_governance_ledger.png")

        # ----------------------------------------------------
        # VIEW 7: Multi-Agent Observability
        # ----------------------------------------------------
        print("8. Executing Multi-Agent Observability...")
        await page.click("nav button:has-text('Observability')")
        await page.wait_for_selector("h2:has-text('Multi-Agent Observability & Tracing')")
        await page.wait_for_timeout(1000)

        await page.screenshot(path=f"{SCREENSHOT_DIR}/07_observability_traces.png")
        print("Captured 07_observability_traces.png")

        # ----------------------------------------------------
        # VIEW 8: Platform Settings & Custom LLM
        # ----------------------------------------------------
        print("9. Executing Platform Settings...")
        await page.click("nav button:has-text('Settings')")
        await page.wait_for_selector("h2:has-text('Platform & Custom LLM Settings')")

        # Fill and test connectivity
        await page.click("button:has-text('Test Live Connectivity')")
        await page.wait_for_selector("text=Connected", timeout=10000)
        await page.wait_for_timeout(1000)

        await page.screenshot(path=f"{SCREENSHOT_DIR}/08_platform_settings.png")
        print("Captured 08_platform_settings.png")

        # ----------------------------------------------------
        # VIEW 9: Live Copilot Stream Drawer
        # ----------------------------------------------------
        print("10. Testing Live Stream Drawer...")
        # Click the AGUI Live Stream toggle button in header
        drawer_btn = page.locator("header button:has-text('AGUI Stream')")
        await drawer_btn.click()
        await page.wait_for_selector("h3:has-text('CopilotKit / AGUI Live Stream')")

        stream_input = page.locator("input[placeholder*='Send direct instruction to MAF agent network']")
        await stream_input.fill("Run compliance check on generated settlements")
        await page.click("button:has-text('Send')")
        await page.wait_for_timeout(1500)

        await page.screenshot(path=f"{SCREENSHOT_DIR}/09_copilot_stream_drawer.png")
        print("Captured 09_copilot_stream_drawer.png")

        await browser.close()
        print("All screenshots successfully captured!")

if __name__ == "__main__":
    asyncio.run(capture_all())
