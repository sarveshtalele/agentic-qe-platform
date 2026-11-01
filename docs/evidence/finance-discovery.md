## Purpose and Users
This is a **Personal Finance MCP server** that provides deterministic financial calculators exposed over the Model Context Protocol (MCP). It serves three interfaces from one codebase: an MCP server for AI clients (Claude Desktop, Claude Code, Cursor), a JSON API for the web frontend, and a static Next.js website with tools, calculator, market dashboard, and setup guide. Users are individuals seeking financial planning via LLM chat (plain-language questions routed to tools) or via the web UI.

## How It Runs End to End
1. **Entry point for MCP (stdio):** `python -m src` → `src/__main__.py` → `src/server.py:main()` → runs `mcp.run(transport="stdio")` using the FastMCP instance that has all tool modules registered.
2. **Entry point for unified web server:** `python -m src.web` → `src/web/__main__.py` → `src/web/server.py:main()` → uvicorn runs the ASGI app built by `build_app()`.
3. **A tool call (e.g., SIP calculation via MCP):** MCP request comes in → `src/server.py` receives on the FastMCP server → dispatches to `mutual_funds.sip_calculator` registered via `mutual_funds.register(mcp)`.
4. **A web API call (e.g., `/api/calc`):** HTTP POST to `/api/calc` with JSON body → `src/web/server.py:run_calc()` → validates inputs via `_sanitize_params()` → looks up function in `CALCULATORS` dict → calls pure function (e.g., `tvm.future_value`) → returns JSON response.
5. **Static site serving:** `src/web/server.py:build_app()` mounts `web/out` directory (Next.js static export) at `/` on the Starlette app.

## Architecture
Three layers:
- **MCP Layer:** FastMCP server (`src/server.py`) registers 13 tool modules from `src/tools/`. Communicates over stdio or streamable-HTTP.
- **Web/API Layer:** Starlette ASGI app (`src/web/server.py`) wraps the MCP streamable-HTTP app. Security middleware (CSP headers, rate limiting, body cap, input bounds) is implemented in `src/web/server.py`. Serves JSON API at `/api/` and Next.js static site at `/`.
- **Tool Layer:** Pure Python functions in `src/tools/` (12 modules visible in `largest_sources` scan, plus `cashflow.py` and `risk_profile.py` making 13 total). Each module has a `register(mcp)` function that wraps pure functions as MCP tools.

## Modules

| Path | Responsibility | Depends On |
| :--- | :--- | :--- |
| `src/server.py` | FastMCP server initialization, registers all tool modules | `mcp[cli]`, `FastMCP`, all tools in `src/tools/` |
| `src/__main__.py` | Entry point for stdio MCP (`python -m src`) | `src.server` |
| `src/web/server.py` | Unified Starlette app: MCP streaming + API + static site, security middleware | `starlette`, `src.server`, tools from `src/tools/` |
| `src/web/__main__.py` | Entry point for web server (`python -m src.web`) | `src.web.server` |
| `src/tools/tvm.py` | Time Value of Money (10 tools: FV, PV, annuities, EAR, etc.) | `mcp[cli]`, `pydantic`, formatters |
| `src/tools/planning.py` | Financial planning (9 tools: net worth, ratios, emergency fund, health score) | `tvm`, `mcp[cli]`, formatters |
| `src/tools/portfolio.py` | Portfolio analytics (11 tools: CAPM, Sharpe, Sortino, etc.) | `mcp[cli]`, formatters |
| `src/tools/debt.py` | Debt & loans (6 tools: EMI, amortization, prepayment) | `mcp[cli]`, formatters |
| `src/tools/mutual_funds.py` | Mutual funds (7 tools: SIP, SWP, CAGR, NAV) | `mcp[cli]`, formatters |
| `src/tools/india_savings.py` | Indian small savings (9 tools: PPF, SSY, NSC, EPF, etc.) | `mcp[cli]`, formatters |
| `src/tools/bonds.py` | Fixed income (6 tools: bond price, YTM, duration, convexity) | `mcp[cli]`, formatters |
| `src/tools/derivatives.py` | Derivatives (5 tools: options, futures, Black-Scholes) | `mcp[cli]`, formatters |
| `src/tools/stocks.py` | Equity valuation (5 tools: DDM, P/E, DCF) | `mcp[cli]`, formatters |
| `src/tools/cashflow.py` | Cash flow & budgeting (3 tools) | `mcp[cli]`, formatters |
| `src/tools/risk_profile.py` | Risk profiling (1 tool) | `mcp[cli]`, formatters |
| `src/tools/advisor.py` | Meta-advisor orchestrator (1 tool) | `mcp[cli]`, formatters |
| `src/tools/marketdata.py` | Live market data (4 tools: MF search, NAV, FX, quote) | `httpx`, `mcp[cli]`, formatters |
| `src/models/schemas.py` | Pydantic input schemas (TVMInput, LoanInput, BondInput, etc.) | `pydantic`, `enums` |
| `src/models/enums.py` | Enum types (CompoundingFrequency, AnnuityType, LoanType, etc.) | none |
| `src/utils/formatters.py` | Output formatting for tool responses (`format_currency`, `format_percentage`, etc.) | none |
| `run_production.py` | Production server runner for SSE transport | `mcp` |
| `src/web/__main__.py` | Entry point for web server | `src.web.server` |
| `web/` (various files) | Next.js frontend (static export → `web/out`) | Next.js, React |

