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
- [x] Previous code preserved in Git at commit 09f14fe

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
- [x] Playwright E2E on real model and browser with screenshots: 32 of 32
- [x] Windows, macOS, and Linux: offline tests and UI build run in CI

## Open items from the owner

- [x] Verify by eye: home page, Agents, live QE view, feature review, observability
- [x] Every feature tested on `personal-finance-mcp`, adding a new tool: 8 of 8 E2E tests pass
- [x] Complete screenshot evidence in `docs/evidence`
- [x] Lint clean: noise came from the `.next-run` build folder, which is now ignored
- [ ] Private repos: logic has offline tests with a stubbed GitHub API. A live check of connect, clone, pull request, and merge needs the owner's token
- [ ] A real Windows double-click of `start-windows.bat`. CI runs the code paths but not the launcher itself
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
- [x] Clean production export: `python scripts/package_azure.py --repo`
- [ ] Deploy on real Azure. Needs your subscription

## Rename, observability, launchers

- [x] Rename to Agentic QE Platform. `ATLAS_` settings and the database file keep their names so existing data still works
- [x] Observability across projects, per project, and per run
- [x] `start-mac.command` run on macOS. `start-windows.bat` written; a real Windows double-click is not yet checked
- [x] Commit and push `feat/real-maf-platform`

## Sandbox, navigation, docs site

- [x] Full clones, complete scan with coverage, Fix all
- [x] Repository page shows the connected repository and sandbox first
- [x] Remove gate ribbon; link every card to its tab
- [x] Rebuild Documentation as a docs site
- [x] `README.md` and `docs/PROJECT_STRUCTURE.md`
- [x] Every feature passes on `personal-finance-mcp`: 10 of 10 E2E tests

## Document editor

- [x] In-place editing, table grids, images, live preview
- [x] BA Studio links to current and recent documents

## Accounts, accuracy, live views

- [x] Admin login, users, allocations, owner-scoped data
- [x] Confidence review at every gate; reliable JSON handling
- [x] Discovery structure and checks
- [x] Live run log, document cards, agent cards and pages
- [x] `docs/AZURE_SYSTEM_DESIGN.md`, including multi-user sandboxes (design only)
- [ ] Build the design: PostgreSQL, Blob Storage, Key Vault, sandbox jobs

## Integrity fixes (Phase 1, done 2026-11-01)

- [x] The signer is the signed-in account id, never a typed name; `by` and `author` removed from request models
- [x] Fix all marks findings `fix_attempted`, not `fixed`, unless the verdict is PASS or NO NEW FAILURES; still open for the next Fix all
- [x] Saving a test case table rebuilds the stored cases from it, validated; an invalid table is refused with a 400

## Next, after your approval

- [ ] `docs/PLUGIN_AND_UI_PLAN.md`: 15 phases, approved 2026-11-01. Phases 1 to 3 done, phase 4 next
- [x] Phase 1, agent names: agents use the plugin's hyphenated keys; `doc_reviewer` merged into `confidence-reviewer` and `gherkin_author` into `business-analyst`; migration `006_agent_plugin_names.sql` moves stored history (checked by `test_migration_006_*`)
- [ ] Phase 1, agent names: live evals of the merged prompts on the real model not yet run
- [ ] Phase 1, `qa-execution-engineer` arrives with phase 5

## Phase 2: errors, recovery, and debugging (ERR)

- [x] `core/errors.py` typed errors; `run_failures` table (migration 007) with the rejected reply saved under the run
- [x] JSON parsing never accepts a fragment; length, JSON, and schema failures have separate codes
- [x] `POST /api/runs/{id}/retry`; design and generate keep finished batches; partial result marked and not approvable
- [x] API error shape and `X-Request-Id`; run error card; `error.tsx` and `global-error.tsx`
- [x] No-cache control on model calls, checked against the real proxy
- [x] Broad `except` audit
- [x] Observability Errors tab, error code docs page (rest of Part 4 and 5)
- [x] Settings: admin-only application log download by day (OPS-4 link)
- [ ] Failure inside a gate approval handler cannot be retried safely yet
- [ ] Live run on a real repository to see a real partial result

## Phase 2, second half (OPS)

- [x] OPS-1 Observability paged and filtered in SQL, migration 008, Load more
- [x] OPS-2 One active run per project and workflow kind (409, atomic claim)
- [x] OPS-3, OPS-4 Daily JSONL app log, retention, admin download
- [x] OPS-5 Deleting a project removes its `data/runs/<id>/` folders
- [x] OPS-6 Model-free browser smoke test in CI (`python scripts/dev.py smoke`; first CI run on all three systems not seen yet)

## Awaiting your decision

- [ ] Rotate the model API key, which is in old Git history on `origin/main`
- [ ] Rewrite Git history to remove that key, if wanted
- [ ] Migrate old `data/sdlc.sqlite3` projects
- [x] A change review cannot show above 60 beside a failing test verdict; discovery accepts paths the repository itself mentions
- [x] A generated test file that cannot import no longer stops the other tests from running

## Phase 3a: models, allowed models, and limits (MDL), 2026-11-01

- [x] specs.md MDL-1 to MDL-5
- [x] Migration 009: `models`, `user_models`, `user_limits`, `agent_calls.model/user_id`, `agent_settings.model`, `runs.user_id/model`, `chat_threads.model`
- [x] `core/models.py`, `auth.check_allowance` / `auth.model_for`, `llm.test_connection` per model, `AQE-ALLOW-002`
- [x] Limit during a run: batch code re-raises it instead of splitting or swallowing it
- [x] Model, time zone, and usage endpoints in `api/settings.py`; users API in `api/auth.py`
- [x] UI: Users, Settings models, model picker on run forms and chat, header tokens, usage page
- [x] Tests (ScriptedClient)
- [x] Real two-model run through the proxy (`deepseek-v4-flash-global`, `kimi-k2.6`): each `agent_calls` row holds its model
- [ ] Not verified: Windows `tzdata`, the browser UI, e2e
- [ ] Next task, not built: roles and project members

## Phase 3b: roles, gate signing, members, account page (ROL), 2026-11-01

- [x] specs.md ROL-1 to ROL-8
- [x] Migration 010 (`users.role`, `sessions.last_seen`, `project_members`)
- [x] `core/auth.py`: roles, rules, members, gate signers, password change, idle timeout
- [x] API: members, transfer, gate roles, account password; role on users; project `my_role`, `can_sign`
- [x] Observability SQL includes member projects
- [x] UI (type-checked only): Account page, role select, gate roles, Members card, Approve hidden when not allowed
- [x] Tests: `tests/test_access.py`
- [ ] Not verified: browser UI, e2e
- [ ] Cost in rupees per user, deferred until the proxy reports cost per call
- [x] Agents page chooses a model per agent, and saving other controls keeps it
