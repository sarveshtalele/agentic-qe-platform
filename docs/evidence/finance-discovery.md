## Purpose and Users

The Personal Finance MCP is a deterministic, stateless financial calculation toolkit exposed through three interfaces: an MCP server (for AI assistants like Claude Desktop/Code), a JSON REST API, and a static Next.js website. It provides 77 pure-math calculators covering time value of money, debt, portfolio analytics, Indian small savings schemes, bonds, derivatives, stocks, mutual funds, cash flow, risk profiling, and live market data (AMFI NAVs, ECB FX rates, Yahoo quotes). A meta-advisor tool (`create_financial_plan`) chains calculators to produce prioritized financial plans from plain-language descriptions.

Users: individuals using MCP-compatible AI assistants, developers integrating financial calculations via API, and general users browsing the website.

## How It Runs End to End

**MCP stdio transport:** User runs `python -m src` → `src/__main__.py` calls `src/server.py:main()` → `src/server.py` initializes `FastMCP` and registers all tool modules via each module's `register(mcp)` function → `mcp.run(transport="stdio")` opens a stdio JSON-RPC channel. Each tool call (e.g., `calculate_emi`) resolves to a function in `src/tools/debt.py:calculate_emi`, wrapped by `@mcp.tool`; the result is formatted by `src/utils/formatters.py:format_tool_response`.

**Unified HTTP server:** User runs `python -m src.web` → `src/web/__main__.py` calls `src/web/server.py:main()` → `src/web/server.py:build_app()` extends the MCP streamable-HTTP app with CORS middleware, a `SecurityMiddleware` (ASGI-layer headers, body cap, per-IP rate limiting), and six JSON API routes on `/api/*`. A sample request: `POST /api/calc` with `{"calculator": "emi", "params": {...}}` → `run_calc()` → `_sanitize_params()` validates/bounds inputs → `CALCULATORS["emi"]` resolves to `debt.calculate_emi` → result returned as JSON. Static files from `web/out` are served at `/`.

**Website (Next.js static export):** Built from `web/` → `npm run build` produces `web/out`. When served by the Python server, users browse `/tools`, `/calculator`, `/dashboard`, `/connect` pages. The calculator page (`web/app/calculator/page.js`) calls `POST /api/calc`.

## Architecture

Three-tier: pure deterministic function modules (`src/tools/`) → MCP server (`src/server.py`) or web server (`src/web/server.py`) → client (MCP/HTTP). The MCP server uses the `fastmcp` library. The web server is a Starlette application that wraps the MCP streamable-HTTP app and adds security middleware and `/api/*` routes. The Next.js frontend is a static export (no SSR). No database, no sessions, no external state.

## Modules

| Path | Responsibility | Depends On |
|------|----------------|------------|
| `src/server.py` | FastMCP initialization, tool registration, stdio entrypoint | `mcp`, all `src/tools/*` |
| `src/__main__.py` | `python -m src` entrypoint | `src.server:main` |
| `src/tools/tvm.py` | 10 TVM calculators (FV, PV, annuity, perpetuity, EAR, etc.) | `math` |
| `src/tools/debt.py` | 6: EMI, amortization, comparison, prepayment, consolidation, invest-vs-prepay | `math` |
| `src/tools/planning.py` | 9: net worth, financial ratios, emergency fund, budget, health score, insurance, retirement, education, goal planning | `tvm`, `formatters` |
| `src/tools/bonds.py` | 6: bond price, YTM, current yield, duration, convexity, zero-coupon | `math` |
| `src/tools/stocks.py` | 5: GGM, DDM, P/E, DCF, dividend yield | `math` |
| `src/tools/mutual_funds.py` | 7: SIP, target SIP, lump-sum-vs-SIP, expense ratio impact, SWP, CAGR, NAV | `math` |
| `src/tools/portfolio.py` | 11: expected return, risk, two-asset, CAPM, Sharpe, Treynor, alpha, information ratio, Sortino, allocation | `math`, `statistics` |
| `src/tools/derivatives.py` | 5: futures fair value, option payoff, put-call parity, Black-Scholes, beta hedge | `math`, `statistics` |
| `src/tools/india_savings.py` | 9: PPF, SSY, NSC, KVP, SCSS, RD, FD, EPF, gratuity | `math` |
| `src/tools/cashflow.py` | 3: cash flow statement, debt-to-income, contingency fund | none |
| `src/tools/risk_profile.py` | 1: risk profile score → equity/debt split | none |
| `src/tools/advisor.py` | 1: `create_financial_plan` orchestrator | all tool modules |
| `src/tools/marketdata.py` | 4: search MF, get NAV, get FX, get quote | `httpx` |
| `src/models/schemas.py` | Pydantic models for calculator inputs (TVM, annuity, loan, bond, etc.) | `pydantic`, `enums` |
| `src/models/enums.py` | Enums: compounding frequency, annuity type, loan type, risk profile, bond type, return method | none |
| `src/utils/formatters.py` | Output formatting for tool responses (currency, percentage, tables) | none |
| `src/web/server.py` | Unified Starlette server: MCP + API + static site, security middleware | `starlette`, `mcp`, `uvicorn`, tool modules |
| `src/web/__main__.py` | `python -m src.web` entrypoint | `src.web.server:main` |
| `web/app/` | Next.js frontend pages (home, tools, calculator, dashboard, connect) | Next.js, React |
| `run_production.py` | SSE transport runner for production | `src.server:mcp` |

