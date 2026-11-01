# Tasks

`[x]` means done and checked by the test named in `specs.md`. `[ ]` means not done or not verified.

## Foundation

- [x] Real `agent-framework` packages replace the hand-written engine
- [x] SQLite with numbered migrations (`src/backend/migrations`)
- [x] Encrypted secrets, redaction, path confinement, origin and host guard
- [x] Hash-chained ledger and signed gates
- [x] Versioned documents and prompts
- [x] Cross-platform launcher (`scripts/dev.py`)
- [x] Activity hook writing `progress.md`
- [x] `CLAUDE.md` guardrails including no deletion without permission
- [x] Previous code preserved in `legacy/`

## Backend features

- [x] Git clone with `owner/repo`, ZIP upload, local folder import, re-sync
- [x] Private GitHub token: validate, encrypt, list repositories
- [x] Repository analysis from disk
- [x] Static scanners: ruff, secrets, JS rules, manifests
- [x] Workflows: `ba`, `qe`, `bug_scan`, `change`
- [x] Agent review with quote verification
- [x] Worktree branches, real test runs, retry, diff approval
- [x] Plugin rules: case multiplicity, one case per file, placeholder refusal, RED baseline, CSV and Jira export
- [x] Templates: built-in and upload
- [x] Source extraction: md, txt, pdf, docx, xlsx, pptx
- [x] Export: md, docx, feature, patch, csv, jira, changed-files ZIP
- [x] Document review and refine on demand
- [x] AG-UI chat with threads and memory
- [x] Agent evals through MAF
- [ ] Push, pull request, and merge against a real private repository. Code exists; it needs your token to verify

## UI

- [x] Projects page and inside-project routes
- [x] Overview, Repository, BA Studio, Documents, Feature Builder, Bug Scan, QE Studio, Governance, Runs & Metrics, Prompts, Copilot
- [x] Settings and Templates
- [x] Chat in a separate window

## Testing

- [x] Unit tests (`tests/test_core.py`)
- [x] Integration tests with real FastAPI, SQLite, git, pytest, and MAF (`tests/test_api_workflows.py`)
- [ ] Playwright E2E on real model and browser with screenshots (`tests/e2e`, `docs/evidence`). Marked done after a full pass
- [ ] Windows and Linux. CI matrix written (`.github/workflows/ci.yml`); it runs after you push

## Open items from the owner

- [x] Verify by eye: home page, Agents, live QE view, feature review, observability
- [x] Every feature tested on `personal-finance-mcp`, adding a new tool: 8 of 8 E2E tests pass
- [x] Complete screenshot evidence in `docs/evidence`
- [x] Lint clean: noise came from the `.next-run` build folder, which is now ignored
- [ ] Private repos: logic has offline tests with a stubbed GitHub API. A live check of connect, clone, pull request, and merge needs the owner's token
- [ ] Windows and Linux: source audit found no POSIX-only code. No Docker or other OS here, so real runs need CI after a push
- [x] Reviewer stricter, with deterministic checks (`core/doc_checks.py`)
- [x] Guardrails, evals, and governance for every agent (`maf/governance.py`, `maf/evals.py`, `evals/`)
- [x] Agent observability in the UI (`/agents`)
- [x] Refresh `tasks.md`, `maf-guide.md`, and other docs from final code
- [ ] `/advisor`: not available in this environment. Nothing to build

## Modular architecture and Azure

- [x] Split API routers, agents, tools, workflows into their own files
- [x] Model call limit and cut-off reply guard
- [x] Clean UI pass from screenshots: fixed the undefined result line and page overflow from long diffs
- [x] `docs/SYSTEM_DESIGN.md`, `docs/AZURE_DEPLOY.md` with INR prices
- [x] `scripts/package_azure.py`, backend and frontend startup scripts, run locally from the unpacked ZIPs
- [x] Clean production export with no `legacy/`: `python scripts/package_azure.py --repo`
- [ ] Deploy on real Azure. Needs your subscription

## Rename, observability, launchers

- [x] Rename to Agentic QE Platform. `ATLAS_` settings and the database file keep their names so existing data still works
- [x] Observability across projects, per project, and per run
- [x] `start-mac.command` run on macOS. `start-windows.bat` written; a real Windows double-click is not yet checked
- [ ] Commit and push `feat/real-maf-platform`

## Sandbox, navigation, docs site

- [x] Full clones, complete scan with coverage, Fix all
- [x] Repository page shows the connected repository and sandbox first
- [x] Remove gate ribbon; link every card to its tab
- [x] Rebuild Documentation as a docs site
- [x] `README.md` and `docs/PROJECT_STRUCTURE.md`
- [ ] Every feature passes on `personal-finance-mcp`

## Document editor

- [x] In-place editing, table grids, images, live preview
- [x] BA Studio links to current and recent documents

## Awaiting your decision

- [ ] Remove `legacy/`
- [ ] Rotate the model API key, which is in old Git history on `origin/main`
- [ ] Rewrite Git history to remove that key, if wanted
- [ ] Commit and push this branch
- [ ] Migrate old `data/sdlc.sqlite3` projects
