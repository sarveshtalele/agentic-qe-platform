# Agentic QE Platform — Autonomous SDLC & Quality Engineering

An enterprise-grade, autonomous software development lifecycle (SDLC) platform powered by **Microsoft Agent Framework (MAF)** and **Agentic Quality Engineering (QE)**.

The platform coordinates specialized autonomous AI agents across 6 strict quality gates, from greenfield business requirements synthesis to brownfield repository ingestion, autonomous feature engineering, runtime debugging, and tamper-evident SHA-256 governance.

---

## 🏛️ Core Architectural Components

### 1. Microsoft Agent Framework (MAF) Multi-Agent Mesh
- **Repository Ingestion Agent**: Inspects GitHub REST API v3 trees, commits, branches, and detects language stacks (Astro, TypeScript, Python, etc.).
- **Greenfield BA Document Studio**: Synthesizes 7-section Enterprise BRDs, 6-section PRDs, and User Stories dynamically tailored to specific domains (calculators, websites, enterprise APIs) with zero canned mock leakage.
- **Document Reviewer Agent**: Evaluates specifications across 5 quality dimensions (Completeness, Clarity, Testability, Edge Cases, Security Constraints) and proposes automated document refinements.
- **Feature Builder Agent**: Scaffolds isolated feature branches, writes framework-accurate code, and executes syntax and AST verification.
- **Interactive Debugger Agent**: Ingests runtime tracebacks and error logs, diagnoses root causes, and generates verified unified diff patches.
- **MAF Composite Evaluator**: Evaluates multi-agent performance across 4 standard dimensions (Faithfulness, Completeness, Context Relevancy, Groundedness) with aggregate quality scoring.

### 2. Six-Gate Governance & Audit Ledger
- **Gate 0 (Repo Ingested)**: AST parsed, complexity mapped, zero high-entropy secrets.
- **Gate 1 (Requirements Baseline)**: BRD/PRD reviewed by Document Reviewer Agent (Score ≥ 80).
- **Gate 2 (Test Design Sign-off)**: Risk analysis, boundary test cases generated.
- **Gate 3 (Test Execution Passed)**: Verification passes with zero regressions.
- **Gate 4 (Static Analysis / AST Clean)**: Zero syntax or structural AST violations.
- **Gate 5 (HITL Authorization)**: Human-in-the-Loop cryptographic non-repudiation sign-off.
- **Dual-Write Cryptographic Ledger**: SHA-256 hash chains (`prev_hash` -> `entry_hash`) recorded simultaneously to SQLite and append-only `ledger.jsonl`.

### 3. Real GitHub Integration
- Live authentication with GitHub Personal Access Tokens (`gho_...`).
- Automated branch creation (`create_branch_and_commit_files`).
- Direct file commits via GitHub Contents API.
- Pull request opening and mainline merge automation.

### 4. End-to-End Structured Logging & Observability
- Dual-logging file handler (`sdlc.log`) and in-memory ring buffer (1000 items).
- Monospace terminal log viewer with real-time polling, level filtering (ALL, INFO, WARNING, ERROR), and clipboard copy.
- Request-level timing, LLM request/response token tracking, and GitHub API auditing.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+ (Next.js 16)
- GitHub CLI (`gh`) or GitHub Personal Access Token

### Backend Setup (FastAPI + MAF)
```bash
cd sdlc-mvp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend Setup (Next.js 16 + React 19 + TailwindCSS)
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

---

## 🧪 Testing & Verification
```bash
cd sdlc-mvp
.venv/bin/pytest tests/ -v
```
All unit tests, MAF agent evaluation suites, and Playwright end-to-end scenarios run with 100% pass rates.
