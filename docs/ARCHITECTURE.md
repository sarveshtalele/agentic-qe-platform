# Architecture — ForgeSDLC MVP

## Runtime model

```text
Browser (vanilla JS + CSS)
       │ same origin, JSON + multipart
       ▼
FastAPI app (`backend/app.py`) ─── OpenAPI (`/docs`)
       │
       ├── SQLite (`data/sdlc.sqlite3`)
       ├── Uploaded source documents (`data/uploads/`)
       ├── Local workspaces (`workspaces/`)
       └── Validated project ZIPs (`data/exports/`)
```

The app is served by one Uvicorn process and needs no frontend build step or remote production server. The frontend uses ordinary browser APIs and is served at `/static`. The default server host is `127.0.0.1`.

## Module responsibilities

- **Application shell and views:** `frontend/index.html`, `frontend/app.js`, `frontend/styles.css`. The sidebar switches among dashboard, projects, documents, requirements, backlog, repository explorer, development plans, Test Center, Security, traceability, run history, deliverables and settings.
- **HTTP and validation:** FastAPI route handlers and Pydantic request models in `backend/app.py`.
- **Persistence:** SQLite tables are created idempotently on import/startup. Foreign keys are enabled. Public artefact IDs use a shared counter per prefix to avoid collisions across projects.
- **Document ingestion:** `parse_document` adapters for text, PDF, DOCX, XLSX and PPTX; uploaded bytes and extracted text are stored separately. Duplicate content is detected with SHA-256.
- **Requirement generation:** `generate_requirements` calls an optional OpenAI-compatible endpoint when configured; otherwise `heuristic_requirements` extracts candidate sentences from real input. Both paths produce drafts. Source evidence is linked only when an exact excerpt can be associated with a stored document.
- **Repository intelligence:** directory inventory and metadata inspection exclude common secrets, binary files, VCS metadata, dependency directories and caches. Git queries are limited to read-only metadata (`rev-parse`, branch name and status). API route detection is based on static patterns.
- **Security scan:** small set of heuristic source patterns plus sensitive filename detection. Evidence for possible secrets is redacted. No dependency database is contacted.
- **Test runner:** test commands are selected from fixed supported runners (pytest or npm test). Execution is disabled by default, bounded by a timeout, and captures the real process outcome. The process inherits host permissions; no sandbox is claimed.
- **Packaging:** ZIP files are constructed from a resolved workspace root, exclude sensitive/unnecessary files, include an inclusion/exclusion manifest, and are integrity-checked before registration and download.

## Core data model

| Table | Purpose |
|---|---|
| `projects` | Project identity, description, repo path/remote metadata, latest analysis snapshot |
| `documents` | Source file metadata, digest, extraction text/method, warnings and version |
| `requirements` | Stable requirement ID, type, statement, priority/status, source reference and evidence classification |
| `stories` | User story text, acceptance criteria and persisted requirement relationships |
| `test_cases` | Test specification, steps, expected result and linked requirement/story |
| `workflow_runs` | Workflow type, actual stage/status, summary, logs and timestamps |
| `test_runs` | Test command, exit code, duration, captured outputs and `executed` evidence |
| `security_findings` | Scanner source, severity/confidence, file/line evidence, remediation and review status |
| `implementation_plans` | Objective, linked artefacts, baseline commit, affected files, steps/risks and approval status |
| `exports` | ZIP path, name, source snapshot, manifest and creation timestamp |
| `counters` | Globally unique per-prefix identifier allocation |

## Evidence vocabulary

- **Source-backed:** the artefact carries a source excerpt tied to the supplied material.
- **Inferred:** the artefact is a reasoned or heuristic draft without a fully verifiable source link.
- **Draft:** editable and not approved.
- **Approved:** an explicit workflow status. In this MVP, approval of an implementation plan does not imply source changes have taken place.
- **Verified:** used only when evidence such as actual test execution or archive integrity supports it. Merely creating a test case is not verification.

## Trust boundaries and known limitations

- Uploaded ZIP paths are checked for traversal and symlinks are not extracted.
- Local paths must resolve inside the configured workspace root.
- This is a single-user local tool, without login/session authorization. Do not bind it to a public interface.
- Command execution is opt-in, but enabling it does not sandbox the process.
- `backend/app.py` contains the initial MVP implementation and schema. As the app grows, separate routers/services/repositories and adopt versioned migrations (for example Alembic), a persistent worker queue, sandboxed execution and a more formal audit model.
- GitHub OAuth, branch/worktree-based change generation, diff review, PR integration, dedicated security scanners and complete E2E frameworks are future increments.
