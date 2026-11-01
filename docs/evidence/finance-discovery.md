## Purpose and Users
Personal Finance MCP is a deterministic personal‑finance toolkit exposed over the **Model Context Protocol**. It provides 77 calculators covering TVM, debt, planning, bonds, stocks, mutual funds, portfolio analytics, derivatives, Indian small savings, cash flow, risk profiling, and live market data, plus a `create_financial_plan` orchestrator. Users interact with it as an MCP server (via Claude Desktop, Claude Code, Cursor), a website (Next.js UI with a live calculator and dashboard), or a hosted connector on Hugging Face. It is stateless, requires no API keys for market data, and is designed for educational use.

## How It Runs End to End
The system runs as a unified ASGI server on a single port (default 7860) serving three surfaces: `/mcp` (streamable‑HTTP MCP), `/api/*` (JSON endpoints for calculators and live data), and `/` (exported Next.js static site).

1. **Entry point** – `src/web/__main__.py` calls `main()` from `src/web/server.py`.
2. **Server startup** – `src/web/server.py` defines `build_app()` which:
   - Calls `mcp.streamable_http_app()` (from `src/server.py` via `FastMCP`) to get a Starlette app with the `/mcp` route.
   - Adds `CORSMiddleware` and `SecurityMiddleware` (ASGI layer for headers, body cap, rate limiting).
   - Prepends API routes: `/api/health`, `/api/tools`, `/api/calc` (POST), `/api/nav`, `/api/fx`, `/api/quote`.
   - Mounts the static Next.js export from `web/out/` at `/`.
3. **MCP tool registration** – `src/server.py` initialises `FastMCP` and calls each tool module’s `register(mcp)` function (e.g. `tvm.register(mcp)`, `debt.register(mcp)`, …). Each register decorates a pure function with `@mcp.tool`.
4. **API calculator calls** – `/api/calc` receives a `calculator` name (mapped in `CALCULATORS` dict) and `params`. Params are sanitised/bounded by `_sanitize_params()`, then the pure function is called via `fn(**allowed)`.
5. **Static site** – Next.js app in `web/` is built with `npm run build` (output: `export`) and served by Starlette’s `StaticFiles`. Pages include home, calculator, tool catalog, dashboard, and connect/setup guide.
6. **Docker production** – `Dockerfile` multi‑stage: builds the Next.js site (stage 1), then copies it into a Python stage running `python -m src.web`. No database; no background workers.

## Architecture
```
┌──────────────────────────────────────────────────────────┐
│  ASGI (Starlette) – src/web/server.py                    │
│  Port 7860                                               │
│                                                          │
│  ┌────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │  /mcp       │  │  /api/*          │  │  /           │ │
│  │  (FastMCP)  │  │  health, tools,  │  │  Next.js     │ │
│  │  streamable │  │  calc, nav, fx,  │  │  static      │ │
│  │  HTTP       │  │  quote           │  │  export      │ │
│  └──────┬──────┘  └────────┬─────────┘  └──────────────┘ │
│         │                  │                              │
│         └──────────┬───────┘                              │
│                    │                                      │
│         SecurityMiddleware (headers, body cap, rate lim)  │
│         CORSMiddleware                                    │
└────────────────────┼──────────────────────────────────────┘
                     │
     ┌───────────────┴───────────────┐
     │  src/server.py                │
     │  FastMCP instance             │
     │  + 13 register() calls        │
     └───────────────┬───────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
┌────▼────┐   ┌─────▼─────┐   ┌────▼────┐
│ tools/  │   │ models/   │   │ utils/  │
│ pure fns│   │ schemas   │   │ format- │
│ + @tool │   │ + enums   │   │ ters    │
└─────────┘   └───────────┘   └─────────┘
```