## Interfaces
- **MCP Server:** Streamable-HTTP at `/mcp` when run via `python -m src.web`, or stdio transport when run as `python -m src` or via `run_production.py` (SSE transport). Number of tools not determined from evidence (the `pyproject.toml` says 76, the `README.md` says 77).
- **Web JSON API** (6 endpoints, all in `src/web/server.py`):
  - `GET /api/health` – health check
  - `GET /api/tools` – list all tools with categories
  - `POST /api/calc` – run a calculator by name with params
  - `GET /api/nav` – mutual fund NAV lookup (by scheme code or search query)
  - `GET /api/fx` – foreign exchange rate
  - `GET /api/quote` – stock/index quote
- **Command-line:** `personal-finance-mcp` CLI entry point in `pyproject.toml` (`src.server:main`), runs stdio MCP. `run_production.py` accepts `--host` and `--port` arguments for SSE transport.

## Data and Integrations
- **No persistent storage:** The code and documentation describe the system as stateless with no database and no sessions.
- **Live market data** (`src/tools/marketdata.py`): Uses `httpx` to fetch from AMFI (mutual fund NAVs), Frankfurter API (FX rates), and Yahoo Finance (equity quotes). The `pyproject.toml` declares `httpx>=0.27` as a dependency. No evidence of API keys in the code. No integration test results are provided to verify these external calls work.
- **Schemas:** 15 Pydantic input models defined in `src/models/schemas.py` for calculator parameters.

## Configuration and Deployment
- **Python package:** Defined in `pyproject.toml`, package name `personal-finance-mcp`, version `2.0.0`. Dependencies: `mcp[cli]`, `pydantic`, `httpx`. Optional `[web]` extra includes `starlette` and `uvicorn`. Optional `[dev]` extra includes `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`.
- **Environment Variables:**
  - `PORT` (default `7860`) – port for the unified web server (`src/web/server.py`)
  - `MCP_HOST` (default `127.0.0.1`) – bind host for SSE server (`run_production.py`)
  - `MCP_PORT` (default `8000`) – port for SSE server (`run_production.py`)
- **CI/CD:** Four GitHub Actions workflows at `.github/workflows/`: `ci.yml`, `codeql.yml`, `hf-sync.yml` (syncs to Hugging Face Docker Space), `pypi-publish.yml`.
- **Docker:** Dockerfile multi-stage build: builds Next.js site (Stage 1), then Python runtime (Stage 2) with `pip install --no-cache-dir -e ".[web]"` and static site copied in. Runs `CMD ["python", "-m", "src.web"]` on port 7860 with healthcheck.
- **Deployment:** Hugging Face Docker Space (auto-synced via `hf-sync.yml`), PyPI package, and local Docker.

## Existing Tests
- **Count:** The scan found 12 test files matching `test_*.py` patterns. The `pyproject.toml` configures pytest with `testpaths = ["tests"]`.
- **Test runner:** pytest, with `pytest-asyncio` and `pytest-cov` as dev dependencies.
- **The README claims 119–137 passing tests, but no test content, execution results, or coverage data are provided in the evidence. These claims are unverified.**

## Risks
- `src/web/server.py:95` – `_hits: dict[str, deque]` is a process-memory rate-limit tracking dict. Under a distributed denial-of-service with rotating IPs, the pruning at line 105 (`_hits.clear()`) on exceeding 20,000 tracked IPs is a hard reset that could be triggered repeatedly. Rate-limiting effectiveness per-client degrades during a burst of distinct IPs.
- `src/web/server.py:114-117` – `_client_ip()` trusts the first `X-Forwarded-For` header value. If deployed behind a proxy that does not strip spoofed headers, an attacker can forge their IP to bypass per-IP rate limiting.
- `src/web/server.py:147` – Security middleware only rate-limits and body-checks `/api` paths. The `/mcp` endpoint (streaming SSE) is not rate-limited by this middleware.
- `src/web/server.py:247-253` – The `run_calc` handler catches all exceptions with bare `except Exception`, which is intentional to avoid leaking stack traces but also catches `SystemExit` and `KeyboardInterrupt`.
- `src/tools/planning.py:376` – Net worth benchmark formula `age * monthly_income * 12 / 10` is a hardcoded heuristic with no evidence of validation.
- Tool count inconsistency: The `pyproject.toml` description says "76 deterministic tools," the `README.md` says "77 calculators" and "77 tools," and the scan of `largest_sources` symbols lists fewer than 76 tools across the 12 modules shown.

## Not Determined
- Exact number of tools. The evidence is inconsistent: `pyproject.toml` says 76, `README.md` says 77, and the symbol counts from `largest_sources` (which does not include `cashflow.py` or `risk_profile.py` symbols) sum to fewer than 76.
- Test file paths and their contents. The scan counted 12 test files but did not list them.
- Whether any tests actually pass or fail. No test execution results are provided.
- Whether the live market data integrations (AMFI, Frankfurter, Yahoo) work correctly in practice or have proper error handling.
- Full content of `src/web/server.py` beyond the first 360 lines shown in `largest_sources`. The security middleware code (lines 132-174) and parameter caps (lines 64-75) are present in the source provided, but the evidence limits coverage.
- Number of Python source files that are not tools (the scan reports 38 Python files total, but only 12 tool modules plus `server.py`, models, and utils are visible).