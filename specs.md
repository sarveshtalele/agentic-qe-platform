# Specifications

Each requirement has an acceptance check. "E2E" means `tests/e2e`, "API" means `tests/test_api_workflows.py`, "Unit" means `tests/test_core.py`.

## Projects and navigation

| ID | Requirement | Check |
|---|---|---|
| PRJ-1 | The first page lists all projects as cards with search, archive, and delete. There is no project dropdown | E2E |
| PRJ-2 | Selecting a project opens its own pages at `/projects/{id}/...` | E2E |
| PRJ-3 | Delete needs the project name typed. Empty states show no invented data | API, E2E |

## Requirements authoring

| ID | Requirement | Check |
|---|---|---|
| BA-1 | Built-in BRD, PRD, and Stories templates. Upload `.md`, `.txt`, `.docx` templates | API |
| BA-2 | Source upload: md, txt, pdf, docx, xlsx, pptx, csv, json, yaml, de-duplicated by hash | API, Unit |
| BA-3 | Generated documents keep every template heading | API |
| BA-4 | An independent reviewer scores the draft; a low score triggers revision | API |
| BA-5 | Gherkin output passes the official parser, is editable, and invalid edits are refused | Unit, API, E2E |
| BA-6 | On-demand review and refine on any requirements document | API |
| BA-7 | Download MD and DOCX, and `.feature` for Gherkin | API, E2E |

## Versioning and governance

| ID | Requirement | Check |
|---|---|---|
| GOV-1 | Each save is an immutable version with hash, author, note, prompt reference; view, diff, restore | Unit, E2E |
| GOV-2 | Prompts are versioned, with activate and rollback. Each output records its prompt version | Unit, API |
| GOV-3 | Gates run in order with a named signer and HMAC signature; rejecting clears later gates | Unit |
| GOV-4 | The ledger is hash-chained and detects edits and deletions | Unit, E2E |
| GOV-5 | Agent evals run real prompts against `evals/*.json` and store results per prompt version | API |

## Repositories

| ID | Requirement | Check |
|---|---|---|
| REP-1 | Clone public HTTPS URLs and `owner/repo` | E2E |
| REP-2 | Private access by validated, encrypted token with a repository picker; no token in argv, URL, or config | Unit |
| REP-3 | ZIP upload refuses traversal, symlinks, and bombs | Unit, E2E |
| REP-4 | Local folder import copies without following symlinks | API |
| REP-5 | Scan reports languages, lines, frameworks, runners, tests, routes, symbols, CI, and commits from disk | Unit, E2E |

## Bugs and features

| ID | Requirement | Check |
|---|---|---|
| BUG-1 | Ruff, secret, JS, and manifest scanners return real lines | Unit |
| BUG-2 | Agent findings need a quote that exists in the file | Unit, API |
| BUG-3 | Re-scans do not duplicate findings; findings can be dismissed | API |
| CHG-1 | Changes happen in a worktree on a new branch. The main checkout stays untouched | API |
| CHG-2 | Real tests run, with retry on failure, and the verdict is honest | API |
| CHG-3 | Edits with escapes, protected paths, or secrets are refused | API |
| CHG-5 | Tests run before the change too. Only new failures count against it, environment failures give INCONCLUSIVE and no retry, and existing files cannot be overwritten whole | API |
| CHG-6 | Passing old tests is not enough. Functions named in the spec must appear in the diff, tests must change when the repo has tests, and stray files are refused. Gaps give INCOMPLETE | API |
| CHG-7 | Edit agents have no tools. Code travels in the message, the agent replies with structured edits, and Agentic QE Platform applies them through path, secret, and scope guards. Existing assertions a change alters are shown to the reviewer | API |
| CHG-4 | A human reviews the diff before commit. Optional push, pull request, merge, ZIP of changes | API |

## QE lifecycle

| ID | Requirement | Check |
|---|---|---|
| QE-1 | G0 to G5 pause in order and survive a restart through checkpoints | API |
| QE-2 | Unverifiable requirements are dropped | API |
| QE-3 | Each P0 or P1 requirement gets 1 Positive, 2 Negative, 1 Exception | Unit |
| QE-4 | One test per file, `CASE_ID` first line, no placeholders or tautologies | API |
| QE-5 | Zero executed tests is `INCONCLUSIVE`. Test code cannot see platform credentials | Unit |
| QE-6 | Healing cannot weaken assertions. Greenfield records a RED baseline | Unit |
| QE-7 | Traceability shows gaps and orphans; 11-column CSV and Jira CSV export | Unit, API |

## Chatbot

| ID | Requirement | Check |
|---|---|---|
| CHAT-1 | Streams over AG-UI through CopilotKit | API, E2E |
| CHAT-2 | Chats are saved, listed, reopened with history, renamed, deleted | API, E2E |
| CHAT-3 | Opens in a new window | E2E |
| CHAT-4 | Project memory reaches the agent in later chats | API, E2E |
| CHAT-5 | Agents are selectable per chat and can read documents and start workflows | E2E |

## Agent governance

