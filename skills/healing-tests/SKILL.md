---
name: healing-tests
description: Diagnoses execution failures, distinguishes true defects from flaky test bugs, and repairs selectors and fixtures while preserving assertions. Use when tests fail or need healing.
metadata:
  author: Sarvesh Talele
  version: "1.4.0"
---

# Healing Tests

Autonomous diagnostic and remediation engine for failed tests.

## When to use
Activate when the heal stage runs (plugin command `qe-heal`), or whenever a test failure needs root-cause classification and potential self-healing.

## Workflow
1. **Trace Analysis:** Ingest error message, stack trace, and DOM snapshot.
2. **Defect Classification:**
   - Test bug (selector drift, fixture desynchronization).
   - Application defect (real bug / regression).
3. **Healing Generation:** For test bugs, synthesize the minimal surgical diff.
4. **Assertion Preservation Gate:** Strictly verify that NO assertions are removed or softened.
5. **Re-Verification:** Re-run the healed test to confirm it now passes legitimately.
6. **Logging:** Record all findings in `07-healing/audit_log.json`.

Failure signatures and the allowed or forbidden remediation for each: [references/HEALING_PATTERNS.md](references/HEALING_PATTERNS.md).

## Platform code steps
- **Diagnosis:** given the error message and stack trace, the platform returns the category (`SELECTOR_DRIFT`, `APPLICATION_DEFECT`, `ENVIRONMENT_ERROR`) and whether it can be healed. Implemented as `classify_failure` in `qe/execution.py`.
- **Patch check:** given the test file, the broken selector and the healed selector, the platform returns the patched source as `patchedCode` and refuses any patch that changes the assertion count. Implemented as `assertions_preserved` in `qe/execution.py`. It never writes the file; the diff is applied only after the user approves it.