## Modules
| Path | Responsibility | Depends On |
| :--- | :--- | :--- |
| `run_production.py` | Production runner for SSE transport (standalone) | `src.server` |
| `src/__main__.py` | Entry: `python -m src` (stdio MCP) | `src.server` |
| `src/server.py` | FastMCP server, registers all tool modules, main() for stdio | `mcp`, all `src.tools.*` |
| `src/tools/tvm.py` | 10 TVM calculators (FV, PV, annuity, perpetuity, EAR, etc.) | `mcp`, `utils.formatters` |
| `src/tools/debt.py` | 6 debt calculators (EMI, amortisation, prepayment, consolidation, invest‑vs‑prepay) | `mcp`, `utils.formatters` |
| `src/tools/planning.py` | 9 financial‑planning tools (net worth, ratios, emergency fund, budget, goals, retirement, education, insurance, health score) | `mcp`, `tvm`, `utils.formatters` |
| `src/tools/bonds.py` | 6 fixed‑income tools (bond price, YTM, duration, convexity, zero‑coupon) | `mcp`, `utils.formatters` |
| `src/tools/stocks.py` | 5 equity‑valuation tools (DDM, multi‑stage DDM, P/E, DCF, dividend yield) | `mcp`, `utils.formatters` |
| `src/tools/mutual_funds.py` | 7 MF calculators (SIP, lumpsum/vs SIP, CAGR, NAV, expense impact, SWP) | `mcp`, `utils.formatters` |
| `src/tools/portfolio.py` | 11 portfolio tools (expected return, risk, 2‑asset, CAPM, Sharpe, Treynor, alpha, info ratio, Sortino, allocation) | `mcp`, `utils.formatters` |
| `src/tools/derivatives.py` | 5 derivatives tools (futures fair value, option payoff, parity, Black‑Scholes, beta hedge) | `mcp`, `utils.formatters` |
| `src/tools/india_savings.py` | 9 Indian small‑savings tools (PPF, SSY, NSC, KVP, SCSS, RD, FD, EPF, gratuity) | `mcp`, `utils.formatters` |
| `src/tools/cashflow.py` | 3 cash‑flow tools (statement, DTI, contingency fund) | `mcp`, `utils.formatters` |
| `src/tools/risk_profile.py` | 1 risk‑profile scoring tool | `mcp`, `utils.formatters` |
| `src/tools/advisor.py` | Meta‑orchestrator `create_financial_plan` | `mcp`, `utils.formatters` |
| `src/tools/marketdata.py` | 4 live‑data tools (MF search, NAV, FX rate, equity quote) | `mcp`, `httpx`, `utils.formatters` |
| `src/models/schemas.py` | Pydantic models for calculator inputs (16 classes) | `pydantic`, `enums` |
| `src/models/enums.py` | Enums: CompoundingFrequency, AnnuityType, LoanType, RiskProfile, BondType, ReturnMethod | none |
| `src/utils/formatters.py` | Output formatters (currency, percentage, tables, tool responses) | none |
| `src/web/__main__.py` | Entry: `python -m src.web` (uvicorn, port 7860) | `src.web.server` |
| `src/web/server.py` | Unified ASGI server: routes, security middleware, API handlers, calculator registry | `starlette`, `mcp`, `tools.*` |
| `web/` (Next.js app) | Front‑end: home, calculator, tools catalog, dashboard, connect page | React, Next.js |

## Interfaces
**MCP (Model Context Protocol)**
- 77 registered tools exposed over streamable‑HTTP at `/mcp` and stdio on `python -m src`.
- Tools documented in `src/server.py` `instructions` string – the LLM is instructed to route intent to tools, never invent numbers, and recompute on input change.

**REST API** (6 endpoints, all served by `src/web/server.py`):
- `GET /api/health` – returns `{"status": "ok", "tools": <count>}`.
- `GET /api/tools` – returns full tool list with category and description.
- `POST /api/calc` – runs a named calculator from the `CALCULATORS` registry with validated/bounded params.
- `GET /api/nav?code=<int>&q=<str>` – mutual‑fund NAV lookup by code or search by name.
- `GET /api/fx?base=USD&symbols=INR` – foreign‑exchange rate from ECB data.
- `GET /api/quote?symbol=^NSEI` – stock/index quote from Yahoo.

**Web UI**
- Exported Next.js static site at `/`: home (`/`), live calculator (`/calculator`), tool catalog (`/tools`), market dashboard (`/dashboard`), connection guide (`/connect`).

**CLI / Script Entry**
- `python -m src` – starts stdio MCP server.
- `python -m src.web` – starts unified HTTP server.
- `python run_production.py` – starts SSE transport server (standalone).
- Installed CLI entry: `personal-finance-mcp` (calls `src.server:main`).

## Data and Integrations
**No local database** – the system is fully stateless and stores nothing on disk across requests.

**External integrations (all public, keyless):**
- **Mutual fund NAV** – AMFI data, functions `search_mutual_funds()` and `get_mf_nav()` in `src/tools/marketdata.py`.
- **Foreign exchange** – ECB (Frankfurter API), function `get_fx_rate()` in `src/tools/marketdata.py`.
- **Equity quotes** – Yahoo Finance, function `get_quote()` in `src/tools/marketdata.py`.

