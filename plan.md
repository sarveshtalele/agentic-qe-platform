# Plan

Modify the existing project into a production-ready app for BAs and developers, on branch `feat/real-maf-platform`. Nothing is deleted without the owner's permission. The previous code stays in Git history at commit 09f14fe. The `legacy/` folder was removed in commit f1a7070.

## Audit of the previous code

| Problem | Evidence (paths at commit 09f14fe) | Resolution |
|---|---|---|
| "MAF" was hand-written, and the real package was not installed | `src/backend/maf/core.py`, `requirements.txt` | Real `agent-framework` packages |
| Engine had a dead code path calling a missing method | `maf/core.py` `step` calls `should_route` | Replaced by MAF workflows |
| Simulated PRs, tokens, and connection success | `github/client.py`, `routes_agentic_qe.py` (`ghp_simulated`, `simulated: True`, latency 34/68/82) | Real calls only |
| Tautological tests reported as verified | `routes_agentic_qe.py` copilot `/test`, `qe/scanner.py` `assert True` | Refused by checks |
| Canned requirements when none exist | `maf/agents/qe.py` `_create_strategy` | Error instead |
| Findings with hardcoded sample code | `qe/scanner.py` | Ruff and quote-verified review |
| Hardcoded proxy URL, model, and default repo | `llm/client.py`, `app/page.tsx` | Settings and environment |
| Token placed in clone URL and plaintext settings | `routes_agentic_qe.py`, `data/settings.json` | Encrypted, env-scoped header |
| Project picked from a header dropdown; one 1021-line page | `components/Header.tsx`, `app/page.tsx` | Projects page and routes |
| Bash and PowerShell scripts in parallel | `scripts/` | `scripts/dev.py` |

## Feature parity with the previous app

| Previous feature | New location | Status |
|---|---|---|
| Repository Hub: token, URL, `owner/repo`, local path | Repository page, Settings | Ported |
| BA Studio: BRD and PRD, review, refine, Gherkin, versions, exports | BA Studio, document page | Ported |
| Feature Builder and error chat, PR, merge, ZIP | Feature Builder, Bug Scan, run panel | Ported |
| Bug Diagnostic with fixes | Bug Scan | Ported |
| QE Test Studio | QE Studio | Ported |
| HITL Governance with manual decisions | Governance | Ported |
| Observability and agent evaluations | Runs & Metrics, Prompts | Ported; numbers now come from real runs |
| Copilot with `/scan`, `/fix`, `/test`, `/verify`, `/gates` | Copilot | Ported as agent tools |
| XLSX and PPTX source upload | BA Studio | Ported |

## Phases

| # | Phase | Result |
|---|---|---|
| 1 | Review code, plugin, and MAF docs | Audit above, `docs/ARCHITECTURE.md` |
| 2 | Guardrails and tracking | `CLAUDE.md`, `.claude/settings.json`, `progress.md` |
| 3 | Backend on real MAF | `src/backend` |
| 4 | Parity and plugin rule alignment | Table above |
| 5 | UI: projects page first | `src/frontend`, `Design.md` |
| 6 | Chatbot on AG-UI and CopilotKit | `/agui`, `components/Chat.tsx` |
| 7 | Tests and evidence | `tests/`, `docs/evidence/` |
| 8 | Final guide | `maf-guide.md`, `README.md` |
| 9 | Agent governance: policy, guardrails, evals, observability | `maf/governance.py`, `maf/evals.py`, `/agents` |
| 10 | Sign-in, per-user allocations, confidence review beside each stage | `core/auth.py`, `api/auth.py`, `core/doc_checks.py`, `/login`, `/users` |
| 11 | Roadmap: Skill Studio, repository-aware changes, application builder, chatbot, new UI | `docs/PLUGIN_AND_UI_PLAN.md`. Approved, not built |
| 15 | Delivery phase 6: deterministic metrics, RAGAS evaluator, benchmarks, stored scores, score cards | `maf/evals/`, `evals/benchmarks/`, `docs/EVALUATIONS.md` | Built |
| 14 | Delivery phase 5: per-case confidence, code-computed verdicts, gate reopening, signature checks, setup and data stages, defect records, case budget, `qa-execution-engineer` | `qe/confidence.py`, `qe/emit.py`, `qe/test_data.py` | Built |
| 13 | Delivery phase 4: plugin skills injected into workflows, chat skill selection, and a live tool check per model | `skills/`, `core/skills.py`, `maf/skill_chat.py`, `llm.tool_check` | Built |
| 12 | Delivery phases 1 to 3 of `docs/PLUGIN_AND_UI_PLAN.md`: names and integrity, typed errors and logs, models, limits, and roles | `core/models.py`, `core/errors.py`, `core/logs.py`, `core/auth.py`, `api/settings.py`, `maf/engine.py`. Built. Phase 4, Skills, is next |