| ID | Requirement | Check |
|---|---|---|
| AGT-1 | One registry lists every agent: purpose, risk tier, allowed tools, write access, token limit per call | Unit |
| AGT-2 | An agent receives only the tools its policy allows. Unlisted tools never reach the model | Unit |
| AGT-3 | An admin can disable an agent or change its token limit. A disabled agent refuses to run with a clear error, and the change goes to the ledger | API, E2E |
| AGT-4 | Guardrails: secrets redacted from input and output, likely prompt injection in user or repository text flagged, token budgets enforced. Each event is stored and shown | Unit, API |
| AGT-5 | Every agent has eval cases, including an adversarial one, with content, schema, Gherkin, and score checks run through MAF. Results are stored per prompt version | API, E2E |
| AGT-6 | Every agent call records agent, prompt version, tokens, latency, tool calls, status, and source (run, chat, eval) | API |
| AGT-7 | An Agents page shows policy, status, prompt version, eval score, calls, tokens, latency, errors, and guardrail events, from stored data only | E2E |
| AGT-8 | Requirements documents get deterministic checks that cap the reviewer score: requirement ids, vague wording, leftover template text, empty sections | Unit |
| AGT-9 | Agent keys are the agentic-qe plugin names with hyphens, one file per agent (`maf/agents/<key with underscores>.py`, `prompts/<key>.md`, `evals/<key>.json`). A document review is the `confidence-reviewer` and Gherkin writing is the `business-analyst`, each chosen by an artifact line in the request. A migration renames stored agent keys without losing history, folds a disabled merged agent into a disabled target, and never rewrites the ledger | Unit, API |

## Architecture and deployment

| ID | Requirement | Check |
|---|---|---|
| ARC-1 | Each agent, tool, workflow, and API area has its own file. Adding a workflow or agent needs no edit to existing workflows | Unit |
| ARC-2 | A process-wide limit bounds concurrent model calls (`ATLAS_MODEL_CONCURRENCY`) | Unit |
| ARC-3 | A reply cut off by the token limit is reported as cut off, never parsed as complete | Unit |
| DEP-1 | `scripts/package_azure.py` makes separate backend and frontend ZIPs with startup scripts, excluding tests, secrets, and runtime data | Unit |
| DEP-2 | Startup scripts build the environment on the server when the package changes, and skip the build otherwise | Local run; Azure run is the owner's |
| DEP-3 | SQLite journal mode is configurable, because WAL fails on network storage | Unit |
| DEP-4 | Published costs come from the Azure Retail Prices API in INR, with the date | Doc |

## Sandbox and complete scan

| ID | Requirement | Check |
|---|---|---|
| SBX-1 | Each project has its own sandbox: a full clone with complete history, one worktree per run, its own Python environment, and a scrubbed environment for test code. Older shallow clones are completed before a scan | Unit, API |
| SBX-2 | Bug Scan reviews every source file. Large files are read in parts, with real line numbers. The result states files reviewed out of total and lists any that were not reviewed | API, E2E |
| SBX-3 | **Fix all** fixes the most severe open findings on one branch, with the usual tests and human review. Fixed findings are marked when the change is approved | API |
| SBX-4 | The Repository page shows a connected repository and its sandbox first. The connect forms open only on request | E2E |

## Navigation

| ID | Requirement | Check |
|---|---|---|
| NAV-1 | The gate ribbon is removed from the project header. Gates stay on Overview and Governance | E2E |
| NAV-2 | Each tile and card opens its tab: home tiles, project card figures, and Overview cards. Findings and documents have pages across all projects | E2E |
| NAV-3 | Documentation works like an official docs site: its own page per topic, grouped sidebar, search, on-this-page links, breadcrumbs, previous and next | E2E |

## Document editing

| ID | Requirement | Check |
|---|---|---|
| DOC-1 | Documents open as a clean formatted page and can be edited in place, block by block, with changes shown live | E2E |
| DOC-2 | Tables, including Gherkin Examples, render as real tables and are edited as grids: change cells, add and remove rows and columns, insert new tables | E2E |
| DOC-3 | PNG, JPEG, GIF, and WebP images can be uploaded, are shown in the page, and export to DOCX. Content is checked by file signature. Images from other sites are not loaded | API, E2E |
| DOC-4 | Source view shows the raw text beside a live preview. Saving creates one immutable version; typing does not | E2E |
| DOC-5 | BA Studio links to the documents the current run created, and to recent documents, as they appear | E2E |

## Accounts and access

| ID | Requirement | Check |
|---|---|---|
| USR-1 | Every page and API needs a signed-in session. The admin login comes from `.env` | API, E2E |
| USR-2 | The admin creates users with a password, model, token allocation, and active dates, and can change or disable them | API, E2E |
| USR-3 | User passwords are salted scrypt hashes, usernames are encrypted at rest, and sessions are stored only as hashes. Logs, ledger, and API replies never hold passwords, and logs never hold usernames | Unit, API |
| USR-4 | Users see only their own projects and everything in them. Admin sees all | API |
| USR-5 | A run or chat uses the owner's model and stops with a clear error when tokens run out or dates pass | API |

## Agent accuracy

| ID | Requirement | Check |
|---|---|---|
| ACC-1 | A confidence review runs before every QE gate and beside the tests on code changes. A failed review shows as not run, never as a score. A low score sends the work back once | API |
| ACC-2 | Discovery covers purpose, end-to-end flow, architecture, all modules, interfaces, data, deployment, tests, and risks. Code checks headings, cited files, and module coverage | Unit, API |
| ACC-3 | A malformed model reply is reported as malformed. An inner fragment is never treated as the answer. Test design splits a batch that keeps failing | Unit, API |

## Live views

| ID | Requirement | Check |
|---|---|---|
| LIVE-1 | Runs show a live log of each step, including agent calls while they wait for the model | E2E |
| LIVE-2 | Documents a run creates show as cards on the right of the screen | E2E |
| LIVE-3 | Agents show as cards. Each opens its own page with a details table | E2E |