**Failure behaviour:** API handlers catch `ValueError`, `ZeroDivisionError`, `KeyError`, `TypeError` and return `400` with an actionable message. Catch-all `Exception` returns `400` with `"calculation failed"` without leaking stack traces. Rate‑limit violations return `429`. Body‑size violations return `413`. Network failures in live‑data tools propagate as exceptions (no fallback data is cached).

## Configuration and Deployment
**Environment variables:**
- `PORT` – HTTP server port (default `7860`), used by `src/web/server.py` and `Dockerfile` (`ENV PORT=7860`).
- `MCP_HOST` / `MCP_PORT` – for `run_production.py` (defaults `127.0.0.1:8000`).

**Build:**
- Python package defined in `pyproject.toml`, built with Hatchling. Dependencies: `mcp[cli]>=1.0.0`, `pydantic>=2.0.0`, `httpx>=0.27`. Optional `[web]` adds `starlette` and `uvicorn`; `[dev]` adds pytest, ruff.
- CLI entry: `personal-finance-mcp = "src.server:main"`.
- Next.js site in `web/` built with `npm run build` (static export).

**CI (4 workflows in `.github/workflows/`):**
- `ci.yml` – tests/lint.
- `codeql.yml` – CodeQL security analysis.
- `hf-sync.yml` – auto‑sync to Hugging Face Docker Space on push to main.
- `pypi-publish.yml` – publish to PyPI.

**Deployment:**
- Primary: Hugging Face Docker Space (auto‑synced, `Dockerfile` multi‑stage build). Health check: `GET /api/health` every 30s.
- Docker: `docker build -t personal-finance-mcp . && docker run -p 7860:7860 personal-finance-mcp`.
- Local: `pip install -e . && python -m src.web` (with `web/out/` built).
- PyPI: `pip install personal-finance-mcp` then `personal-finance-mcp` (stdio).
- Cross‑origin: `CORS` allows `*` origins for GET/POST, no credentials. Security headers include CSP (allows Hugging Face frames), HSTS, etc.

## Existing Tests
**Test runner:** pytest (12 test files in `tests/`).

**What is tested:** The 137 passing tests (from README badge) cover deterministic calculator functions. Tests use `pytest-asyncio` and `pytest-cov`.

**How to run:** `pytest -q` (configured via `pyproject.toml` with `testpaths = ["tests"]` and `pythonpath = ["."]`).

**What is not covered (from evidence):** No test files are provided in the scan data. The following are potentially untested based on the code structure: ASGI middleware (`SecurityMiddleware`), API routes (`/api/*`), rate‑limiting logic, Next.js UI, Docker build, live‑market‑data HTTP calls, and integration between tool modules.

## Risks
- `src/web/server.py:58-75` – `PARAM_CAPS` caps loop‑driving inputs (years, months, age) but depends on each calculator respecting the bound. If a calculator uses parameter names not in this dict, unbounded loops remain possible.
- `src/web/server.py:95-106` – In‑memory rate‑limiter (`_hits` dict) can grow to `_MAX_TRACKED_IPS` entries per window. Under a distributed attack with spoofed IPs, it clears all counters, losing legitimate tracking. Also not persisted across restarts.
- `src/web/server.py:306-344` – `build_app()` accesses `mcp._tool_manager._tools` (private attribute) for tool listing. If the FastMCP internal API changes, this breaks.
- `src/tools/planning.py:516-548` – `plan_financial_goal_tool` and other planning tools build output as f‑string templates with hard‑coded currency symbols (`₹`). No formatting abstraction.
- `src/tools/marketdata.py` – Live‑data functions (`get_mf_nav`, `get_fx_rate`, `get_quote`) make HTTP calls with no timeout configuration visible in the scan. If external APIs hang, the server or MCP client blocks indefinitely.
- `Dockerfile:11` – `npm run build` runs during Docker build; if it fails, the image still builds but the static site is absent (the mount at line 332 checks `static_dir.is_dir()` and skips silently).
- `src/web/server.py:270-273` – Catch‑all `except Exception` suppresses all unexpected errors (logging only) and returns `400`. Production observability depends on log aggregation.

## Not Determined
- The exact list of 12 test files and their coverage of individual tools.
- Whether live‑market‑data functions (`marketdata.py`) have timeout or retry logic.
- The full list of 77 tool names beyond the 13 module `register()` calls.
- The Next.js page structure beyond the known routes (home, calculator, tools, dashboard, connect).
- Any documentation files in `docs/` (HOW_IT_WORKS.md, deployment.md, Architecture.md, testing.md, setup.md) – their content is not provided.
- Whether there are any tool integrations beyond the 13 registered modules (e.g., a retirement calculator not shown in the scan).