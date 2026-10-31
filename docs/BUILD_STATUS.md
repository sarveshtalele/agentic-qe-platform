# Build status

_Last updated: 2026-10-29_

## Implemented and exercised

- [x] Single local web application with responsive navigation across the core lifecycle workspaces.
- [x] SQLite storage for projects and the main lifecycle artefacts; globally unique, stable IDs per prefix.
- [x] Document uploads, type/size validation, SHA-256 duplicate detection and text extraction for the supported formats.
- [x] Requirement generation with optional OpenAI-compatible endpoint and honest heuristic fallback; source excerpts and draft statuses.
- [x] Editable requirements, stories, priorities/statuses and acceptance criteria; template-based story generation.
- [x] Local repository path onboarding and safe ZIP ingestion; static file inventory, language/framework guesses, likely entry points, test files, route hints and read-only Git metadata.
- [x] Heuristic secret/suspicious-pattern scanner with redacted secret evidence and persisted finding status.
- [x] Implementation plan creation, baseline metadata, linked artefacts and approval status (no source write capability).
- [x] Test case draft generation; test runner detects pytest/npm scripts and records actual command outcome.
- [x] Test command execution disabled by default, with an explicit opt-in environment flag and timeout.
- [x] Traceability matrix for requirement/story/test links, plus explicit limitations around implementation/execution proof.
- [x] Markdown and CSV exports; ZIP packaging, inclusion/exclusion manifest, archive integrity validation and download endpoint.
- [x] FastAPI OpenAPI docs and setup/troubleshooting documentation.
- [x] Optional synthetic demo seeder (not automatically run).

## Deferred / partial

- [ ] GitHub OAuth repository picker and least-privilege installation permissions.
- [ ] Remote commit/push/merge or pull-request creation.
- [ ] AI code generation, isolated worktrees, unified diffs and accept/reject patch controls.
- [ ] Full asynchronous job queue with safe cancellation/retry of long-running operations.
- [ ] Versioned migration history; schema currently initializes idempotently at startup.
- [ ] Full control/approval/audit matrix and multi-user authentication/authorization.
- [ ] Formal architecture graph or AST-based symbol/call graph across languages.
- [ ] Dedicated SAST/dependency vulnerability database adapters, DAST, container scans and release gates.
- [ ] Full API/integration/E2E browser test execution adapters across multiple languages.
- [ ] OCR for scanned PDFs and richer source page/range mapping for all document formats.
- [ ] DOCX/XLSX/PDF report exporters beyond Markdown/CSV and source ZIP.
- [ ] Container/OS sandbox, resource quotas and strict network isolation for test commands.

## Commands run in the build environment

| Command | Result |
|---|---|
| `python -m py_compile backend/app.py` | Passed |
| `node --check frontend/app.js` | Passed |
| `pytest -q` | **8 passed** |
| API integration: create project, upload/parse source, generate drafts, story/test relationships, traceability, repository analysis, scanner, ZIP | Passed via integration suite |
| Path-boundary / ZIP traversal checks | Passed via integration suite |
| Generated FastAPI starter app's real pytest command through API | Passed via integration suite (captured exit code 0 and pytest output) |
| Downloaded ZIP open + `ZipFile.testzip()` validation | Passed via integration suite |
| Browser-driven Chromium UI automation | Not run: Chromium executable was not present in the build environment. Frontend JavaScript syntax and served static assets were checked. |

## Integrity and release notes

- Test outcomes in this file reflect the test commands that were actually executed for this build; no live GitHub OAuth, AI provider, external scanner or E2E integration is claimed.
- The browser is not automatically seeded with demo projects. Run `python scripts/seed_demo.py` against a locally running server to create explicitly synthetic records.
- Local command execution is disabled by default. When enabled it runs with host permissions and is not sandboxed.
