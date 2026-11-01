## Purpose and Users
This project is a deterministic personal-finance toolkit exposed as an MCP (Model Context Protocol) server and a web application. It provides calculators covering time value of money, debt, financial planning, Indian small savings schemes (PPF/SSY/NSC), mutual funds, bonds, derivatives, portfolio analytics, and live market data. It also includes a meta-advisor orchestrator (`create_financial_plan`) that chains relevant calculators into a prioritized plan.

**Users** access it in three ways:
1.  **MCP Clients** (Claude Desktop, Claude Code, Cursor, VS Code) connect via **streamable-HTTP** to a hosted connector URL or via **stdio** to a local process (`src/server.py`).
2.  **Web Users** visit a Next.js website for a calculator, tool catalog, market dashboard, and setup guide.
3.  **API Users** call `/api/*` JSON endpoints for individual calculations or market data.

## How It Runs End to End
The system operates in two primary modes: MCP and Web.

**MCP Request Flow (e.g., Claude Desktop):**
1.  **Entry:** A user asks Claude a financial question.
2.  **Client:** The MCP client (Claude Desktop) sends a request to the server via the `/mcp` endpoint over streamable-HTTP.
3.  **Server (`src/web/server.py`):** The Starlette app receives the request. The `SecurityMiddleware` (line 132) checks rate limits and injects security headers.
4.  **MCP Core (`src/server.py`):** The request is routed to the `FastMCP` instance. The LLM's server instructions (line 31-73 of `src/server.py`) guide it to route intent to the appropriate tool.
5.  **Tool Execution:** The `FastMCP` instance calls the registered `@mcp.tool` function (e.g., `plan_retirement_tool` in `src/tools/planning.py:551`).
6.  **Pure Function:** The MCP tool wrapper calls a pure math function (e.g., `inflation_adjusted_amount` from `src/tools/tvm.py` and `required_monthly_savings`).
7.  **Response:** The tool returns a formatted string, the `FastMCP` packages it as an MCP response, and it flows back through the middleware to the client.

**Web UI Request Flow (e.g., SIP Calculator):**
1.  **Entry:** A user on the website visits `/calculator` and fills out a form.
2.  **Frontend (`web/app/calculator/page.js`):** The Next.js frontend sends a JSON POST request to `/api/calc` on the same server.
3.  **API Route (`src/web/server.py`):** The `run_calc` handler (line 243) receives the request. `_sanitize_params` (line 196) validates and caps all inputs for security.
4.  **Calculator Registry:** The handler looks up the calculator function (e.g., `mutual_funds.sip_calculator`) in the `CALCULATORS` dict (line 37).
5.  **Pure Function:** The same pure math function from the tools module is called with sanitized parameters.
6.  **Response:** The result is returned as a JSON response.

## Architecture
The system has a modular, layered architecture designed for reuse across three interfaces (MCP, Web UI, JSON API).

```mermaid
graph TD
    Client[MCP Client e.g., Claude] -->|streamable-HTTP or stdio| WS1[src/web/server.py or src/server.py]
    User -->|Browser| WS1
    API_Caller -->|REST| WS1

    subgraph "Web Layer (src/web/)"
        WS1(Starlette App) --> SM[SecurityMiddleware]
        SM --> MCP_Routes
        SM --> API_Routes
        SM --> Static[Served Next.js Site]
    end

    subgraph "MCP Layer (src/)"
        MCP_Routes --> FM[FastMCP Instance in src/server.py]
        FM --> Tool_Registry[register()]
    end

    subgraph "Tool Layer (src/tools/)"
        Tool_Registry --> tvm.py
        Tool_Registry --> debt.py
        Tool_Registry --> planning.py
        Tool_Registry --> mutual_funds.py
        Tool_Registry --> marketdata.py
        Tool_Registry --> ...
    end

    subgraph "Pure Functions"
        tvm.py --> f_calc{Deterministic Math}
        debt.py --> f_calc
    end

    subgraph "Shared Models (src/models/)"
        f_calc --> schemas.py
    end

    subgraph "Frontend (web/)"
        Static --> Next[Next.js App]
        Next --> Client_API[/api/calc/]
        Client_API --> API_Routes
    end

    subgraph "Data Sources"
        marketdata.py --> AMFI[AMFI Mutual Fund NAVs]
        marketdata.py --> ECB[ECB FX Rates]
        marketdata.py --> Yahoo[Yahoo Finance Quotes]
    end
```

