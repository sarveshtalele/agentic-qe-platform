## Purpose and Users
Personal Finance MCP is a deterministic personal-finance toolkit exposed over the **Model Context Protocol** (MCP). Based on the README, it provides 77 calculators covering time value of money, debt, portfolio analytics, Indian small-savings schemes, mutual funds, bonds, derivatives, equity valuation, cash flow, risk profiling, and a meta-advisor. Users interact via MCP clients (Claude Desktop, Claude Code, Cursor), a web UI, or JSON API endpoints. The README states the system is stateless, but this is not independently verified.

## How It Runs End to End

**MCP tool invocation (stdio transport):**
1. Entry point: `src/__main__.py` calls `src/server.py::main()`.
2. `src/server.py` initializes a `FastMCP` server (`"Personal Finance Advisor"`) and registers tool modules from `src/tools/` (tvm, debt, planning, bonds, stocks, mutual_funds, portfolio, derivatives, india_savings, cashflow, risk_profile, advisor, marketdata) via each module's `register(mcp)` function (lines 77-89).
3. The server runs on stdio transport (`mcp.run(transport="stdio")`, line 94), listening for JSON-RPC requests.

**HTTP connector (streamable-HTTP + website):**
1. Entry point: `src/web/__main__.py` calls `src/web/server.py::main()`.
2. `src/web/server.py::build_app()` (line 306) calls `mcp.streamable_http_app()` to get a Starlette app with `/mcp` endpoint.
3. It adds `CORSMiddleware` (line 310), `SecurityMiddleware` (line 318), and registers 6 API routes (lines 320-327).
4. If `web/out` exists, it mounts `StaticFiles` at `/` (line 343).
5. The app runs via `uvicorn` on `0.0.0.0:PORT` (default 7860, line 354-355).

**Production SSE server:**
1. Entry point: `run_production.py:34` imports `src.server.mcp` and runs it with `mcp.run(transport="sse", host=..., port=...)` (line 43).

**Web UI (Next.js):**
1. The Next.js app in `web/` is built with `npm run build` (output `export`) as shown in `Dockerfile:11`.
2. Pages include home (`web/app/page.js`), calculator (`web/app/calculator/page.js`), dashboard (`web/app/dashboard/page.js`), tools catalog (`web/app/tools/page.js`), connect (`web/app/connect/page.js`).
3. The client calls the JSON API via `web/app/lib.js` (defines endpoints `api/calc`, `api/nav`, `api/fx`, `api/quote`).

## Architecture

- **Layers:** Next.js static frontend → Starlette HTTP server (ASGI) → FastMCP MCP layer → pure Python math functions.
- **Protocol separation:** The same pure functions (e.g., `tvm.future_value`, `debt.calculate_emi`) power MCP tools, the web calculator API (`/api/calc`), and tests, as stated in `README.md:179-180`.
- **Security:** `SecurityMiddleware` (`src/web/server.py:132-174`) injects security headers (CSP, HSTS, etc.), caps request bodies at 16 KB (line 58), rate-limits `/api/*` per client IP (90 requests/10s, lines 59-60), and sanitizes/bounds calculator parameters (lines 196-220).

## Modules