## Observability

| ID | Requirement | Check |
|---|---|---|
| OBS-1 | A log across all projects, and one per project, shows skills, agent calls, tools, MCP tools, workflow steps, approvals, guardrails, and ledger entries from stored data only | API, E2E |
| OBS-2 | Every tool call is stored with agent, project, run, redacted arguments, duration, and status, in workflows and chat | API |
| OBS-3 | Filter by project, run, type, and text. Each run can be opened as a full trace | API, E2E |
| OBS-4 | The filtered log downloads as JSON. Ledger integrity shows per project | API |
| OBS-5 | When no MCP server is connected, the page says so and shows zero | E2E |

## Launchers

| ID | Requirement | Check |
|---|---|---|
| RUN-1 | `start-windows.bat` and `start-mac.command` install on first use, run backend and UI, open the browser, and stop both together | Local on macOS; Windows through CI and the owner |

## Non-functional

| ID | Requirement | Check |
|---|---|---|
| NF-1 | Runs on Windows, macOS, Linux | CI matrix |
| NF-2 | Cross-site writes and DNS rebinding are blocked | API |
| NF-3 | Keys are never returned by the API and are encrypted at rest | API |
| NF-5 | A model call that hangs fails the run with a clear error after a bounded time (`ATLAS_MODEL_TIMEOUT`) | Unit |
| NF-4 | `progress.md` logs actions before and after, with time | Hook pipe test |

## Skill Studio (SKL), planned and not built

Full design in `docs/PLUGIN_AND_UI_PLAN.md`, Part 9.

- SKL-1: A skill starts from a BA document at a set version, an uploaded file, a brief, or an imported skill.
- SKL-2: A skill follows the Agent Skills specification and must load in MAF `FileSkillsSource`.
- SKL-3: Each save is an immutable version with SHA-256, author, and prompt reference.
- SKL-4: Output evaluations run with and without the skill in clean context, and report pass rate, time, tokens, and the difference.
- SKL-5: A grade passes only if its evidence exists in the output. No runs or no tests is INCONCLUSIVE.
- SKL-6: Trigger tests use a held-out set, and the best description is chosen by held-out score.
- SKL-7: A named person signs S0 to S4. Agents never do.
- SKL-8: A skill reaches an agent only after publishing. `allowed-tools` never widens an agent's tools.

## Skill bundles (SKL, continued)

- SKL-9: Skill Studio has its own harness from `create_harness_agent`, with a live check that picks full or structured mode.
- SKL-10: At S0 the user chooses instructions only, Python scripts, or TypeScript scripts.
- SKL-11: The install ZIP holds a `skill-name/` folder that MAF can load.

## Repository-aware changes and delivery (CHG), planned

- CHG-1: A code map covers every file in the repository.
- CHG-2: The agent can request more files, and the review sees whole files, callers, and the impact list.
- CHG-3: A delivery ZIP holds a code-written guide, files in real paths, a patch, and evidence.
- CHG-4: The ZIP is applied to a clean copy of the base commit and its tests rerun, and the result is shown as Verified or Not verified.
- CHG-5: Secrets, `.env`, and `.git` never enter a ZIP.

## Application builder (APP), planned

- APP-1: `app_build` builds an application from approved BA documents, with human decisions A0 to A3.
- APP-2: Every requirement traces to architecture, files, test cases, tests, and results.
- APP-3: The generated application goes through the QE lifecycle, and runs in the sandbox before delivery.

## Integrity (INT)

- INT-1: Gates, approvals, document versions, prompts, agent settings, findings, and run starts record the signed-in account id from the session. A name or `by` sent by a client is ignored. Display names are resolved on read for people who may see the project.
- INT-2: A change run marks findings `fixed` only when its test verdict is PASS or NO NEW FAILURES. Otherwise they are `fix_attempted`, which counts as open and is shown in the Bugs and Findings pages.
- INT-3: Saving a new version of a test case document parses its table back into cases and checks each with `TestCase`. Exports read the result. A table that does not parse or validate is refused with a 400 listing the problems.

## Errors and recovery (ERR)

- ERR-1: Failures are typed errors in `core/errors.py` with a code, message, action, and `retryable`: `AQE-MODEL-001` to `006`, `AQE-ALLOW-001`, `AQE-REPO-001`, `AQE-EVID-001`, `AQE-TEST-001`, `AQE-INT-001`. Old exception types stay as subclasses. `retryable` means a retry may succeed without any change; the UI offers Retry failed stage on every failed run, because the fix named in the action may already be done.
- ERR-2: A reply that is not valid JSON is `AQE-MODEL-001` with the position and the text around it. A reply cut off by `finish_reason` length is `AQE-MODEL-002`. Valid JSON with the wrong shape or fields is `AQE-MODEL-003`. An inner fragment of a broken reply is never accepted as the answer.
- ERR-3: Every failed stage writes one `run_failures` row (migration 007) with redacted stack and technical detail. The whole rejected model reply is saved after `redact()` under `data/runs/<run_id>/failures/` through `safe_path`. Nothing prints a traceback to the console.
- ERR-4: `POST /api/runs/{id}/retry` resumes a failed or interrupted run from its latest checkpoint with its state. Only one retry can run at a time. Retries count against the run token limit and the owner's allocation.
- ERR-5: `qe_design` and `qe_generate` save each finished batch under `data/runs/<run_id>/parts/` as it completes. A retry repeats only batches without a saved result. After two earlier failures of the same stage the stage ends with a partial result, marked in the gate title, summary, payload, and document title, and a partial result cannot be approved.
- ERR-6: Every API error is `{code, message, action, error_id, detail}`; `detail` is kept for older clients. Every response carries `X-Request-Id`. Model calls send the LiteLLM no-cache control, so a retry is not answered from the proxy cache. `ATLAS_MODEL_NO_CACHE=0` turns it off for endpoints that reject the field.
- ERR-7: The UI shows a failed run as a card (what happened, what to do, collapsed detail, Retry failed stage, Copy diagnostics), and `app/error.tsx` and `app/global-error.tsx` show an id and a retry button.
- ERR-8: Each `except Exception` in `src/backend` records the error or re-raises it.