## Modules

| Path | Responsibility | Dependencies |
| :--- | :--- | :--- |
| `src/server.py` | Initializes the `FastMCP` server, registers all tool modules, and provides a `main()` for stdio transport. | `mcp[cli]`, `pydantic`, all `src/tools/*` modules |
| `src/web/server.py` | Unified Starlette ASGI app that serves MCP (`/mcp`), a JSON API (`/api/*`), and a static Next.js site (`/`). Includes security middleware (rate limiting, body caps, CSP headers). | `starlette`, `uvicorn`, `httpx`, `src/server.py`, `src/tools/*` |
| `src/web/__main__.py` | Entry point for the web server (`python -m src.web`). | `src.web.server` |
| `src/__main__.py` | Entry point for the stdio MCP server (`python -m src`). | `src.server` |
| `src/tools/tvm.py` | Time Value of Money pure functions (future_value, present_value, annuity, perpetuity, EAR). | Standard library |
| `src/tools/debt.py` | Debt and loan calculation pure functions (EMI, amortization, prepayment, invest vs. prepay). | Standard library |
| `src/tools/planning.py` | Financial planning and ratio analysis (net worth, budget, emergency fund, health score, retirement, education, insurance). | `src/tools/tvm.py`, `src/utils/formatters`, `mcp` |
| `src/tools/portfolio.py` | Portfolio analytics (expected return, risk, CAPM, Sharpe, Sortino, alpha, allocation). | Standard library |
| `src/tools/mutual_funds.py` | Mutual fund calculators (SIP, SWP, CAGR, expense ratio impact). | Standard library |
| `src/tools/bonds.py` | Fixed income calculators (bond price, YTM, duration, convexity). | Standard library |
| `src/tools/stocks.py` | Equity valuation calculators (DDM, P/E, DCF, dividend yield). | Standard library |
| `src/tools/derivatives.py` | Derivatives calculators (futures, options, Black-Scholes, beta hedge). | Standard library |
| `src/tools/india_savings.py` | Indian small savings scheme calculators (PPF, SSY, NSC, KVP, SCSS, RD, FD, EPF, gratuity). | Standard library |
| `src/tools/cashflow.py` | Cash flow and budgeting tools (statement, debt-to-income, contingency fund). | Standard library |
| `src/tools/risk_profile.py` | Risk profiling score. | Standard library |
| `src/tools/advisor.py` | Orchestrator tool (`create_financial_plan`) that chains other calculators for a user story. | Other `src/tools/*` modules |
| `src/tools/marketdata.py` | Live market data fetchers (mutual fund NAVs, FX rates, stock quotes from public APIs). | `httpx` |
| `src/models/schemas.py` | Pydantic data models for inputs (TVM, Loan, Bond, Portfolio, etc.). | `pydantic`, `src/models/enums` |
| `src/models/enums.py` | Enums for compounding frequency, annuity type, risk profile, etc. | Standard library |
| `src/utils/formatters.py` | Output formatting helpers (currency, percentage, tables). | Standard library |
| `run_production.py` | Alternative entry point for running the MCP server with SSE transport. | `src.server` |
| `web/` | Next.js front-end application (static export). | Node.js, React, Next.js |

## Interfaces

- **MCP over Streamable-HTTP** (`/mcp`): The primary connector endpoint for MCP clients. Exposes all tools registered in `src/server.py`.
- **MCP over stdio**: The `src/__main__.py` entry point provides command-line access via standard input/output.
- **JSON API (REST, via `src/web/server.py`):**
    - `GET /api/health` - Health check.
    - `GET /api/tools` - Lists all tools with categories and descriptions.
    - `POST /api/calc` - Runs a specific calculator from a registry of 15 functions.
    - `GET /api/nav` - Search or get NAV for mutual funds.
    - `GET /api/fx` - Get foreign exchange rates.
    - `GET /api/quote` - Get stock or index quotes.