## Interfaces

**MCP (Model Context Protocol):**
- Transport: stdio (`python -m src`) or streamable-HTTP (`/mcp` path on the web server) or SSE (`run_production.py`)
- 77 tools registered via `@mcp.tool` decorators across 13 module files
- Tool names include `calculate_net_worth`, `analyze_financial_ratios`, `plan_retirement`, `calculate_emi`, `portfolio_expected_return`, `sip_calculator`, `black_scholes`, `get_mf_nav`, `create_financial_plan`, etc.

**JSON API (6 routes):**
- `GET /api/health` — status, tool count
- `GET /api/tools` — list all tools with category and description
- `POST /api/calc` — run a calculator by name with params
- `GET /api/nav?code=CODE` — mutual fund NAV lookup
- `GET /api/fx?base=USD&symbols=INR` — exchange rate
- `GET /api/quote?symbol=^NSEI` — stock/index quote

**Website:** exported Next.js static pages at `/`, `/tools`, `/calculator`, `/dashboard`, `/connect`.

## Data and Integrations

**No persistent storage.** No database, no sessions, no state.

**External APIs (keyless, public):**
- `src/tools/marketdata.py`: mutual fund NAVs (AMFI), exchange rates (Frankfurter/EU ECB), equity quotes (Yahoo Finance). Uses `httpx`.
- On failure: `src/web/server.py` wraps API calls in try/except; errors return JSON 400 with a message. Market data failures degrade gracefully (calculator functions that don't call external APIs continue working).

## Configuration and Deployment

**Environment variable:** `PORT` (default 7860 for Hugging Face Spaces).

**Build & run:**
- Python: `pip install -e ".[web]"` installs dependencies (`mcp`, `pydantic`, `httpx`, `starlette`, `uvicorn`).
- Website: `cd web && npm install && npm run build` produces static export in `web/out`.
- Docker: multi-stage build (`Dockerfile`) — Node 20 for Next.js build, Python 3.12-slim runtime, serves all three interfaces on port 7860.

**CI/CD:** 4 GitHub Actions workflows:
- `.github/workflows/ci.yml`
- `.github/workflows/codeql.yml`
- `.github/workflows/hf-sync.yml` — syncs to Hugging Face Docker Space on push to `main`
- `.github/workflows/pypi-publish.yml` — publishes to PyPI

**PyPI install:** `pip install personal-finance-mcp` or `uvx personal-finance-mcp`. CLI entry point: `personal-finance-mcp` → `src.server:main`.

## Existing Tests

12 test files. Test runner: `pytest` (configured in `pyproject.toml` with test paths in `tests/`). README reports 137 passing tests. Run with `pytest -q`. What is not covered: not determined from available evidence.

## Risks

- `src/web/server.py:95-106`: In-memory rate-limit tracker `_hits` is a dict of IP → deque. When `_prune` clears on `> 20,000` entries, all rate-limit state is lost (DoS for legitimate users). Also, the pruning logic checks `now - q[-1] > RATE_WINDOW` but `q[-1]` is the *last* timestamp, not the *oldest*; this may not prune correctly.
- `src/tools/planning.py:438-442`: `calculate_net_worth_tool` uses `json.loads(assets_json)` on user-supplied JSON strings without depth or size limits. Extremely nested JSON could cause unbounded parsing, though mitigated by the 16 KB body cap at the web layer.
- `src/web/server.py:48-49`: `CALCULATORS` hard-codes functions from `tvm`, `debt`, `mutual_funds`, `india_savings`, `advisor`. If new calculators are added to tool modules but not added to this registry, the website calculator will not expose them.
- `src/tools/planning.py:688-691`: `calculate_insurance_need_tool` uses a hard-coded `discount_rate = 0.06` with no configuration or input parameter, which may produce incorrect results for users in different economic environments.
- `src/web/server.py:207-218`: Input sanitization silently drops booleans typed as `True`/`False` by the JSON parser (they are handled, but the logic is: silently drop `None` and nested structures; booleans are kept). Not a risk per se, but the comment "silently drop nulls / nested structures" means some invalid inputs produce no error.

## Not Determined

- Exact test file content and test coverage details (only counts known: 12 files, 137 tests per README).
- Content of documentation files (`docs/HOW_IT_WORKS.md`, `docs/deployment.md`, `docs/Architecture.md`, `docs/testing.md`, `docs/setup.md`).
- What the `src/tools/__init__.py` exports or imports (not provided).
- Specific dependency versions beyond what `pyproject.toml` declares.
- Whether `ruff` linting is configured beyond `src/tools/planning.py:421` (`# ruff: noqa: E402`).