## Observability, run limits, logs, and CI smoke (OPS)

- OPS-1: `GET /api/observability` pages and filters in SQL (migration 008 adds the indexes). One UNION over run events, agent calls, tool calls, guardrail events, and the ledger is ordered `ts DESC, source rank, id DESC` and paged by a keyset cursor: `before=<key>` returns the items after that key, and `next` is the key of the last item when more exist. Project, run, kind, and text filters and the owner scope are part of the SQL, so a page is never filled and then thinned. `total`, `counts`, `errors`, and `tokens` are counted in SQL over the whole scope. A user sees only rows of projects they own; the admin sees all. The export reads up to 25,000 matching records.
- OPS-2: Per project and workflow kind, only one run can be `running` or `waiting_approval` (a waiting run holds its worktree). `engine.start` claims the slot with one `INSERT ... WHERE NOT EXISTS` inside `BEGIN IMMEDIATE`; `engine.retry` claims it in the same way. A second start answers 409 with a message that names the active run and its page, and no error code. The slot frees when the run completes, fails, is rejected, cancelled, or interrupted.
- OPS-3: `data/logs/app-YYYY-MM-DD.jsonl` holds one JSON line per API request (request id, method, path without query string, status, duration, user id) and per warning or error record (with run, stage, agent, and error ids when known). A line never holds a request body, query string, cookie, or username, and passes `redact()`. A new file starts each day, so no file is ever renamed (safe on Windows). Files whose date in the name is older than `ATLAS_LOG_RETENTION_DAYS` (default 30) are deleted at start-up and when a new day starts; nothing else in the folder is touched.
- ERR-OBS: `GET /api/observability/errors?project_id=` groups run failures by code and agent (count, latest message, no stack), owner-scoped in SQL. Observability has a Log and an Errors view.
- OPS-4: `GET /api/logs?date=YYYY-MM-DD` downloads one day's file. The Settings page links to it for admins. Admin only (rule in `core/auth.py`), path through `safe_path`, a date that is not a real date is refused with 422.
- OPS-5: Deleting a project also removes `data/runs/<run_id>/` for each of its runs. Nothing else is deleted.
- OPS-6: CI runs `tests/e2e/test_smoke.py` (marker `smoke`) against a built app with no model: sign in, wrong password, navigation to the main pages, access refused for a non-admin on Users, and empty states. The administrator password is generated at test time.

## Models, allowed models, and token limits (MDL)

- MDL-1: Table `models` (name, label, enabled, is_default). The admin adds names by hand or with **Load from proxy**, which reads `/models` from the configured endpoint, drops the `*` wildcard, and enables nothing. Each model has a **Test** that sends a real short completion. The URL and key stay one encrypted setting. Migration 009 seeds the configured model as default and copies each `users.model` into that user's allowed list. Check: Unit, API.
- MDL-2: Table `user_models` lists the models each user may use. A user with none cannot run or chat (`AQE-ALLOW-001`). `users.model` is the user's default and must be one of theirs. The admin bypasses the list. Check: Unit, API.
- MDL-3: A call's model is the first of: the run's or chat's choice, the agent's model (`agent_settings.model`), the user's default, the system default. The result must be enabled and in the acting user's list, whatever way it was chosen; otherwise the call is refused and the attempt goes to `auth_events` by account id. `agent_calls.model` records the model really used. Check: Unit, API.
- MDL-4: Optional daily, weekly, and monthly token limits per user, and optional per-model limits (`user_limits`, model empty means all models), apply with the allocation and dates. Time zone is the admin setting `timezone`, default Asia/Kolkata. Days reset at midnight, weeks on Monday, months on the 1st. Tokens count from `agent_calls.user_id` (the account that started the call; a run uses its starter). A limit gives `AQE-ALLOW-002` naming the limit and its reset time. A run stops at the next call, keeps finished batches, and Retry failed stage continues after the reset. Chat obeys the same limits. Admin work, including agent evals, is never counted against a user. Check: Unit, API.
- MDL-5: Users page: model tick boxes, default, three limits, per-model limits, usage bars. Header: tokens left today with a warning from 80%. Admin-only usage page and `GET /api/usage` (by user, model, agent, day) with CSV export; no data shows an empty state. Check: tsc, API.

## Roles, gate signing, project members, account page (ROL)

