---
name: executing-tests
description: Dispatches test execution to local isolated runner adapters, capturing traces, standard streams, and JUnit XML reports. Use when executing automated tests.
metadata:
  author: Sarvesh Talele
  version: "1.4.0"
---

# Executing Tests

Executes test suites using runner adapters in project-local environments with structured log streaming and timeout enforcement.

## When to use
Activate when the execute stage runs (plugin command `qe-execute`), or whenever invoking test runners to capture verified pass/fail execution evidence.

## Runner Adapters
Consult [references/RUNNER_REGISTRY.md](references/RUNNER_REGISTRY.md) for the allowed commands and report paths across Playwright, Vitest, PyTest, Maven and Gradle. Pinned tool versions: [references/VERSIONS.md](references/VERSIONS.md).

## Playwright UI runs
Set `BASE_URL` in the environment. If the Playwright MCP server is connected (`mcp__playwright__browser_navigate`, `mcp__playwright__browser_snapshot`), use `browser_snapshot` to read the real accessibility tree when a locator fails; otherwise read the page source. MCP setup is opt-in and never auto-started.

In greenfield mode the first run of test-first suites records a RED baseline: failures are expected until the app exists and are reported as baseline, not as defects.

## Screenshot evidence (required)
Run every UI suite with screenshots on (`screenshot: "on"`, or `testInfo.attach` per step). After the run, the platform copies them out of the Playwright report in code: it reads `results/playwright.json` and writes them to `docs/qe/<app>/06-execution/evidence/e2e`. It writes `<caseId>-<step>.png` for each image attachment (base64 bodies and files), keeps only real PNG or JPEG data up to 5 MB, and refuses paths outside the project. `test-results/` is cleaned by the next run, so a screenshot that is not copied here is lost. The Gate 5 report embeds every image in `06-execution/evidence/`, and the dashboard flags any it does not show. This copy step is planned in `qe/execution.py` and is not yet built.

## MCP evidence
After the UI suite runs, write a plan `[{caseId, url, title?}]` from each E2E case's page to `docs/qe/<app>/06-execution/evidence/mcp-plan.json`. The platform then drives the Playwright MCP server in code, headless, and writes `<caseId>.png`, `<caseId>.snapshot.md` and `mcp-evidence.json` to `docs/qe/<app>/06-execution/evidence/mcp/`. With `BASE_URL` set, only its exact origin (host and port) is visited. Without it, only `localhost` URLs on the ports named in the plan (or the configured port) are visited, and well-known service ports are refused. A page that redirects to any other origin is recorded as `ok: false`; the redirect is detected after the browser follows it. If the MCP server cannot start (offline, or required tooling missing), record "MCP evidence skipped: <reason>" and continue; test-runner screenshots remain the primary evidence. This step is planned and not yet built.

## Platform code steps
- **JUnit summary:** the platform parses the JUnit XML in code (`parse_junit` in `qe/execution.py`) and returns total, passed, failed, skipped, durationMs, status, failures and cases. It writes nothing.
- **Verdict:** given raw counts, the platform returns the verdict in code (`verdict` in `qe/execution.py`). It returns `INCONCLUSIVE` when total is 0.
- **Runs:** suites run through `run_suite` in `qe/execution.py`, in an isolated project-local environment with a timeout.

## Verdict Integrity Rule
A run is ONLY marked `PASS` if test evidence confirms at least one executed passing test and zero failures. Empty suites or configuration errors are strictly marked `INCONCLUSIVE`.
