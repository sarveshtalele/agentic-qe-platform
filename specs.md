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