- ROL-1: `users.role` (migration 010) is `qe_lead`, `ba`, `developer`, or `viewer`; default `developer`, so existing users keep what they can do. The environment admin is `admin`. A viewer account can read but never start, edit, run, or approve anything, in any project (403 naming the role). Only the admin sets a role (Users page, `PATCH /api/users/{id}`).
- ROL-2: The setting `gate_roles` maps each gate G0 to G5 to the roles that may sign it. A gate with no entry may be signed by any role that can write, so nobody loses the ability on upgrade. The admin edits it (`PUT /api/settings/gate-roles`, Settings page). It is checked on the server in `POST /api/projects/{id}/gates/{n}/decision` and in `engine.decide` for gate approvals, from the signed-in account (`auth.signer()`), never from the body; the admin may always sign. A refusal is 403 naming the roles needed. An approval that is not a gate needs a write role. Agents never approve.
- ROL-3: `project_members(project_id, user_id, role)` (migration 010). Members see the project and everything in it. A member's effective right is the lesser of the account role and the member role: a viewer on either side cannot write, and a gate role must be held by both. The owner has full control, limited only by the account role. A removed member loses access on the next request.
- ROL-4: `GET/POST/DELETE /api/projects/{id}/members` for the owner and the admin only. To add someone the owner types the exact username; it is looked up by keyed hash and the answer is only added or not found. Usernames are never listed to anyone else, and there is no list of users for non-admins.
- ROL-5: `POST /api/projects/{id}/transfer` (admin only) gives the project to another account by username and writes `project.transferred` to the ledger. The new owner leaves the member list.
- ROL-6: `/account`: change own password (current password, the same strength rule as the admin, other sessions end, the current one stays), and own models, limits, and usage. The environment admin's password lives in the environment and cannot be changed there. The event `password.changed` is recorded by account id; no password reaches a log or table in plain form.
- ROL-7: `ATLAS_SESSION_IDLE_MINUTES` (default 480) ends a session with no request for that long. `sessions.last_seen` is written at most once a minute.
- ROL-8: Every API path has a rule in `core/auth.py` (admin only, admin writes, project-owned, or `SESSION_ONLY`); a path with none is refused 403 for everyone but the admin. A test lists every route and fails when one has no rule.

## Plugin skills on MAF (PLG)

Design in `docs/PLUGIN_AND_UI_PLAN.md`, Part 1 "Decision: how skills run on MAF" and Part 9 "What I measured". Measured 2026-11-01 on the real proxy: when tools are offered, every model tested called tools never offered and ignored tool results; skill text placed in the message worked (6 of 6 facts, against 1 of 6 without). So no workflow depends on a tool to load a skill.

- PLG-1: `core/skills.py` loads `skills/` once through MAF `FileSkillsSource`, which acts as the validator. A skill folder MAF cannot load is a startup warning and is absent from `get`, `for_agent`, and the API. The folder is `ATLAS_SKILLS_DIR`, default `<root>/skills`; files are read through `safe_path`. Skill text is trusted platform content, unlike repository and document content. `get(name)` gives frontmatter and body, `references(name)` gives the reference files, `for_agent(key)` gives the skills named by the agent's policy. Check: Unit.
- PLG-2: The mapping lives in each agent's policy file as `skills`. A policy that names a skill that does not exist fails a test. `bug-reviewer`, `feature-engineer`, and `project-copilot` have none. Check: Unit.
- PLG-3: In workflows, `AgentCall` puts the chosen skills' SKILL.md body and references into the first message of its session, before the task text, so retries keep it and the stable part comes first for provider caching. A stage picks its skills and reference files (`skills=`, `refs=`); the default is all of the agent's skills. The text of one call is bounded (`SKILL_CHAR_LIMIT`, 20,000 characters for SKILL.md bodies and 24,000 for references); a reference that does not fit is left out and logged. The JSON format rule and batch sizes are unchanged and the skill text says the format rule wins. Check: Unit, API.
- PLG-4: `agent_calls.skills` (migration 011) holds the skill names, versions, and SHA-256 used. The run's live log gets one `skill` event per call. `prompt_ref` becomes `agent@vN:hash+skills:hash`, where the second hash covers the skill text sent, so a changed skill changes the reference stored with every document version and call. Check: Unit, API.
- PLG-5: Chat agents with skills pick a skill with one small structured model call from names and descriptions, once per user message, and the chosen skill text is added to that turn only. The call counts against the user's tokens (source `chat-skill`). A failed or invalid pick means no skill and a log line, never a failed chat. Check: Unit, API.
- PLG-6: `llm.tool_check(model)` sends one real tool-call round trip through the endpoint: one uniquely named tool whose reply holds a unique token. It passes only if the model called exactly that tool and the final reply holds the token. The result (status, reason, time, `max_tokens` used) is stored on the `models` row (migration 011). The key never appears in the result. Check: Unit.
- PLG-7: Settings model list has **Check tools** beside Test, showing passed, failed, or not checked, with the reason. System health shows loaded skills and tool-check counts. Chat shows a warning when its model failed the check. Check: tsc, API.
- PLG-8: On a model that passed the tool check, chat uses MAF `SkillsProvider` (`FileSkillsSource`, load and resource approvals off, no script runner) filtered to the agent's skills, instead of the pick call. Check: Unit.
- PLG-9: Each plugin skill's `evals/evals.json` joins its agent's eval set and is stored by agent and tagged with the skill. The plugin cases hold `expected_behavior` sentences for a human or grader. Only the part code can really check becomes a `checks` rule (`evals/skills/checks.json`); the rest is listed as "needs grader" and counts as neither pass nor fail until phase 6. Check: API.
- PLG-10: `GET /api/skills` and `GET /api/skills/{name}` are read-only for any signed-in account (rule in `core/auth.py`). The Skills page lists each skill, its agent, description, and references. Check: Unit, tsc.
- PLG-11: `scripts/package_azure.py` puts `skills/` in the backend ZIP. Check: Unit.

## Per-case confidence and gate reopening (CNF)

