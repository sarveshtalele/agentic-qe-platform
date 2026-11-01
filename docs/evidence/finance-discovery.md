## Purpose and Users

This is a **Personal Finance MCP server** — a deterministic toolkit of financial calculators exposed over the Model Context Protocol (MCP). Its purpose is to let LLMs (Claude Desktop, Claude Code, Cursor) execute verifiable personal-finance math: TVM, debt, Indian small-savings schemes, bonds, derivatives, portfolio analytics, mutual funds, and live market data. It also ships a Next.js website and a JSON API on the same ASGI app.

Users connect to it either as an MCP connector URL (`/mcp` over streamable-HTTP), via stdio (`python -m src`), or through the web UI at `/`. The primary users are developers and financial advisors who want an AI assistant grounded in deterministic formulas rather than model guesses.

**Tool count discrepancy:** The scan evidence shows 76 tool symbols registered across 13 `src/tools/` modules (one `register` function per module, each registering multiple `@mcp.tool` decorated functions). The `Dockerfile` (line 16) states "76 tools" and `pyproject.toml` (line 4) says "76 deterministic tools." However, `src/server.py` (line 39) reads `len(mcp._tool_manager._tools)` with no hardcoded number, and `src/web/server.py` (line 227) reports tools dynamically. The `README.md` claims "77 tools" (lines 3, 52) and "77 calculators" (line 3). This is a contradiction in the evidence that cannot be resolved without counting every `@mcp.tool` decorator call across all tool modules.

## How It Runs End to End

**MCP request (streamable-HTTP):** A user asks Claude Desktop a question like "I'm 30, earn ₹1L/month, want to retire at 60." Claude's model routes intent to `create_financial_plan` (in `src/tools/advisor.py`). That tool chains calls to `inflation_adjusted_amount` (from `src/tools/tvm.py`), `required_monthly_savings` (also `tvm.py`), and others, then returns a formatted answer. The MCP transport is handled by FastMCP in `src/server.py`, mounted inside the Starlette app at `/mcp` from `src/web/server.py`.

**JSON API request (HTTP):** A browser at `/api/calc` sends `POST` with body `{"calculator": "emi", "params": {...}}`. The handler `run_calc` in `src/web/server.py` validates and sanitizes params via `_sanitize_params`, then calls `debt.calculate_emi` from `src/tools/debt.py`. The response is a JSON object with the result.

**Web UI request:** A visitor loads `/tools` on the Next.js site. The browser fetches `/api/tools` to list all tools with descriptions and categories, then renders the page from `web/app/tools/page.js`.

## Architecture

The system has three layers stacked in one process:

1. **Pure calculation layer** (`src/tools/`) — stateless, deterministic Python functions with no side effects.
2. **MCP server layer** (`src/server.py`) — FastMCP instance that imports every tool module and calls its `register(mcp)`.
3. **Web/API layer** (`src/web/server.py`) — a Starlette ASGI app that mounts three things on a single port: the MCP app at `/mcp`, JSON API handlers at `/api/*`, and static Next.js export at `/`.

The tool files separate pure functions from MCP wrappers: each file has standalone math functions and a `register(mcp)` function that decorates them with `@mcp.tool`. The same pure functions power the MCP server, the JSON API, and the unit tests.

## Modules

