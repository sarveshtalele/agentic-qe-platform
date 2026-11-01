## Purpose and Users
This is a deterministic personal finance toolkit exposed over the Model Context Protocol (MCP). It provides 77 calculators covering time value of money, portfolio analytics, financial planning, Indian small savings schemes, mutual funds, debt and loans, fixed income, derivatives, equity valuation, cash flow, risk profiling, and live market data.

Users include individuals connecting via MCP clients (Claude Desktop, Claude Code, Cursor, VS Code), developers using the JSON API, and anyone visiting the web UI at `https://sarveshtalele-personal-finance-mcp.hf.space`. The system takes plain-language financial questions and routes them to deterministic calculators through an LLM orchestrator.

## How It Runs End to End
A user connects via MCP transport (stdio or streamable-HTTP) to `src/server.py`. The FastMCP server registers tools from each module in `src/tools/`. A plain-language query like "I'm 30, earn 1L/month, want to retire at 60" flows to the `create_financial_plan` orchestrator in `src/tools/advisor.py`, which chains calculations from `src/tools/tvm.py`, `src/tools/planning.py`, and `src/tools/portfolio.py`.

For the web UI: a browser request hits `src/web/server.py`, which routes `/` to static Next.js files in `web/out`, `/api/calc` to calculator functions registered in the `CALCULATORS` dict (line 37-53), and `/mcp` to the FastMCP streamable-HTTP handler. Market data endpoints (`/api/nav`, `/api/fx`, `/api/quote`) in `src/web/server.py` call functions in `src/tools/marketdata.py`.

## Architecture
Three layers from one codebase:
1. **Core calculators** (`src/tools/`): Pure mathematical functions with thin `@mcp.tool` wrappers. Each file has a `register(mcp)` function.
2. **Server layer** (`src/server.py`, `src/web/server.py`): FastMCP server for MCP protocol, plus Starlette ASGI app for HTTP serving.
3. **Front end** (`web/app/`): Next.js static site exported to `web/out`, served by the Starlette app.

The unified server (`src/web/server.py`) serves MCP streamable-HTTP at `/mcp`, JSON API at `/api/*`, and static website at `/` from one ASGI app on one port.

## Modules
| Path | Responsibility | Dependencies |
|------|---------------|--------------|
| `src/server.py` | FastMCP server initialization, tool registration | `mcp`, all `src/tools/` modules |
| `src/tools/tvm.py` | Time Value of Money: 10 calculators | `mcp`, `math` |
| `src/tools/debt.py` | Debt & Loans: EMI, amortization, comparison | `mcp`, `math` |
| `src/tools/planning.py` | Financial Planning: net worth, ratios, goals, retirement, insurance | `mcp`, `src/tools/tvm.py` |
| `src/tools/portfolio.py` | Portfolio Analytics: CAPM, Sharpe, Sortino, MPT | `mcp`, `math` |
| `src/tools/bonds.py` | Fixed Income: bond price, YTM, duration, convexity | `mcp`, `math` |
| `src/tools/stocks.py` | Equity Valuation: DDM, P/E, DCF | `mcp`, `math` |
| `src/tools/mutual_funds.py` | Mutual Funds: SIP, SWP, CAGR, NAV | `mcp`, `math` |
| `src/tools/derivatives.py` | Derivatives: futures, options, Black-Scholes | `mcp`, `math` |
| `src/tools/india_savings.py` | Indian Small Savings: PPF, SSY, NSC, EPF | `mcp`, `math` |
| `src/tools/cashflow.py` | Cash Flow & Budgeting | `mcp` |
| `src/tools/risk_profile.py` | Risk profiling score | `mcp` |
| `src/tools/advisor.py` | Financial plan orchestrator | `mcp`, other tools |
| `src/tools/marketdata.py` | Live data: mutual fund NAV, FX rates, stock quotes | `mcp`, `httpx` |
| `src/models/schemas.py` | Pydantic input schemas | `pydantic` |
| `src/utils/formatters.py` | Output formatting helpers | None |
| `src/web/server.py` | Unified HTTP server: routes, security, calculator registry | `starlette`, `src/server.py`, tool modules |
| `src/__main__.py` | Entry point for `python -m src` (stdio) | `src/server.py` |
| `src/web/__main__.py` | Entry point for `python -m src.web` (HTTP) | `src/web/server.py` |
| `run_production.py` | SSE transport runner | `src/server.py` |
| `web/app/` | Next.js front-end pages | Next.js, React |