Design in `docs/PLUGIN_AND_UI_PLAN.md`, "Where we stand" and Part 1 "New accuracy rules", decision 3. Port of the plugin's `confidence.ts` and `agents/confidence-reviewer.md`. The reviewer model scores, and code decides.

- CNF-1: `qe/confidence.py` holds `RUBRIC` (design: `source_proven` 30, `correct_target` 25, `expected_derivable` 25, `fixture_validity` 20; code: `compilable` 30, `assertion_integrity` 30, `import_safety` 20, `traceability_present` 20; plan: `controls_covered` 40, `level_fit` 30, `scenarios_derivable` 30), `THRESHOLD` 70, `ASSERTION_FLOOR` 20 and `verdict_for(total)`: 100 is APPROVED, 70 or above REVISE, below 70 REJECT. Check: Unit.
- CNF-2: `check_item` accepts only whole-number scores inside each dimension's range, refuses an unknown dimension, computes the total as the sum of the scores (a total that differs is a problem and the model's number is ignored), recomputes the verdict, and requires each flaw below 100 to carry `path:line` evidence and a fix. The result carries `effective` (the verdict after checks), `low`, `low_reason`, `problems` and `evidence`. Check: Unit.
- CNF-3: Every citation (the component under test, the test file, each flaw) goes through `safe_path` against the sandbox clone (the worktree for generated tests) and must exist on disk, including its line number. A missing file, a line past the end of the file, a path outside the repository, or a file over 5 MB means `evidence: missing` and an effective REJECT. `verified` means every citation exists; `not-checked` means there is no repository folder to check against (a greenfield design), and is never shown as verified. A design record without a component (file and line) is REJECT. Check: Unit.
- CNF-4: A record is low confidence when its effective verdict is REJECT, its total is under 70, or (generated code) `assertion_integrity` is under 20 at any total. Check: Unit.
- CNF-5: In the QE workflow `confidence-reviewer` scores each design case, each generated test and the plan. Cases go in batches of 8 (`REVIEW_BATCH`) with a typed schema, batches run together within the model limit, and design batches are reviewed as each design batch finishes. Code recomputes every record. A review batch that cannot be parsed marks its cases `NOT RUN` with no score; the stage continues and the roll-up never shows APPROVED while a case is NOT RUN. Check: API.
- CNF-6: A case with an effective REJECT goes back alone to its agent with its flaws and fixes, at most once per stage, and never for REVISE. Only those cases are reviewed again. A case that is still REJECT stays on the gate as REJECT with both rounds recorded. Review and revise calls count against the run's tokens and `RUN_TOKEN_LIMIT`; the gate payload reports the tokens the reviews and revisions used. Check: API.
- CNF-7: `cases_review` and `tests_review` keep their keys. `score` is the average of the code-computed totals, `verdict` follows the worst rule (any REJECT gives REJECT, else any REVISE or NOT RUN gives REVISE, else APPROVED; NOT RUN when nothing was reviewed), and `records` holds one record per case with total, verdict, evidence, low, flaws (file, line, fix). Check: API.
- CNF-8: After execution, a reviewed test that FAILED is capped at 60: its record shows `total` min(total, 60), `capped` true and the total it had. `tests_review_after` holds this summary and is shown at Gate 5. Check: Unit, API.
- CNF-9: Humans decide. `engine.decide` refuses an approval of a gate whose payload holds any REJECT record unless the reason is not empty, and writes the reason with the rejected ids to the ledger (`gate.reject_accepted`). A REVISE can be approved without a reason. No agent or default setting approves. Check: API.
- CNF-10: Editing an approved document reopens its gate and every later gate. `gates.DOC_GATE` maps `discovery` and `requirements` to G1, `test_plan` G2, `test_cases` G3, `test_code` G4 and `release` G5. `documents.save_version` (so also restore, refine and the chat save tool) removes the stored decisions from that gate upward and writes `gate.reopened` for each to the ledger with the cause, document, and the earlier status, signer, time and signature. The API returns `reopened: [gates]`; `GET /api/documents/{id}` returns `would_reopen` so the editor warns before saving. A later gate cannot be approved while an earlier one is open (`GateOrderError`). Creating a first version never reopens. Check: API, Unit.
- CNF-11: `prompts/requirements-analyst.md` states the plugin's observable behavior, code-over-comments and one-actor rules. Code checks that the actor is one of `anonymous`, `customer`, `admin`, `system` (schema, so a bad reply is retried with the error), and drops a code-derived requirement whose quote is a comment line. `prompts/confidence-reviewer.md` has `## Review: design cases`, `## Review: generated tests` and `## Review: plan`. Check: Unit, API.
- CNF-12: `scripts/gen_structure.py` describes every file under `skills/`, so it reports no file without a description. Check: script output.

## Test checks, setup, data, defect records, case limits, execution agent (TST)

Design in `docs/PLUGIN_AND_UI_PLAN.md`, Part 1 and Part 13 "Found in the second review". Failures this reduces, seen on the finance repository: wrong keyword for a real function (22), `httpx.AsyncClient(app=...)` on a new httpx (17), async tests without pytest-asyncio (20), the app's own rate limiter returning 429 (12), imports of packages that are not installed, and tests that need a running server (10).

