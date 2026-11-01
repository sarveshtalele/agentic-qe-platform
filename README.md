# Agentic QE Platform

A governed workspace for BAs and developers, built on Microsoft Agent Framework. Turn briefs into templated requirements and Gherkin, scan real repositories, build features and fixes on isolated branches, run the full test lifecycle with human gates, and chat with project-aware agents.

## Requirements

Python 3.12+, Node.js 20+, and Git, on Windows, macOS, or Linux.

## Setup

```bash
python scripts/dev.py setup
```

Add your model to `.env`, or use the Settings page. Any OpenAI-compatible endpoint works.

## Run

Double-click `start-windows.bat` on Windows, or `start-mac.command` on macOS. The first run installs everything, then the app opens in your browser. Press Ctrl+C in that window to stop it. If macOS blocks the file, right-click it and choose **Open**.

You can run the same thing from a terminal:

```bash
python scripts/dev.py up
```

For development with live reload:

In two terminals:

```bash
python scripts/dev.py backend
```

```bash
python scripts/dev.py frontend
```

Open http://127.0.0.1:3000. For a production build of the UI, use `python scripts/dev.py start`.

## Test

```bash
python scripts/dev.py test
```

```bash
python scripts/dev.py e2e
```

The E2E suite uses the real model and network on ports 8010 and 3010, and saves screenshots to `docs/evidence`.

## Deploy

```bash
python scripts/package_azure.py
```

This makes separate backend and frontend ZIPs in `dist/`. `docs/AZURE_DEPLOY.md` has the portal steps. Add `--repo` for a clean copy with no legacy code in `dist/agentic-qe-platform`.

## Documents

| File | Contents |
|---|---|
| `docs/SYSTEM_DESIGN.md` | End-to-end design and how to add agents, tools, and workflows |
| `docs/AZURE_DEPLOY.md` | Deploy to Azure with the portal and ZIPs, with costs in INR |
| `docs/ARCHITECTURE.md` | Plugin mapping and workflow details |
| `maf-guide.md` | MAF features used, by file |
| `plan.md`, `specs.md`, `tasks.md` | Audit, requirements, status |
| `Design.md` | UI design |
| `CLAUDE.md` | Project rules and guardrails |
| `progress.md` | Timestamped activity log |
| `legacy/` | Previous code, unchanged |

## Security limits

Agentic QE Platform is a single-user app that binds to loopback, with no login. Do not expose it to a network without adding authentication. Generated and repository tests run on your machine with a scrubbed environment after you approve Gate 4; there is no OS sandbox.
