---
name: generating-test-code
description: Synthesizes compilable, idiomatic test source code (Playwright TS, Vitest, PyTest, JUnit 5, NUnit/xUnit/MSTest) with 1:1 case traceability. Use when generating automated test suites.
metadata:
  author: Sarvesh Talele
  version: "1.4.0"
---

# Generating Test Code

Emits concrete test automation source files conforming to the native framework and idiom of the target repository.

## When to use
Activate when the generate stage runs (plugin command `qe-generate`), or when converting approved design specifications into executable test code.

## Strict Standards
1. **One Case Per File:** Exactly one test declaration per emitted test file.
2. **Canonical Comment:** First line must contain `// CASE_ID: <case-id>`.
3. **No Placeholders:** Zero `pass`, `TODO`, ellipsis (`...`), or `assert True`.
4. **Clean Imports:** Only import dependencies present in repository manifests. Maximum 10 imports.
5. **UI tests:** Playwright locators come from the real page. See the Playwright section of [references/LANGUAGE_RULES.md](references/LANGUAGE_RULES.md).
6. **UI evidence:** Copy `assets/playwright.config.ts` into the project. Wrap each case step in `test.step(...)` and attach a step screenshot (`<CASE_ID> step N`) after key assertions.
7. **Rules per Language:** See [references/LANGUAGE_RULES.md](references/LANGUAGE_RULES.md). Pinned tool versions: [references/VERSIONS.md](references/VERSIONS.md).

## Platform code step
The platform emits the test in code (planned: `qe/emit.py`, not yet built). Given `{"caseId","scenario","route","assertion"}`, it returns a validated Playwright test and fails on an invalid `caseId` or route. It writes nothing; save the output only after the user approves the file. The invalid-test-code check that already exists is `invalid_test_code` in `qe/execution.py`.
