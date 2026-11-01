# Agentic QE Platform

A governed workspace for business analysts and developers, built on Microsoft Agent Framework (MAF) in Python with a Next.js UI. It turns briefs into templated requirements and Gherkin, reviews complete repositories for bugs, builds features and fixes on separate branches, and runs a full test lifecycle with a named person approving each stage.

## Features

| Area | What it does |
|---|---|
| Projects | One page per project, with search, rename, archive, and delete. Every tile and card opens its tab |
| Repository and sandbox | Git, private GitHub, ZIP, or local folder. Each project gets a sandbox with a full clone, a branch per run, and its own Python environment |
| BA Studio | Requirements from built-in or uploaded templates, with an independent review and validated Gherkin |
| Documents | Formatted pages edited in place, with table grids and images. Immutable versions, diffs, restore, and downloads as `.md`, `.docx`, `.feature`, and `.csv` |
| Bug Scan | Static scanners and an agent review of every source file, with coverage reported. Findings must quote real code. Fix one or Fix all |
| Feature Builder | Changes on a branch, checked against a test baseline. You review the diff and verdict before commit |
| QE Studio | Requirements, plan, design, generated tests, execution, healing, and traceability, through gates G0 to G5, shown live |
| Copilot | AG-UI and CopilotKit chat with saved threads, project memory, and selectable agents |
| Agents | 13 agents with tool policy, kill switch, token limits, guardrails, and evaluations |
| Observability | Skills, agents, tools, workflow steps, approvals, guardrails, and the audit ledger, by run, project, or all projects |
| Documentation | A built-in docs site at `/docs`, with search |

## Quick start

You need Python 3.12+, Node.js 20+, Git, and an OpenAI-compatible model endpoint.

Double-click `start-windows.bat` on Windows or `start-mac.command` on macOS. The first run installs everything, then the app opens in your browser. Press Ctrl+C in that window to stop it. If macOS blocks the file, right-click it and choose **Open**.

From a terminal, the same thing is:

```bash
python scripts/dev.py up
```

Then open **Settings**, enter the model details, and choose **Test connection**. You can put them in `.env` instead.

### Development with live reload

Run these in two terminals:

```bash
python scripts/dev.py backend
```

```bash
python scripts/dev.py frontend
```

## Architecture

```mermaid
flowchart LR
  B[Browser] --> N[Next.js UI]
  N -->|/api proxy| A[FastAPI routers]
  N -->|CopilotKit, AG-UI| G[AG-UI endpoint]
  A --> E[Run engine on MAF workflows]
  E --> W[Workflows: ba, bug_scan, change, qe]
  W --> R[Agent runtime]
  G --> R
  R --> M[OpenAI-compatible model]
  W --> C[Code checks: quotes, Gherkin, validators, real tests]
  W --> S[(Project sandbox)]
  A --> D[(SQLite, ledger, documents)]
```

Each agent, tool, workflow, and API area has its own file. To add an agent or workflow, add a file. See `docs/SYSTEM_DESIGN.md`.

## Project layout

| Path | Holds |
|---|---|
| `src/backend/api` | REST routers, one file per area |
| `src/backend/maf/agents` | One file per agent, holding its policy |
| `src/backend/maf/tools` | One file per tool |
| `src/backend/maf/workflows` | One file per workflow |
| `src/backend/maf` | Agent runtime, engine, governance, observability, evals, AG-UI, model client |
| `src/backend/core` | Documents, gates, ledger, prompts, security |
| `src/backend/repos` | Git, GitHub, ingest, sandbox, scan, static analysis |
| `src/backend/qe` | Validators, runners, traceability |
| `src/frontend` | Next.js pages, components, and documentation content |
| `prompts`, `evals`, `templates` | Agent prompts, agent eval cases, document templates |
| `tests` | Unit, integration, and Playwright tests |
| `deploy/azure`, `scripts` | App Service startup, launcher, packaging, hooks |
| `docs` | Design, Azure guide, file map, test screenshots |
| `legacy` | Earlier code, kept until the owner removes it |

`docs/PROJECT_STRUCTURE.md` lists every file, what it does, and what uses it. It is generated from the real imports by `python scripts/gen_structure.py`.

## Test

These run offline with real FastAPI, SQLite, Git, and pytest, and a scripted stand-in for the model:

```bash
python scripts/dev.py test
```

These use the real model, real repositories, and a real browser on ports 8010 and 3010, and save screenshots to `docs/evidence`:

```bash
python scripts/dev.py e2e
```

`tests/e2e/test_finance_repo.py` runs every feature on [personal-finance-mcp](https://github.com/sarveshtalele/personal-finance-mcp) by adding a new MCP tool. CI runs the offline tests on Windows, macOS, and Linux.

## Deploy to Azure

```bash
python scripts/package_azure.py
```

This makes separate backend and frontend ZIPs in `dist/`. With `--repo`, it also makes a clean copy with no legacy code in `dist/agentic-qe-platform`. `docs/AZURE_DEPLOY.md` has the portal steps and costs: about ₹1,182 a month on one Basic B1 Linux plan in East US, at retail prices checked on 1 November 2026.

## Documents

| File | Contents |
|---|---|
| `docs/SYSTEM_DESIGN.md` | End-to-end design, and how to add agents, tools, and workflows |
| `docs/PROJECT_STRUCTURE.md` | Every file, its purpose, and how it connects |
| `docs/AZURE_DEPLOY.md` | Azure deployment with the portal and ZIPs |
| `docs/ARCHITECTURE.md` | Plugin mapping and workflow details |
| `maf-guide.md` | MAF features used, by file |
| `plan.md`, `specs.md`, `tasks.md` | Decisions, requirements, status |
| `Design.md` | UI design rules |
| `CLAUDE.md` | Rules for changing this project |
| `progress.md` | Timestamped activity log |

## Security limits

- The app is single-user and has no login. Locally it binds to loopback. On Azure, use App Service Authentication and an access restriction, as the guide describes.
- A project sandbox isolates by folder and environment, and is not an operating system container. Tick **Install repository dependencies** only for repositories you trust, because that runs their install scripts.
- Keys are encrypted at rest and redacted from logs. Keep `data/` private.