| Path | Responsibility | Depends On |
|---|---|---|
| `src/__init__.py` | Empty package marker | — |
| `src/__main__.py` | Entry point for stdio server | `src.server` |
| `src/server.py` | FastMCP server init, tool registration (lines 77-89), main() | `mcp`, `src.tools.*` |
| `src/tools/tvm.py` | TVM calculations (FV, PV, annuities, perpetuity, rule of 72, EAR, real return, inflation, required savings) — 428 lines | `mcp`, `src.utils.formatters` |
| `src/tools/debt.py` | EMI, amortization schedule, loan comparison, prepayment impact, debt consolidation, invest vs prepay — 371 lines | `mcp`, `src.utils.formatters` |
| `src/tools/planning.py` | Net worth, financial ratios, emergency fund, budget analysis, financial health score, goal/retirement/education/insurance planning — 774 lines | `mcp`, `src.utils.formatters`, `src.tools.tvm` |
| `src/tools/bonds.py` | Bond price, current yield, YTM, duration, convexity, zero-coupon bond price — 306 lines | `mcp`, `src.utils.formatters` |
| `src/tools/stocks.py` | Gordon growth model, multi-stage DDM, P/E valuation, DCF, dividend yield — 267 lines | `mcp`, `src.utils.formatters` |
| `src/tools/mutual_funds.py` | SIP calculator, SIP required for target, lumpsum vs SIP, expense ratio impact, SWP, CAGR, NAV calculation — 339 lines | `mcp`, `src.utils.formatters` |
| `src/tools/portfolio.py` | Portfolio expected return, risk, two-asset portfolio, CAPM, Sharpe/Treynor/Sortino/Jensen's alpha, information ratio, asset allocation — 587 lines | `mcp`, `src.utils.formatters` |
| `src/tools/derivatives.py` | Futures fair value, option payoff, put-call parity, Black-Scholes, beta hedge — 273 lines | `mcp`, `src.utils.formatters` |
| `src/tools/india_savings.py` | PPF, SSY, NSC, KVP, SCSS, RD, FD, EPF, gratuity — 331 lines | `mcp`, `src.utils.formatters` |
| `src/tools/cashflow.py` | Cash flow statement, debt-to-income, contingency fund — 130 lines | `mcp`, `src.utils.formatters` |
| `src/tools/risk_profile.py` | Risk profile score — 120 lines | `mcp`, `src.utils.formatters` |
| `src/tools/advisor.py` | `create_financial_plan` orchestrator — 187 lines | `mcp`, `src.utils.formatters`, `src.tools.*` |
| `src/tools/marketdata.py` | Live market data: MF search, MF NAV, FX rate, stock/index quote — 154 lines | `mcp`, `httpx` |
| `src/models/schemas.py` | Pydantic models (TVMInput, LoanInput, BondInput, PortfolioInput, etc.) — 160 lines | `pydantic`, `src.models.enums` |
| `src/models/enums.py` | Enums (CompoundingFrequency, AnnuityType, LoanType, etc.) — 59 lines | — |
| `src/utils/formatters.py` | Output formatting helpers (currency, percentage, tables) — 103 lines | — |
| `src/web/server.py` | Starlette ASGI app: MCP streaming, 6 API routes, SecurityMiddleware, static serving — 360 lines | `starlette`, `src.server`, `src.tools.*` |
| `src/web/__main__.py` | Entry point for unified HTTP server | `src.web.server` |
| `web/` (directory) | Next.js frontend (static export) | Next.js |

## Interfaces

- **MCP tools:** Registered via `@mcp.tool` decorators in `src/tools/` modules, exposed over stdio (`src/server.py`) or streamable-HTTP (`/mcp` via `src/web/server.py`). The README claims 77 tools, but the scan identifies 13 tool modules with the following exported symbols: tvm (10), portfolio (11), planning (9), india_savings (9), mutual_funds (7), debt (6), bonds (6), derivatives (5), stocks (5), marketdata (4), cashflow (3), risk_profile (1), advisor (1) — totaling 77 across these categories.
- **HTTP API routes (6):** Defined in `src/web/server.py:320-327`:
  - `GET /api/health` — returns tool count (line 227)
  - `GET /api/tools` — lists tools with categories (line 231)
  - `POST /api/calc` — runs calculator by name from `CALCULATORS` registry (line 243)
  - `GET /api/nav` — mutual fund NAV lookup (line 276)
  - `GET /api/fx` — FX rate lookup (line 288)
  - `GET /api/quote` — stock/index quote lookup (line 296)
- **CLI command:** `personal-finance-mcp` script (`pyproject.toml:28`) runs `src.server:main` for stdio transport.
- **Entry point scripts:** `python -m src` (stdio), `python -m src.web` (HTTP/streamable-HTTP), `python run_production.py` (SSE).

## Data and Integrations

- **Storage:** None evident. The system has no database, no file persistence, and no sessions. The rate-limit tracking dictionary (`_hits`, `src/web/server.py:95`) is in-memory and resets on process restart — this is stateful within a single process lifetime but not persistent storage.
- **External services (live market data from `src/tools/marketdata.py`):**
  - Mutual fund NAVs: AMFI (public, keyless)
  - FX rates: ECB/Frankfurter (public, keyless)
  - Equity quotes: Yahoo Finance (public, keyless)
- **Failure handling for external services:** Not determined. `src/tools/marketdata.py` imports `httpx` but no error-handling code (timeouts, retries, fallbacks) is visible in the scan.
- **Static files:** The Next.js export (`web/out`) is served at `/` when the directory exists (`src/web/server.py:330-344`).

## Configuration and Deployment