| Path | Responsibility | Depends On |
|------|---------------|------------|
| `src/server.py` | FastMCP server initialization, tool registration | All `src/tools/*` modules, `mcp` |
| `src/__main__.py` | Entry point for stdio mode (`python -m src`) | `src.server.mcp` |
| `src/tools/tvm.py` | Time Value of Money (FV, PV, annuity, perpetuity, EAR, rule of 72, real return, inflation, required savings) | `mcp`, `src.utils.formatters` |
| `src/tools/debt.py` | EMI, amortization, loan comparison, prepayment, consolidation, invest-vs-prepay | `mcp`, `src.utils.formatters` |
| `src/tools/planning.py` | Net worth, financial ratios, emergency fund, budget analysis (50/30/20), financial health score, retirement/education/insurance planning | `mcp`, `src.utils.formatters`, `src.tools.tvm` |
| `src/tools/portfolio.py` | CAPM, Sharpe/Sortino/Treynor/Jensen's alpha, information ratio, expected return, risk, two-asset portfolio, asset allocation suggestion | `mcp`, `src.utils.formatters` |
| `src/tools/mutual_funds.py` | SIP calculator, SIP required for target, lumpsum vs SIP, expense ratio impact, SWP, CAGR, NAV calculation | `mcp`, `src.utils.formatters` |
| `src/tools/india_savings.py` | PPF, SSY, NSC, KVP, SCSS, RD, FD, EPF, gratuity | `mcp`, `src.utils.formatters` |
| `src/tools/bonds.py` | Bond price, current yield, YTM, duration, convexity, zero-coupon bond | `mcp`, `src.utils.formatters` |
| `src/tools/derivatives.py` | Futures fair value, option payoff, put-call parity, Black-Scholes, beta hedge | `mcp`, `src.utils.formatters` |
| `src/tools/stocks.py` | Gordon growth model, multi-stage DDM, P/E valuation, DCF, dividend yield | `mcp`, `src.utils.formatters` |
| `src/tools/cashflow.py` | Cash flow statement, debt-to-income, contingency fund | `mcp`, `src.utils.formatters` |
| `src/tools/risk_profile.py` | Risk profile score (suitability → equity/debt split) | `mcp`, `src.utils.formatters` |
| `src/tools/advisor.py` | `create_financial_plan` orchestrator (story → prioritized plan) | `mcp`, `src.utils.formatters` |
| `src/tools/marketdata.py` | Live data: mutual fund search/NAV (AMFI), FX (Frankfurter/ECB), equity quotes (Yahoo) | `mcp`, `httpx` |
| `src/models/schemas.py` | Pydantic input models (TVM, annuity, loan, goal, net worth, budget, bond, stock, portfolio, SIP, retirement, financial health) | `pydantic`, `src.models.enums` |
| `src/models/enums.py` | Enums: compounding frequency, annuity type, loan type, risk profile, bond type, return method | none |
| `src/utils/formatters.py` | Output formatting (currency, percentage, tables, section helpers) | none |
| `src/web/server.py` | Starlette ASGI app: mounts MCP app, adds security middleware, API routes, static file serving | `starlette`, `src.server.mcp`, `src.tools.*` |
| `src/web/__main__.py` | Entry point for web mode (`python -m src.web`) | `src.web.server.main` |
| `run_production.py` | Alternative entrypoint for SSE transport (legacy) | `src.server.mcp` |
| `web/app/` (multiple JS files) | Next.js frontend: home, tools catalog, calculator, dashboard, connect guide | Next.js |

## Interfaces

**MCP server endpoints (declared in `src/server.py` via FastMCP):** Tools registered across 13 modules. Each tool is declared with `@mcp.tool(name=...)` and accepts typed parameters. Transport: stdio (default) or streamable-HTTP at `/mcp`. Exact tool count is inconsistent in the evidence: `Dockerfile` line 16 and `pyproject.toml` line 4 state 76; `README.md` lines 3, 52 state 77.

**JSON API endpoints (declared in `src/web/server.py`):** 6 routes:
- `GET /api/health` — returns `{"status": "ok", "tools": len(mcp._tool_manager._tools)}`
- `GET /api/tools` — lists all tools with name, category, description
- `POST /api/calc` — runs a named calculator from a 15-entry registry (`CALCULATORS`)
- `GET /api/nav` — mutual fund NAV lookup (by scheme code or search query)
- `GET /api/fx` — foreign exchange rate (default USD/INR)
- `GET /api/quote` — stock/index quote (default ^NSEI)

**CLI entry points:**
- `python -m src` — stdio MCP server
- `python -m src.web` — unified HTTP server on port 7860
- `personal-finance-mcp` (installed script) — same as `python -m src`
- `python run_production.py` — SSE transport (legacy, port 8000)

## Data and Integrations

The project has **no database, no sessions, no persistent storage**. Every call is stateless and reproducible.

**External data sources (all public, no API keys):**
- Mutual fund NAVs — AMFI (India)
- Foreign exchange — Frankfurter API (ECB data)
- Equity quotes — Yahoo Finance

These are called from `src/tools/marketdata.py` via `httpx`. The server has a 16 KB body cap for `/api` paths and per-IP rate limiting (90 requests per 10 seconds) for `/api` paths, but there is **no circuit breaker, retry, or caching** for these external calls. If a source is unreachable, the error propagates as an HTTP 400 or 500.

**Input validation bounds** (set in `src/web/server.py` `PARAM_CAPS`): years ≤ 120, months ≤ 2400, age ≤ 120, compounding periods ≤ 365, absolute numeric magnitude ≤ 1e13. These prevent denial-of-service via loop-driven calculators.

**Body cap gap:** The 16 KB body cap (`MAX_BODY` at `src/web/server.py:58`) is enforced only for `/api` paths (check at line 147). The `/mcp` streaming path has no body cap from this middleware.

## Configuration and Deployment

**Environment variables:**
- `PORT` — bind port for the web server (default 7860, used by Hugging Face Spaces)
- `MCP_HOST` / `MCP_PORT` — for the legacy `run_production.py` runner (defaults 127.0.0.1:8000)

**Dependencies** (`pyproject.toml`): core requires Python ≥3.10, `mcp[cli]>=1.0.0`, `pydantic>=2.0.0`, `httpx>=0.27`. Web mode adds `starlette>=0.37` and `uvicorn>=0.30`. Dev mode adds `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`.