- TST-1: `qe/emit.py` checks a generated Python test with `ast` only, never running it. It looks at every import. A local module (in the repository root or `src/`) must resolve to a real file or package; each `from x import y` name must exist in that module, following re-exports and star imports of local modules; if a module cannot be known (a `__getattr__`, an unresolvable star import) nothing is reported. A third-party import must be installed in the sandbox Python, or declared in the repository's manifests when dependencies will be installed. Standard library names come from the sandbox Python. Imports inside `try` with an `ImportError` handler are skipped. Check: Unit.
- TST-2: `emit` checks each call to an imported local function, class, or method against its real signature (positional-only, positional, keyword-only, defaults, `*args`, `**kwargs`). It reports too many positional arguments, an unexpected keyword, a missing required argument, and a keyword that repeats a positional one. It stays silent when it cannot know: a decorated function (except known pass-through decorators), a call with `*x` or `**x` for what that hides, a class with no explicit `__init__`, a call inside `pytest.raises` or `assertRaises`. Class and static methods, `Class.method`, and `var = Class(...)` then `var.method(...)` are handled. It also reports `httpx.Client(app=...)` and `httpx.AsyncClient(app=...)` when the installed httpx is 0.28 or newer. Check: Unit, against small real modules.
- TST-3: The sandbox inventory is read by a subprocess of the sandbox Python (argument list, `-I`, 30 second timeout, `clean_env()`) that prints installed distributions, importable names, and the standard library names. If it cannot run, the third-party check is skipped and the stage says so. JavaScript and TypeScript get only a relative import path check (`ponytail:` limit). Check: Unit.
- TST-4: A generated test with findings goes back alone to `test-automation-engineer` with each finding and the real signature, at most one round. The new file replaces the old only if it passes the existing file checks. A test that still has findings stays, marked `unresolved` in `state.emit_unresolved`, in the test document, and at Gate 4. The existing `invalid_test_code` checks are unchanged. Check: API with ScriptedClient.
- TST-5: The generation prompt carries the real signatures of the public functions and classes in the files under test (`emit.signatures`, within `SIGNATURE_BUDGET` characters) and the environment notes of TST-6. Check: API.
- TST-6: `execution.environment_facts` reads, without changing anything: the installed httpx version, whether pytest-asyncio is installed, and rate limiters (slowapi, flask-limiter, fastapi-limiter, django-ratelimit, or an in-repository limiter found by scanning for `Limiter(`, `.limit(`, `RateLimit`, `rate_limit`). `environment_notes` turns that into instructions for the generation prompt: the httpx form that works for that version, async only when it can run, reset or avoid the limiter in a fixture, and no assumption of a running server. Check: Unit.
- TST-7: Stage `prepare` runs after Gate 4 and before `execute`. It installs dependencies when the run was started with the install option (moved from `execute`), installs `pytest-asyncio` into the sandbox when async tests exist and the install option is on, and records `env_facts`, `async_tests`, and `pytest_args`. `pytest_args` holds `-o asyncio_mode=auto` only when pytest-asyncio is importable in the sandbox and async tests exist; it is a command-line option for the generated tests only, so the repository's own config is not edited. Check: Unit, API.
- TST-8: `classify_failure` returns `ENVIRONMENT` for: a missing module, a refused connection (the test needs a running server; starting the app is phase 7), a missing browser, async tests with no plugin, and a 429 where the test did not expect 429 (`assert 429 == 200`, `assert 429 in (200, 201)`). A failure whose first line is an assertion is never `ENVIRONMENT`, except that 429 rule, so text inside an assertion cannot hide a real failure. An unexpected keyword or a wrong argument count is `FIXTURE_DRIFT` (a test problem). Everything else stays `DEFECT`. A class never turns a failure into a pass: `ENVIRONMENT` counts as not passed, coverage is unchanged, and the verdict rules are unchanged (zero executed is INCONCLUSIVE; FAIL stays FAIL). The release summary also reports failures by class. Check: Unit.
- TST-9: Stage `data` (plugin command `qe-data`, skill `generating-test-data`) follows `design` and carries Gate 3. `qe/test_data.py` ports `synthesize-data.ts`: `synthesize_user`, `boundary_payload`, `pagination`, `auth_headers`, and `synthesize(spec)`, with the plugin's shapes, example.com addresses, and no real personal data. `build_fixtures(cases)` masks e-mail addresses, national-ID-like and card-like numbers in case data, picks datasets from each case's type and wording, keeps the shared datasets once and each case's entry short, and is bounded to `FIXTURE_LIMIT` characters. It makes no model call. The result is the `test_data` document, attached to Gate 3, and `tests/agentic_qe/fixtures.json`. Check: Unit, API.
- TST-10: Every failed test gets a record `{test, case_id, classification (defect, test problem, environment), class, evidence, cause, fix, pattern, healed}`. Cause and fix come from `HEALING_PATTERNS` in `qe/execution.py` (a copy of `healing-tests/references/HEALING_PATTERNS.md` plus the evidence signatures above); `defect-diagnostician` may sharpen the text of each, but code fixes the classification. Records are in `state.defect_records` and the `defect_report` document, are shown at Gate 5 with cause and fix, and in the test results view. Check: Unit, API.
- TST-11: Healing repairs selectors and fixtures only. An edit is refused if it removes or changes an assertion, adds a skip, or touches a file outside `tests/`, an application file, or a test file whose failure is not drift. An application defect stays a failing test. Check: API.
- TST-12: `ATLAS_MAX_CASES` (default 40) is a budget applied BEFORE design, so no token is spent on a case that is then cut. `model.case_quota(requirements, limit)` computes, by code and deterministically, an "at most N cases" quota per requirement: P0 and P1 get 4 (the plugin's 1 Positive, 2 Negative, 1 Exception, so `coverage_gaps` stays satisfiable); lower priorities get 2, then 1 each if 2 does not fit, then 1 for as many as still fit in order. If P0 and P1 alone exceed the limit they are still designed and `p0_over_limit` says so. Lower-priority requirements with no budget are left out and named in `state.case_limit` (`left_out_requirements`) and on Gate 3, before any model call. The quota is in each design prompt per requirement. After design, code drops a case beyond its requirement's quota before review and records the ids (`dropped_over_quota`). Gap revision obeys the same quota. `limit_cases` stays as a final safety check that reports what it cuts. Check: Unit, API.
- TST-15: A review batch is sent only the evidence for its own items: the requirements those items cover, their quotes, and the source lines around each citation (`code_pack` on that small file list), at most 12,000 characters per batch in total (`REVIEW_EVIDENCE_CHARS`). The rubric is never cut. Citations are still verified on disk by code whatever the model saw. Check: Unit.
- TST-16: A review batch whose reply cannot be used (after the call's own retries) is split in half and each half is asked once more. A half that fails again gives NOT RUN for its items; NOT RUN stays for what truly failed. The reviewer's `tc_id` is matched to the item key after trimming brackets and case; a record that names the case's own id instead of the key is matched through the id inside the item. Check: Unit.
- TST-17: The run token limit is checked again after a call gets its turn at the model gate, so calls queued behind the concurrency limit stop when an earlier call has pushed the run over. The run then stops with AQE-ALLOW-001 between batches and finished batches stay saved. Calls already in flight can overshoot by their own size. Gates of the QE workflow show a token line `payload.tokens` (`used`, `limit`, `left`) and the same text in the summary. The limit is not raised. Check: Unit, API.
- TST-13: The Gate 3 and Gate 4 payloads carry `estimate`: the tokens this run has really used (from `runs`), the average tokens per recorded call of the agent whose work is next, the number of calls expected, and their product. With no recorded call to average, `estimated_tokens` is null and the reason is given. Nothing is invented. Check: API.
- TST-14: Agent `qa-execution-engineer` (the plugin's eighth, so 12 agents): `agents/qa_execution_engineer.py`, `prompts/qa-execution-engineer.md`, `evals/qa-execution-engineer.json`, skill `executing-tests`. Code still runs the tests. After each run the agent writes a short summary from the evidence (counts, verdict, failures by class). Code checks its stated passed, failed, skipped and verdict, and every "N passed/failed/skipped/tests" in its text, against the JUnit counts. On any mismatch, or if the agent call fails, the summary is refused and code's own summary is used; the result says which. The summary is shown at Gate 5. Check: API.

## Evaluation metrics (EVL)

- EVL-1: `maf/evals/metrics.py` holds deterministic, free metrics, each also a MAF `@evaluator` check: Groundedness (every cited path, line, and quote is checked on disk with `static_analysis.verify_quote`, or against the given context text), Precision, Recall, F1 against a labelled key where items can be matched, and Mutation score. A metric whose denominator is zero has no value (`None`), never 0 or 1. Check: Unit.
- EVL-2: Mutation score plants one labelled bug in a temporary copy of the repository, runs the generated tests with `execution.run_suite`, and counts a mutant killed when a test fails. Zero executed tests gives `INCONCLUSIVE` and no score. A mutant that does not apply to the copy is "not applied", never counted. The real repository is never touched. Check: Unit with real pytest.
- EVL-3: `maf/evals/ragas_evaluator.py` implements MAF's `Evaluator` and imports `ragas` lazily. `requirements-evals.txt` pins it and is not part of `requirements.txt`. Without it every RAGAS metric reads "Not measured: RAGAS is not installed" with no value. The judge model is `ATLAS_EVAL_MODEL`; when unset or equal to the agent's model each score carries `self_graded = true`. A metric that needs something the endpoint lacks (embeddings) is reported "not available" with the reason. Check: Unit, live.
- EVL-4: Case format: `evals/<agent>.json` cases may add `context`, `reference`, `metrics` (a list of names). Which metrics apply to an agent is the table `METRICS_BY_AGENT` (Part 3). A metric that does not apply reports `n/a` with no number. Check: Unit.
- EVL-5: The plugin skill cases that "need a grader" are graded by the judge model on `expected_behavior`. A PASS needs evidence quoted from the output, and code checks the quote is in the output. A missing or unfound quote is FAIL. Without a judge model they stay "needs grader". Check: Unit.
- EVL-6: Table `evaluation_metrics` (migration 012) stores per metric: value, n, judge model, self-graded flag, label state (`reviewed`), tokens, case detail, prompt version, and the eval run id. History and trend are by prompt version. Check: Unit.
- EVL-7: Groundedness is recorded for every real `AgentCall` reply that cites files, free of tokens, with source `live`, per agent call. Check: Unit.
- EVL-8: Benchmarks `evals/benchmarks/shop/` (planted bugs, clean files, labelled requirements, failures, questions) and `evals/benchmarks/finance/labels.json` (pinned commit). Every label set has `"reviewed": false` until the owner changes it; cards show "labels not yet reviewed" while false. Check: Unit.
- EVL-9: Agents cards show tiles Groundedness, Faithfulness, Recall, F1: "Not measured" until run, "n/a" where it does not apply. The agent page shows all metrics, trend per prompt version, each case with question, context, answer, reason (worst first), and the spread over repeated runs. The Prompts page shows scores for a version beside the active one. Check: type check; browser by the owner.
- EVL-10: Eval runs have no user: they are started by an admin and never count against another account's limit (MDL-4). Skill evals started by a user will count against that user when that exists. Check: Unit.