Latest results, after phase 6: offline 447 passed, end-to-end 32 of 33 passed (`test_f4` failed, as Feature Builder ended with a failing verdict), agent evaluations 33 of 33 passed. The finance repository QE run executed 56 tests, 14 passed and 42 failed, coverage 53%, verdict FAIL, 446,876 tokens. Results vary widely between runs.

## How MAF is used

See `maf-guide.md`. In short: `Agent` for specialists, structured edits applied by guarded code for feature and fix work, `WorkflowBuilder` with `request_info` and checkpoints for gates, fan-out and fan-in for scans, context providers for memory, middleware for tool audit, `AgentFrameworkAgent` for AG-UI, and `evaluate_agent` for prompt quality.

## Documentation sources

The MAF PDF and the installed package source are primary. Context7 and Firecrawl supplied CopilotKit and AG-UI setup details. `.mcp.json` registers both for future sessions. `npx rea-agents setup` was run for Claude Code. REA reverse engineers compiled apps, so this source-based project did not need it.

## Decisions needing the owner

| Item | Default until told otherwise |
|---|---|
| Commit and push | Not done |
| Old `data/sdlc.sqlite3` and `workspaces/` | Left untouched and not migrated |

## Modular architecture (owner request, 2026-11-01)

The backend grew two large files: `app.py` (833 lines) and `maf/workflows.py` (790 lines). Both split along feature lines. Public imports stay the same so callers and tests do not change.

```text
src/backend/
  app.py                 App creation, middleware, router includes only
  api/                   One router per area: projects, repositories, documents, runs, chat, governance, settings
  maf/
    agents/              runtime.py (AgentCall, build) and one file per agent holding its policy
    tools/               One file per tool, assembled by repo_tools, document_tools, chat_tools
    workflows/           shared.py, edits.py, then ba.py, bug_scan.py, change.py, qe.py. Adding a workflow means adding a file
    engine.py, governance.py, evals.py, agui.py, llm.py
```

### Harness patterns chosen

Source: Harness Patterns (ashishpatel26.github.io/agent-harness-engineering-pattern), 192 patterns. Most are general catalog entries, so only the ones that fix a real gap here are adopted.

| Pattern | Status | Where |
|---|---|---|
| Layered architecture, Registry (8.04, 2.06) | Adopting | Router, workflow, agent, and tool files with registries |
| Plugin discovery (2.07) | Adopting | Agent files found by scanning the package |
| Backpressure and Bulkhead (3.10, 7.05) | Adopting | A process-wide limit on concurrent model calls, needed on a one-core plan |
| Cut-off reply guard (1.01) | Adopting | A reply stopped by the token limit is reported as cut off |
| Retry with backoff (3.04) | Have | OpenAI SDK retry plus `ATLAS_MODEL_TIMEOUT` |
| Structured output with repair (3.16) | Have | `AgentCall.typed` |
| Middleware, Proxy (1.05, 2.14) | Have | `governance.telemetry`, `tool_audit`, `governance.allowed` |
| Append-only log, Immutable records (7.09, 4.13) | Have | `core/ledger.py`, document versions |
| Checkpoint and resume (1.07) | Have | `FileCheckpointStorage` in `engine.py` |
| Health check (7.08) | Have | `/api/health`, wired to App Service Health check |
| One-door gateway (8.11) | Have | `session_guard` denies every API path by default, and Azure adds an access restriction on the backend |
| Scripted stand-in tests (12.04) | Have | `tests/scripted_client.py` |

Skipped: circuit breaker, fallback chain, semantic cache, sharding, CQRS, tenant rate limits, durable execution engines, and CodeAct. Agentic QE Platform runs on one instance with one model, and sandboxes do not isolate untrusted users yet, so none of these fixes a problem it has. Add them when it serves several tenants or models.

### Azure target

Two Linux web apps on one B1 plan in East US: ₹1.6189 per hour, ₹1,181.80 per 730-hour month, from the Azure Retail Prices API on 2026-11-01. It is the cheapest region checked and the closest to the current model endpoint. Central India is ₹1,251.29. Free F1 costs ₹0 but allows 60 CPU minutes a day and has no Always On, so workflows would die. Microsoft documents that the Kudu ZIP drag-and-drop page does not work on Linux, so the guide uses Cloud Shell upload, with Kudu file upload as the alternative. SQLite on the `/home` network share cannot use WAL, so the journal mode becomes a setting.

## Observability design (owner request, 2026-11-01)

The page reads existing stores, with one new table.

| Log type | Source |
|---|---|
| Skill | `run_events` stage starts, mapped to the agentic-qe skill each stage implements |
| Agent | `agent_calls` |
| Tool, MCP tool | New `tool_calls` table, written by `tool_audit` for workflows and chat |
| Workflow step, approval | `run_events` |
| Guardrail | `guardrail_events` |
| Audit | Hash-chained `ledger` |

Agentic QE Platform connects to no MCP server, so the MCP count is zero and the page says that. The `kind` column is there for when one is added.