**Build & CI** (from scan evidence): Four GitHub Actions workflows:
- `.github/workflows/ci.yml` — test runner (pytest)
- `.github/workflows/codeql.yml` — CodeQL security analysis
- `.github/workflows/hf-sync.yml` — auto-sync to Hugging Face Spaces on push to `main`
- `.github/workflows/pypi-publish.yml` — PyPI publish

**Deployment:** Published to PyPI as `personal-finance-mcp` (version 2.0.0 from `pyproject.toml`). Also deployed to a Hugging Face Docker Space at `https://sarveshtalele-personal-finance-mcp.hf.space`. The `Dockerfile` is a multi-stage build: Node 20 builds the Next.js site, then Python 3.12-slim runs the unified server with the static export.

**Security posture** (from `src/web/server.py`): CSP headers, HSTS, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, COOP. Body size cap (16 KB for `/api` only), per-IP rate limiting (90/10s for `/api` only), input bounding on loop-driving parameters. CORS allows `*` origins with GET/POST only, no credentials.

## Existing Tests

From the scan: 12 test files, test runner is pytest. The `README.md` badge claims "137 passing tests" (line 9), but test file contents were not provided in the evidence, so the actual test count and pass/fail status cannot be confirmed. How to run from evidence: `pytest -q` (from `pyproject.toml` test config). What is not covered: integration tests for the web layer (API routes, middleware, rate limiting), end-to-end MCP transport tests, and failure modes for live market data calls.

## Risks

- `src/web/server.py:95` (`_hits: dict[str, deque]`) — per-IP rate limiting state is in-process. Under rotated/spoofed IPs (e.g., genuine clients behind a shared proxy), the in-memory `deque` is keyed by IP derived from `X-Forwarded-For` (line 116). If every request has a unique IP, the `_MAX_TRACKED_IPS` cap of 20,000 (line 96) prevents unbounded growth, but under sustained rotation the rate limiter has no effect and client IPs are effectively untracked.

- `src/web/server.py:265` — The exception handler `except (ValueError, ZeroDivisionError, KeyError, TypeError)` catches domain errors from pure functions. However, `ZeroDivisionError` can leak whether a division-by-zero occurred, which an attacker could use to probe edge cases.

- `src/web/server.py:268` (`except Exception: # noqa: BLE001`) — bare except swallows all unexpected exceptions. They are logged to "personal-finance" logger, but the server returns a generic 400 even for internal bugs.

- `src/web/server.py:58,147` — The 16 KB body cap (`MAX_BODY`) is enforced only for `/api` paths (check at line 147). The `/mcp` streaming path has no body cap from this middleware, leaving it potentially vulnerable to large payloads.

- `src/web/server.py:177-193` — The `_category` function maps module names to category labels. If a tool is added from a new module not in the dictionary, it falls through to `.title()` (line 192), which may produce an unexpected category name.

- `src/tools/marketdata.py` (154 lines, 5 symbols from scan) — calls to AMFI, Frankfurter, and Yahoo are keyless and uncached. If any of these free public APIs become unavailable, rate-limit the server, or change their endpoints, the market data tools will break without graceful degradation.

- `src/web/server.py:79` — CSP includes `'unsafe-inline'` for both `style-src` and `script-src`. This weakens XSS protection; inline scripts are permitted.

- `src/tools/planning.py:438` (`json.loads(assets_json)`) — the MCP tool `calculate_net_worth` accepts JSON strings that are parsed with `json.loads`. No size limit or structural validation is applied to the deserialized dict before passing to the pure function.

- `src/server.py:69` (`allowed_hosts=["*"]`, `allowed_origins=["*"]`) — DNS rebinding protection is disabled, and all origins are permitted for the MCP transport. This is intentional for public hosting per the comment at lines 65-67.

## Not Determined

- The exact number of tools: the evidence shows 76 (Dockerfile, pyproject.toml) and 77 (README.md) without reconciliation. A manual count of every `@mcp.tool` decorator is needed.
- Test file contents and actual test count: 12 test files exist, but their contents and the claimed "137 passing tests" cannot be verified from the evidence provided.
- The full source code of `src/tools/marketdata.py` was not provided; only its interface (5 symbols, 154 lines) and external dependencies (`httpx` for AMFI/Frankfurter/Yahoo) are known.
- The Next.js frontend code was not scanned in detail; only page structure (home, tools, calculator, dashboard, connect) is known from file names.
- No authentication, authorization, or database exists in the codebase.
- The Redis or any external rate-limiting store is not present; the rate limiter is purely in-process single-worker.
- Total file count: scan evidence shows languages (38 Python, 15 JavaScript, 1 CSS) but does not confirm "88 files" — that count may include other file types (config, markdown, etc.) not enumerated in the language breakdown.