- **Web UI**: A Next.js site served as static files at the root `/`, featuring pages for home, tools catalog, calculator, dashboard, and MCP connector setup.

## Data and Integrations

The system is **stateless** with no local database. Persistent state is not required.

- **Live Market Data** is fetched on-demand from public, keyless APIs:
    - **Mutual Fund NAVs (`src/tools/marketdata.py`)**: Fetched from AMFI (Association of Mutual Funds in India).
    - **FX Rates**: Fetched from the European Central Bank's Frankfurter API.
    - **Equity Quotes**: Fetched from Yahoo Finance.
- **Failure Mode**: The code shows no explicit caching or fallback for these calls. A failed external API call will likely raise an `httpx` error, which is caught generically by the `run_calc` handler (line 268 of `src/web/server.py`) and returns a generic "calculation failed" error. The MCP tools themselves (e.g., `get_fx_rate` in `src/tools/marketdata.py`) do not have error handling visible in the provided code.
- **Static Files**: The Next.js website is pre-built and served from the `web/out` directory.

## Configuration and Deployment

- **Configuration**: The primary mechanism is a single environment variable, `PORT`, which defaults to `7860` for Hugging Face Spaces. The `run_production.py` script also reads `MCP_HOST` and `MCP_PORT`.
- **Deployment**:
    - **Local**: `pip install -e .` and then `python -m src` (stdio) or `python -m src.web` (web server).
    - **PyPI**: The package `personal-finance-mcp` can be installed and run via `uvx personal-finance-mcp` for stdio.
    - **Docker**: A multi-stage `Dockerfile` builds the Next.js site and then runs the Python web server on port 7860.
    - **CI/CD**: GitHub Actions workflows exist for CI (`ci.yml`), CodeQL scanning (`codeql.yml`), PyPI publishing (`pypi-publish.yml`), and Hugging Face sync (`hf-sync.yml`). The main deployment target is a Hugging Face Docker Space.
- **Build System**: Uses `hatchling` for building and distributing the Python package.

## Existing Tests
The scan detected **12 test files** run by **pytest**. The README states 137 tests in a badge and 119 in a code block. The test directory is `tests/`. Not all source files have test coverage visible from the scan (e.g., `marketdata.py` testing external APIs would require mocking).

- **How to run**: `pytest -q`
- **Mocking Strategy**: Not determined from evidence.

## Risks
- **Inconsistent tool count**: `README.md` states 77 tools while `pyproject.toml` says 76 and the scan found 76 tool functions across source files. This is a documentation inconsistency that could confuse users.
- **No explicit error handling in `src/tools/marketdata.py` for external API failures (AMFI, ECB, Yahoo)**: The web handler at `src/web/server.py:268` catches generic exceptions, but the MCP tools may expose `httpx` exceptions to the LLM directly, which could leak error details or cause confusing behavior for MCP clients.
- **Rate limiting state stored in memory (`_hits` dict at `src/web/server.py:95`)**: The per-IP rate limiting dictionary is stored in a single Python process's memory. Under heavy load with spoofed IPs, this could be a memory-exhaustion vector, and the `_hits.clear()` fallback (line 106) removes rate limits for all IPs.
- **Webserver accesses `mcp._tool_manager._tools` (private API at `src/web/server.py:227, 232`)**: The web API handler accesses this private attribute directly. A future update to the `mcp` library could break this code without notice.

## Not Determined
- **Full content of `src/tools/marketdata.py`**: The exact HTTP calls and error handling for external APIs were not provided.
- **Contents of the `tests/` directory**: The specific test suite structure, coverage, and mocking strategies are unknown.
- **Exact number of tools**: The README states 77 tools, `pyproject.toml` says 76, and the scan found 76 tool functions. The true count cannot be resolved from the provided evidence.
- **All CI workflow logic**: The precise steps in the GitHub Actions workflows (`pypi-publish`, `hf-sync`) are not detailed.
- **Next.js page logic**: The exact logic for the website's calculator page (`web/app/calculator/page.js`) and dashboard (`web/app/dashboard/page.js`) is not examined in detail.