## Interfaces
- **MCP tools**: 77 tools registered via `@mcp.tool` decorators across 13 modules. Entry point at `src/server.py` lines 77-89.
- **JSON API endpoints** (in `src/web/server.py` lines 320-327): `GET /api/health`, `GET /api/tools`, `POST /api/calc`, `GET /api/nav`, `GET /api/fx`, `GET /api/quote`.
- **MCP streamable-HTTP endpoint**: `/mcp` from FastMCP's `streamable_http_app()`.
- **Static web UI**: `/` serves Next.js export from `web/out`.
- **CLI entry points**: `personal-finance-mcp` command from `pyproject.toml` line 28, `python -m src` (stdio), `python -m src.web` (HTTP), `python run_production.py` (SSE).
- **Calculator registry**: 15 calculators mapped in `CALCULATORS` dict at `src/web/server.py` lines 37-53.

## Data and Integrations
- **No database**: Stateless, in-memory only. Per-IP rate limit tracking in `_hits` dict at `src/web/server.py` line 95.
- **Live market data**: Public, keyless sources via `src/tools/marketdata.py` (AMFI for mutual fund NAVs, ECB for FX, Yahoo for equity quotes). Uses `httpx`.
- **No secrets**: All data sources are public and require no API keys.
- **Failure modes**: If market data sources fail, the API endpoints return error responses via JSON. Input validation catches domain errors (ValueError, ZeroDivisionError) at `src/web/server.py` lines 265-267.

## Configuration and Deployment
- **Build**: `pyproject.toml` defines Python project with `hatchling` build backend. `Dockerfile` does multi-stage build: Node 20 for Next.js export, Python 3.12-slim for runtime.
- **CI**: 4 GitHub Actions workflows: `ci.yml`, `codeql.yml`, `hf-sync.yml` (auto-sync to Hugging Face), `pypi-publish.yml`.
- **Environment variables**: `PORT` (default 7860 for HF Spaces), `MCP_HOST` (default 127.0.0.1), `MCP_PORT` (default 8000).
- **Docker**: `Dockerfile` uses `CMD ["python", "-m", "src.web"]` on port 7860 with health check.
- **PyPI package**: `personal-finance-mcp` with optional extras `[web]` (starlette, uvicorn) and `[dev]` (pytest, ruff).
- **Hosting**: Deployed as Hugging Face Docker Space, auto-synced from GitHub main branch.

## Existing Tests
- 12 test files using `pytest` with `pytest-asyncio` and `pytest-cov` plugins.
- Configuration at `pyproject.toml` lines 37-39: test paths in `tests/`, Python path includes root.
- README states 119 tests (line 203) or 137 tests (line 9).
- Coverage: The test file count suggests unit tests for calculator functions, but no test files were provided in the scan. Not determined which specific modules or edge cases are covered.

## Risks
- `src/web/server.py:163-165`: Rate limit enforcement at 90 requests per 10 seconds per IP. If this is triggered by legitimate heavy usage, users will receive 429 errors with no clear recovery guidance. The rate limit applies only to `/api/*` paths.
- `src/web/server.py:105-106`: `_prune` function clears the entire `_hits` dict when it exceeds 20,000 tracked IPs, which would reset rate limit counters for all clients including potential attackers.
- `src/web/server.py:37-53`: `CALCULATORS` dict maps calculator names to pure functions directly imported from tool modules. If any of these functions raise unhandled exceptions beyond the caught types (ValueError, ZeroDivisionError, KeyError, TypeError), the generic error handler at line 273 logs them but returns a generic "calculation failed" message.
- `src/tools/marketdata.py`: All live data sources (AMFI, ECB, Yahoo) are keyless and public. There is no authentication or rate limiting on the downstream requests from the server. If these APIs throttle or block the server, market data endpoints fail silently with error responses.
- `src/web/server.py:206-220`: `_sanitize_params` silently drops nulls and nested structures. This means missing required parameters may not be caught at this layer; the calculator function call at line 264 would then receive unexpected keyword arguments and raise TypeError, caught by the error handler.
- `pyproject.toml:6`: Version 2.0.0 description says "76 deterministic tools" while README says "77 calculators". Tools count at `src/server.py:39` reports `len(mcp._tool_manager._tools)` which varies by registration.

## Not Determined
- Which specific test files exist and their coverage depth. The scan reports 12 test files but none were provided.
- Whether there are any rate limits or authentication requirements for the external market data APIs (AMFI, ECB, Yahoo Finance).
- The exact count of tools (76 vs 77) and whether this discrepancy is a documentation error or actual difference.
- How the Next.js front-end (`web/app/`) is built and what its exact pages are — only a subset of files were visible in the scan.
- Whether there are any CORS or security considerations beyond what's configured in `src/web/server.py`.
- The contents of documentation files (`docs/`) referenced in README.