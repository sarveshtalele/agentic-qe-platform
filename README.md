# Agentic QE Platform — Autonomous SDLC & Quality Engineering

An enterprise-grade, autonomous software development lifecycle (SDLC) platform powered by **Microsoft Agent Framework (MAF)** and **Agentic Quality Engineering (QE)**.

The platform coordinates specialized autonomous AI agents across 6 strict quality gates, from greenfield business requirements synthesis to brownfield repository ingestion, autonomous feature engineering, runtime debugging, Gherkin BDD specifications, and tamper-evident SHA-256 governance.

---

## 🏛️ Modular Repository Architecture

The platform is organized with clean separation between frontend, backend, tests, and documentation:

```
atlas-ba-mvp/
├── src/
│   ├── frontend/         # Next.js 16 + React 19 + Tailwind CSS v4 Web Application
│   │   ├── app/          # App router, page layouts, global styling (high contrast)
│   │   └── components/   # Views: BA Studio, Feature Studio, QE Hub, Settings, etc.
│   └── backend/          # FastAPI + Microsoft Agent Framework (MAF)
│       ├── app.py        # Main API entrypoint & static mounting
│       ├── maf/          # MAF Core, Pregel Engine, Agents, Workflows & Evaluators
│       ├── governance/   # SHA-256 Cryptographic Audit Ledger, Gates G0-G5, HITL
│       ├── ba/           # Greenfield Requirements Generator & Gherkin BDD Engine
│       ├── qe/           # Quality Engineering Runner & ISTQB Oracles
│       ├── github/       # Real Octokit-compatible GitHub Client
│       └── llm/          # Multi-provider LLM Client (LiteLLM, Azure, Anthropic)
├── tests/                # Comprehensive Pytest Suite (Unit, Integration, E2E)
├── docs/                 # System Architecture, File Guide & MAF Reference
│   ├── ARCHITECTURE.md   # System architecture and agent topology
│   ├── FILES_AND_MODULES.md # Line-by-line guide to every file in the codebase
│   └── AMBITION_CHECKLIST.md# Felix Rieseberg Ambition Framework (Altitude, Depth, Range)
├── data/                 # SQLite database, cryptographic audit ledger, documents
├── workspaces/           # Isolated sandbox environments for feature code & git repos
├── package.json          # Root orchestration runner for frontend, backend, and tests
├── pytest.ini            # Pytest configuration with pythonpath = ["src"]
└── requirements.txt      # Python dependencies for backend and MAF agents
```

---

## 🚀 Quickstart & Execution

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ (Next.js 16)
- GitHub Personal Access Token (for repository ingestion & PR creation)

### 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/sarveshtalele/agentic-qe-platform.git
cd agentic-qe-platform

# Setup Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Setup Frontend dependencies
cd src/frontend && npm install && cd ../..
```

### 3. Running the Platform
Using root orchestration scripts:
```bash
# Terminal 1: Start Backend (FastAPI on Port 8000)
npm run start:backend
# Or: PYTHONPATH=src .venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000

# Terminal 2: Start Frontend (Next.js on Port 3000)
npm run start:frontend
# Or: cd src/frontend && npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to access the platform.

---

## 🧪 Comprehensive Verification & Test Suite

The test suite covers unit tests, MAF agent evaluation suites, governance gates, and Playwright end-to-end scenarios:

```bash
# Run full test suite (70 tests)
npm run test
# Or: .venv/bin/pytest tests/ -v

# Run MAF unit & evaluation tests
npm run test:unit
# Or: .venv/bin/pytest tests/test_maf_unit.py tests/test_maf_governance.py tests/test_maf_evaluation.py -v

# Run Playwright E2E browser tests (Next.js & static fallback)
npm run test:e2e
# Or: .venv/bin/pytest tests/test_nextjs_e2e_playwright.py tests/test_e2e_playwright.py -v
```

---

## 🛡️ Enterprise Governance & Security Controls

- **CTL-DOC-04**: Immutable versioning of all business specifications with incremental SHA-256 ledger chaining.
- **CTL-SEC-01**: Shannon entropy secret scanning before database or log persistence.
- **CTL-SEC-02**: Subprocess command whitelist blocking destructive shell operations (`rm -rf`, `sudo`).
- **CTL-SEC-04**: Path traversal boundary guards preventing directory escape outside project workspaces.
- **CTL-GATE-05**: Human-in-the-Loop (HITL) cryptographic nonce authorization required before production cutover.
