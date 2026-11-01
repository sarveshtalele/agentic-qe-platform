# Agentic QE Platform end-to-end system design

Agentic QE Platform is a single-user workspace on Microsoft Agent Framework (MAF). `docs/ARCHITECTURE.md` maps each plugin command to its code. This document explains how the whole system fits together and how to extend it. `docs/AZURE_DEPLOY.md` covers deployment.

## System context

```mermaid
flowchart LR
  U[BA or developer] --> UI[Next.js UI]
  UI -->|/api proxy| API[FastAPI]
  UI -->|CopilotKit route, AG-UI| API
  API --> LLM[OpenAI-compatible model]
  API --> GH[GitHub and Git hosts]
  API --> DISK[(SQLite, repos, worktrees, checkpoints)]
  API --> RUN[Git, ruff, pytest, vitest, jest, Playwright]
```

## Code layout

Dependencies point one way: `api` calls `maf`, `maf` calls `core`, `repos`, and `qe`. Those three never call upward.

```text
src/backend/
  app.py                 App creation, security middleware, router includes
  config.py, db.py       Settings, SQLite, migrations
  api/                   REST routers
    projects, repository, documents, templates, runs, findings, governance, settings, chat
  maf/
    agents/              One file per agent, holding its policy. Scanned into POLICIES
    tools/               One file per tool, assembled into project-scoped sets
    workflows/           ba, bug_scan, change, qe, plus shared.py and edits.py. Scanned into REGISTRY
    runtime.py           AgentCall, build, ProjectContext, model call limit, JSON repair
    engine.py            MAF WorkflowBuilder wrapper: stages, gates, checkpoints, events
    governance.py        Tool policy, kill switch, guardrails, telemetry
    evals.py, agui.py, llm.py
  core/                  Documents, gates, ledger, prompts, security, Gherkin, files
  repos/                 Git, GitHub, ingest, scan, static analysis
  qe/                    Plan and case validators, runners, traceability
prompts/  evals/  templates/   Versioned text, one file per agent or template
src/frontend/            Next.js UI and the CopilotKit runtime route
deploy/azure/            App Service startup scripts
```

## How to extend it

| To add | Do this | Nothing else changes |
|---|---|---|
| An agent | Add `maf/agents/<key>.py` with a `POLICY`, `prompts/<key>.md`, and `evals/<key>.json` | It appears in the registry, the Agents page, and evals |
| A tool | Add `maf/tools/<name>.py` with `build()`, list it in `tools/__init__.py`, and allow it in the agent's policy | Denied to every other agent by default |
| A workflow | Add `maf/workflows/<name>.py` that ends with `REGISTRY["<name>"] = definition`. Import only the agents and tools it needs | Other workflow files stay untouched |
| An API area | Add `api/<name>.py` with a `router`, and list it in `api/__init__.py` | |

## Core flows

### A workflow with a human gate

```mermaid
sequenceDiagram
  participant U as Person
  participant A as API
  participant E as Engine
  participant W as Workflow stage
  participant M as Model
  U->>A: POST /projects/{id}/runs
  A->>E: start
  E->>W: run stage
  W->>M: agent call through guardrails
  M-->>W: reply
  W->>W: code checks the reply
  W-->>U: event stream shows progress
  W->>E: request_info at the gate
  E->>E: checkpoint saved, run waits
  U->>A: approve, with a name
  A->>E: decide, ledger entry
  E->>W: resume from checkpoint
```

### A code change

1. **Prepare.** Create a branch in its own worktree, and run the tests for a baseline.
2. **Implement.** Send the selected code in the message. The agent replies with structured edits and has no tools.
3. **Guard.** `guarded_apply` refuses path escapes, secrets, overwrites, deletions, stray files, and out-of-scope edits. Refusals and current files go back for another round.
4. **Verify.** Run the real tests. Only new failures count. Up to two retries get the failing test files first.
5. **Review.** A person sees the verdict, the diff, and any existing assertion the change altered. Nothing is committed until they approve.

### Chat

The browser uses CopilotKit hooks, which call the runtime route, which calls `/agui/agent`. That route runs a MAF agent with the project's tools and streams AG-UI events. Threads and memories are stored per project, and any agent with a chat policy can be selected.

## Why agents edit without tools