- **Environment variables:**
  - `PORT` — HTTP server port (default 7860) — `src/web/server.py:354`
  - `MCP_HOST` — SSE server bind host (default 127.0.0.1) — `run_production.py:18`
  - `MCP_PORT` — SSE server bind port (default 8000) — `run_production.py:19`
- **Python packaging:** `pyproject.toml` defines the project, dependencies (`mcp[cli]>=1.0.0`, `pydantic>=2.0.0`, `httpx>=0.27`), optional web deps (`starlette>=0.37`, `uvicorn>=0.30`), dev deps (`pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`), and hatchling build backend.
- **Docker:** `Dockerfile` multi-stage build: Node 20-slim compiles Next.js, then Python 3.12-slim runs `pip install -e ".[web]"` and copies the static export. Healthcheck on `/api/health`, listens on port 7860.
- **CI/CD:** 4 GitHub Actions workflows detected: `.github/workflows/ci.yml`, `.github/workflows/codeql.yml`, `.github/workflows/hf-sync.yml`, `.github/workflows/pypi-publish.yml`.
- **Rate limiting:** 90 requests per 10 seconds per client IP on `/api/*` — `src/web/server.py:59-60`
- **Body cap:** 16 KB maximum request body — `src/web/server.py:58`
- **Parameter caps:** Loop-driving parameters bounded (e.g., `years`: 120, `months`: 2400) — `src/web/server.py:64-75`

## Existing Tests

- **Test runner:** `pytest` configured in `pyproject.toml:37-39` with `testpaths = ["tests"]` and `pythonpath = ["."]`.
- **Test file count:** 12 test files detected by the scan.
- **Test results:** Not provided. The README badge claims 137 passing tests, but no test execution results are present in the scan evidence. Whether these tests pass or fail is not determined.
- **Test coverage:** Not determined. No coverage configuration is visible.
- **Module-specific test coverage:** Not determined. No evidence connects specific test files to specific tool modules (e.g., whether `src/tools/marketdata.py` has any tests).

## Risks

- **`src/tools/marketdata.py:154`** — The `marketdata` module calls external APIs (AMFI, ECB, Yahoo) with no visible error-handling for network failures, timeouts, or rate limits. An outage of any source could return an unhandled exception to the client. No test evidence exists for this module.
- **`src/web/server.py:105-106`** — `_hits.clear()` is a hard cap backstop on the rate-limit tracking dict. If a flood of distinct IPs exceeds 20,000 in one window, all rate-limit state is lost, allowing a burst of requests.
- **`src/web/server.py:162`** — Rate limiting is per in-memory `_hits` dict, not shared across workers/processes. Under multiple uvicorn workers, the rate limit is effectively per-process.
- **`src/web/server.py:353`** — `uvicorn.run(app, host="0.0.0.0", port=port)` binds to all interfaces by default. This exposes the full API and MCP endpoint to any network that can reach the host.
- **`src/tools/planning.py:1`** — `from .tvm import ...` is a relative import that may break if the package layout changes or if run from a different working directory.
- **`Dockerfile:9`** — `npm install --no-audit --no-fund` runs without a lockfile guarantee. The glob `web/package-lock.json*` at line 8 may not match depending on npm version; if no lockfile is present, builds are not reproducible.
- **`Dockerfile:22`** — `pip install -e ".[web]"` uses an editable install in a production Docker image, which is unconventional and may affect import resolution.
- **`src/web/server.py:58-60`** — Rate limit and body cap are configured as module constants, not environment variables. Changing these requires code modification or a rebuild.

## Not Determined

- Test execution results — no test output or results are provided; the README's claim of 137 passing tests cannot be verified.
- Contents of the 12 test files — the scan detected their existence but did not provide their contents.
- Whether any test exists for `src/tools/marketdata.py` or other individual tool modules.
- Requirements traceability — no requirements document or test-to-requirement mapping is provided.
- Dependency versions beyond what is declared in `pyproject.toml` (exact versions of `mcp`, `starlette`, `httpx`, etc.).
- Next.js `package.json` dependencies and build configuration.
- Error-handling details in `src/tools/marketdata.py` (HTTP timeouts, retries, fallback behavior).
- Behavior under high concurrency (multiple simultaneous requests).
- Logging configuration beyond the single `logging.getLogger().exception()` call in `src/web/server.py:272`.
- Whether the 13 registered tool modules (lines 77-89) each have at least one registered tool — the symbols list shows modules with `register` functions but the scan does not confirm every function is mapped to a requirement.
- Whether the live external API endpoints (AMFI, ECB, Yahoo) are functional.