Agent loops with tools were measured on `personal-finance-mcp` and failed badly on this model endpoint, which loses older tool results. The agent reread files, drifted to other work, and used 170,000 to 955,000 tokens without finishing. Sending code in the message and applying structured edits finished the same task at about 86,000 tokens, with the real suite passing at 148 tests.

## Harness patterns

Source: [Harness Patterns](https://ashishpatel26.github.io/agent-harness-engineering-pattern/). `plan.md` lists the ones chosen and skipped.

| Harness concern | Pattern | Agentic QE Platform |
|---|---|---|
| Loop limits | Agent loop guards | Tool round limits, token limit per call, token budget per run |
| Model layer | Retry, timeout, structured output, cut-off guard | SDK retry, `ATLAS_MODEL_TIMEOUT`, `AgentCall.typed`, cut-off replies are never parsed |
| Load | Backpressure, bulkhead | `ATLAS_MODEL_CONCURRENCY` limits model calls for the process |
| Tools | Registry, proxy, deny by default | `tools/`, `governance.allowed`, `tool_audit` |
| Safety | Guard chain, append-only history | `guard_text`, hash-chained ledger, immutable versions |
| Durability | Checkpoint and resume | MAF `FileCheckpointStorage` |
| Testing | Scripted stand-in, evals | `tests/scripted_client.py`, `evals/*.json` |

## Trust boundaries

| Boundary | Rule | Enforced by |
|---|---|---|
| Model output | Never trusted alone | Validators, quote checks, Gherkin parser, real test runs |
| Repository and document text | Untrusted data | `neutralize`, `redact`, agents read it as data |
| Agent edits | Confined to a branch | `safe_path`, `guarded_apply` |
| Test code | Cannot see platform secrets | `clean_env` |
| Approvals | Named person only | `gates`, `decide` |
| Network | Loopback locally. Sign-in and IP restriction on Azure | Host and origin guard, App Service |

## Failure handling

| Failure | Behavior |
|---|---|
| Model hangs | The call fails after `ATLAS_MODEL_TIMEOUT` and one retry. The run fails with a clear error |
| Reply cut off | Asked again for a shorter answer. Three failures fail the run |
| Provider content filter | The error names the block, and text is neutralized before sending |
| Run over budget | Stops at `ATLAS_RUN_TOKEN_LIMIT` |
| Server restart | Waiting runs resume from checkpoints. Running ones are marked interrupted |
| No tests ran | The verdict is `INCONCLUSIVE`, never `PASS` |

## Accounts and access

Every API and chat path passes `session_guard` in `app.py`, which denies by default. `core/auth.py` holds the rules: an unknown session gets 401, another owner's item gets 404, and admin areas get 403. Runs and chats use the project owner's model, token allocation, and active dates, so background work is limited the same way as page requests. Passwords are salted scrypt hashes, usernames are encrypted, and sessions are stored only as hashes. Every log line passes through `redact()`.

## Accuracy controls

| Stage | Checks by code | Independent review |
|---|---|---|
| Discovery | Required sections, every cited path exists, every source folder covered | Before the requirements gate, with one automatic revision |
| Requirements | Each quote must exist in the file | Before Gate 1, with one automatic revision |
| Test plan | Plan score and coverage | Before Gate 2, with one automatic revision |
| Test design | Case mix per requirement, duplicates | Per batch, in parallel, before Gate 3 |
| Generated tests | Imports exist, syntax, no placeholders, one case per file | Before Gate 4 |
| Code change | Baseline comparison, named functions present, assertions flagged | In parallel with the tests, before review |
| Bug scan | Each quote must exist in the file | Once, on the verified findings |

A review that cannot run shows as **not run**, never as a score.

## Deployment

```mermaid
flowchart TB
  U[Signed-in user] -->|HTTPS, Microsoft sign-in| F
  subgraph P[App Service plan: Basic B1 Linux]
    F[Frontend app: Node, Next.js standalone]
    B[Backend app: Python, uvicorn, 1 worker]
  end
  F -->|Only allowed caller, by IP| B
  B --> H[(/home share: SQLite, repos, checkpoints, secret key)]
  B --> M[Model endpoint]
  B --> G[Git hosts]
```

On each start, the startup scripts compare a stamp, rebuild only what changed, and then serve. `docs/AZURE_SYSTEM_DESIGN.md` has the multi-user target design.
