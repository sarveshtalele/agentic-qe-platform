# File & Module Guide — Agentic QE Platform

This document describes **every file and module** in the repository, explaining its exact purpose, architectural role, internal mechanisms, and security controls.

---

## Workspace Structure Overview

```
atlas-ba-mvp/
├── src/
│   ├── frontend/         # Next.js 16 + React 19 + Tailwind CSS v4 Web Application
│   └── backend/          # FastAPI + Microsoft Agent Framework (MAF) Engine
├── tests/                # Full Pytest Test Suite (Unit, Integration, E2E)
├── docs/                 # Architectural, Governance, and Module Documentation
├── data/                 # SQLite database, cryptographic audit ledger, documents
├── workspaces/           # Isolated sandbox environments for feature code & git repos
├── scripts/              # Shell automation scripts for execution and testing
├── package.json          # Root orchestration runner for frontend, backend, and tests
├── pytest.ini            # Pytest configuration with pythonpath = ["src"]
└── requirements.txt      # Python dependencies for backend and MAF agents
```

---

## 1. Backend Core (`src/backend/`)

| File / Module | Purpose | How It Works & Key Mechanisms |
|---|---|---|
| [`src/backend/app.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/app.py) | **Main FastAPI Application & Entrypoint** | Initializes SQLite schema, registers routers, mounts CORS middleware, sets up upload/export directories, and configures static fallback serving. Dual-writes all top-level project operations to the audit ledger. |
| [`src/backend/logger.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/logger.py) | **Centralized Logging & Real-time Buffer** | Provides `agentic_qe` logger with custom `InMemoryLogHandler` holding a circular buffer of 1,000 recent logs for the Observability UI. Also persists to `data/sdlc.log`. |
| [`src/backend/database.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/database.py) | **Database Layer & Schema Migrations** | Manages SQLite connection factory with WAL (Write-Ahead Logging) mode, foreign key enforcement, row factory dictionaries, and table creation (`projects`, `documents`, `requirements`, `user_stories`, `test_cases`, `test_runs`, `quality_gates`). |
| [`src/backend/routes_agentic_qe.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/routes_agentic_qe.py) | **Agentic-QE & Greenfield Studio Endpoints** | Exposes endpoints for BRD/PRD synthesis, Gherkin conversion, Word/Markdown/Feature downloads, document versioning (`POST /save-document`, `GET /versions`), feature branching, error traceback diagnosis, real GitHub ingestion, and live telemetry. |
| [`src/backend/routes_maf_governance.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/routes_maf_governance.py) | **Quality Engineering & Governance Routes** | Exposes endpoints for 5 Quality Gates, risk test strategy (`/qe/strategy`), ISTQB 4-oracle test design (`/qe/design`), pytest synthesis (`/qe/synthesize`), sandboxed execution (`/qe/execute`), confidence review (`/qe/review`), and HITL resolution. |
| [`src/backend/routes.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/routes.py) | **Brownfield SDLC & Artifact Routes** | Handles document uploads, raw text extraction, requirement ingestion, story-test traceability matrices, and safe project zip exports. |

---

## 2. Microsoft Agent Framework Subsystem (`src/backend/maf/`)

| File / Module | Purpose | How It Works & Key Mechanisms |
|---|---|---|
| [`src/backend/maf/core.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/core.py) | **MAF Foundation & Pregel Superstep Engine** | Implements `AIAgent` base class, `AgentSession` state store, immutable `Message` dataclass, and `PregelEngine`. Supports cyclic graphs, barrier synchronization, and `HITLInterrupt` exceptions when human input is mandated. |
| [`src/backend/maf/workflows.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/workflows.py) | **Workflow Patterns** | Provides builders for Sequential, Concurrent (parallel execution), and Dynamic Handoff workflows matching `agent-framework.pdf` Chapter 4. |
| [`src/backend/maf/evaluation.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/evaluation.py) | **Outside Judge & Evaluation Suite** | Implements `AgentEvaluationSuite` and `CompositeEvaluator` (`agent-framework.pdf` p. 220–227). Runs 4 deterministic evaluators (`CompletenessEvaluator`, `GroundTruthQuoteEvaluator`, `SyntaxEvaluator`, `SecurityInvariantEvaluator`) so models never grade their own homework. |
| [`src/backend/maf/agents/analysts.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/agents/analysts.py) | **Requirements Analyst & Repo Intelligence** | `RequirementsAnalystAgent` parses stakeholder briefs into atomic business rules (BR-001–BR-006). `RepoIntelligenceAgent` inspects codebases, identifies framework stacks, and assesses defect risk. |
| [`src/backend/maf/agents/doc_reviewer.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/agents/doc_reviewer.py) | **Lead Document Reviewer & Auditor** | Dynamically audits business documents across 5 dimensions: Completeness, Testability, Feasibility, Security, and Atomic Rule Numbering. Generates actionable feedback and dimension scores out of 100. |
| [`src/backend/maf/agents/feature_builder.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/agents/feature_builder.py) | **Feature Builder & Interactive Debugger** | `FeatureBuilderAgent` scaffolds stack-accurate code and creates isolated git branches. `InteractiveDebuggerAgent` parses traceback stack traces via AST, locates root cause line faults, and synthesizes defensive patches. |
| [`src/backend/maf/agents/qe.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/agents/qe.py) | **Quality Engineering Agents** | Contains 4 specialized agents: `PrincipalTestArchitectAgent` (strategy), `TestDesignEngineerAgent` (4 ISTQB oracles), `TestAutomationEngineerAgent` (pytest synthesis), and `QAExecutionEngineerAgent` (real sandboxed pytest subprocess runner). |
| [`src/backend/maf/agents/confidence.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/agents/confidence.py) | **Confidence Reviewer Agent** | Evaluates composite deployment readiness score across 5 quality gates before Gate 5 sign-off. |
| [`src/backend/maf/agents/orchestrator.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/agents/orchestrator.py) | **Magentic Orchestrator Agent** | Coordinates multi-agent handoffs and task decomposition across the full SDLC lifecycle. |

---

## 2.1 MAF Executable Agent Skills (`src/backend/maf/skills/`)

All 11 skills ported from `sarveshtalele/agentic-qe` into Python adhering to Microsoft Agent Framework:

| Skill Class & File | Registered Skill Name | Category | Core Mechanics |
|---|---|---|---|
| `RepoAnalysisSkill` ([`repo_analysis.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/skills/repo_analysis.py)) | `analyzing_repositories` | `Discovery` | Deep filesystem traversal detecting Astro, Node, Python, .NET stack signals and test file ratios. |
| `RequirementsContractSkill` ([`requirements.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/skills/requirements.py)) | `extracting_requirements` | `Requirements` | Parses briefs into atomic verifiable requirements with line numbers and ground-truth evidence quotes. |
| `RiskCalculationSkill` ([`risk_planning.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/skills/risk_planning.py)) | `planning_tests` | `TestPlanning` | Computes ISO 25010 risk profile, controls covered (0-40), level fit (0-30), scenarios derivable (0-30). |
| `TestCaseDesignSkill` ([`test_design.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/skills/test_design.py)) | `designing_test_cases` | `TestDesign` | Designs ISTQB test cases declaring deterministic oracles and Gherkin Given/When/Then scenarios. |
| `TestCodeEmissionSkill` ([`test_code_emission.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/skills/test_code_emission.py)) | `generating_test_code` | `TestAutomation` | Emits syntax-verified executable Pytest and Playwright test source code. |
| `IsolatedTestExecutionSkill` ([`isolated_execution.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/skills/isolated_execution.py)) | `executing_tests` | `TestExecution` | Spawns sandboxed subprocess with timeout, parsing pass/fail counts and terminal logs. |
| `TestHealingSkill` ([`test_healing.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/skills/test_healing.py)) | `healing_tests` | `TestHealing` | Enforces Assertion Preservation Rule: repairs selector drift while preserving test integrity. |
| `TraceabilityMatrixSkill` ([`traceability.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/skills/traceability.py)) | `tracing_coverage` | `Traceability` | Constructs bidirectional requirement-to-testcase matrix and computes coverage percentage. |
| `TestDataSynthesisSkill` ([`test_data.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/skills/test_data.py)) | `generating_test_data` | `TestData` | Synthesizes deterministic persona fixtures (valid/invalid tokens, user payloads). |
| `UserStoryAuthoringSkill` ([`user_stories.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/skills/user_stories.py)) | `authoring_user_stories` | `Agile` | Generates INVEST-compliant user stories in Role-Action-Benefit format with acceptance criteria. |
| `QEDashboardSkill` ([`qe_dashboard.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/maf/skills/qe_dashboard.py)) | `building_qe_dashboard` | `Reporting` | Generates stamped Quality Gate markdown compliance reports with SHA-256 ledger proof. |


---

## 3. Governance, Security & Audit Ledger (`src/backend/governance/`)

| File / Module | Purpose | How It Works & Key Mechanisms |
|---|---|---|
| [`src/backend/governance/ledger.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/governance/ledger.py) | **Tamper-Evident SHA-256 Audit Ledger** | Implements immutable cryptographic hash chaining (`CTL-DOC-04`, `CTL-SEC-01`). Every entry hashes the previous block's SHA-256 digest, actor, action, and payload. `verify_chain()` detects any line-level tampering or out-of-sequence insertion. |
| [`src/backend/governance/gate_controller.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/governance/gate_controller.py) | **Quality Gate Controller (G0–G5)** | Enforces strict prerequisite state transitions: Gate 0 (Ingestion) $\to$ Gate 1 (Requirements) $\to$ Gate 2 (Architecture) $\to$ Gate 3 (Design) $\to$ Gate 4 (Execution) $\to$ Gate 5 (Cutover). |
| [`src/backend/governance/hitl.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/governance/hitl.py) | **Human-in-the-Loop (HITL) Manager** | Manages approval requests, enforces cryptographic single-use nonces, prevents replay attacks, and records operator approvals or rejections to the ledger. |
| [`src/backend/governance/guards.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/governance/guards.py) | **Subprocess & Path Traversal Guards** | Enforces `CTL-SEC-02` (blocks `rm -rf`, `sudo`, destructive commands) and `CTL-SEC-04` (blocks `../` directory escapes and writing outside workspace root). |
| [`src/backend/governance/secret_scanner.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/governance/secret_scanner.py) | **Shannon Entropy & Secret Detector** | Scans all payloads, files, and logs for high-entropy secrets, API keys (`sk-...`, `ghp_...`), private keys (`id_rsa`), and tokens before they reach logs or database. |

---

## 4. Business Analysis & Export Engines (`src/backend/ba/`)

| File / Module | Purpose | How It Works & Key Mechanisms |
|---|---|---|
| [`src/backend/ba/doc_generator.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/ba/doc_generator.py) | **Greenfield Document & Gherkin Generator** | Synthesizes 7-section enterprise BRDs/PRDs. `to_gherkin()` converts user personas and business rules into executable Gherkin syntax tagged with `@enterprise @governed`. `export_docx()` builds genuine Office Open XML binary packages. `export_md()` builds formatted GitHub Flavored Markdown. |
| [`src/backend/ba/doc_reviewer.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/ba/doc_reviewer.py) | **Rule Verification & Score Calculator** | Validates document completeness against ISO/IEC 25010 standards and ISTQB oracle baselines. |

---

## 5. Integrations & LLM Clients (`src/backend/github/` & `src/backend/llm/`)

| File / Module | Purpose | How It Works & Key Mechanisms |
|---|---|---|
| [`src/backend/github/client.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/github/client.py) | **Real GitHub Client** | Connects to GitHub API v3. Fetches real public/private repositories, default branches, recent commit logs, file trees, and language statistics. Creates real branches and pull requests when configured with personal access tokens. Strictly reports 404/auth errors with zero mock fallback. |
| [`src/backend/llm/client.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/backend/llm/client.py) | **Dynamic Multi-Provider LLM Client** | Connects to Azure LiteLLM proxy, OpenAI, Anthropic, or local endpoints configured in `PlatformSettings`. Reads credentials from `data/settings.json`. Strict zero-mock enforcement: raises descriptive `LLMNotConfiguredError` if endpoint is unconfigured. |

---

## 6. Frontend Application (`src/frontend/`)

| File / Component | Purpose | Key Capabilities |
|---|---|---|
| [`src/frontend/app/page.tsx`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/frontend/app/page.tsx) | **Single-Page Application Root** | Manages application state, active project workspace, quality gate status, audit trail, view routing, notifications, and SSE stream listeners. |
| [`src/frontend/app/globals.css`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/frontend/app/globals.css) | **Global Styling & Accessibility** | Tailwind CSS v4 design tokens. Defines universal high-contrast selection rules (`#ffffff` on `#2563eb`), dark/light theme variables, and scrollbar styling. |
| [`src/frontend/components/Header.tsx`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/frontend/components/Header.tsx) | **Top Navigation & Quality Gate Ribbon** | Displays project selector, New Project button, Copilot drawer trigger, dark/light theme toggle, active LLM model badge, and real-time Quality Gate status (G0–G5). |
| [`src/frontend/components/Sidebar.tsx`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/frontend/components/Sidebar.tsx) | **Collapsible Navigation Rail** | Supports 2 modes: 240px expanded navigation with icon and labels, and 64px compact icon-only rail with tooltip hover. |
| [`src/frontend/components/views/GreenfieldBAStudio.tsx`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/frontend/components/views/GreenfieldBAStudio.tsx) | **BA Document Studio & Gherkin Editor** | 4-tab switcher: Structured Sections, Gherkin BDD (.feature), Markdown (.md), and Version History. Features inline rich table editing, Save & Version workflow, and multi-format exports (.docx, .md, .feature). |
| [`src/frontend/components/views/FeatureStudio.tsx`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/frontend/components/views/FeatureStudio.tsx) | **Autonomous Feature Builder & Debugger** | Synthesizes framework-accurate feature code, displays terminal execution logs, features interactive error chat for traceback pasting and automated AST patch application, and triggers GitHub PR creation. |
| [`src/frontend/components/views/RepositoryHub.tsx`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/frontend/components/views/RepositoryHub.tsx) | **GitHub & Local Repo Ingestion** | Fetches live GitHub repos, renders dossier cards (languages, branches, commits, file trees), and provides 4-action switchboard routing. |
| [`src/frontend/components/views/QETestStudio.tsx`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/frontend/components/views/QETestStudio.tsx) | **Quality Engineering & Oracles Studio** | Manages 5 testing tabs: Test Strategy (Gate 2), 4-Oracle Test Design (Gate 3), Pytest Synthesizer, Sandboxed Runner (Gate 4), and Confidence Review (Gate 5). |
| [`src/frontend/components/views/BugDiagnostic.tsx`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/frontend/components/views/BugDiagnostic.tsx) | **Code Scanner & Regression Fixer** | Displays static analysis findings, vulnerability severity badges, automated regression patches, and verification status. |
| [`src/frontend/components/views/HITLGovernance.tsx`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/frontend/components/views/HITLGovernance.tsx) | **Audit Ledger & Approval Center** | Real-time SHA-256 audit ledger inspection, single-click ledger verification, and HITL pending approval cards with single-use nonces. |
| [`src/frontend/components/views/Observability.tsx`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/frontend/components/views/Observability.tsx) | **Telemetry & Live Execution Traces** | Live MAF topology diagram, execution trace cards with child latency spans, token consumption charts, and system log inspector. |
| [`src/frontend/components/views/PlatformSettings.tsx`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/frontend/components/views/PlatformSettings.tsx) | **Credentials & Endpoint Configuration** | Configures Custom LLM Base URL, API Key, Model Identifier, and GitHub Personal Access Token with live connectivity test button. |
| [`src/frontend/components/CopilotDrawer.tsx`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/src/frontend/components/CopilotDrawer.tsx) | **AG-UI Copilot Stream Drawer** | Slides out from right to show real-time agent thought steps, tool invocations, token telemetry, and stream events via SSE. |

---

## 7. Tests (`tests/`)

| Test File | Coverage & Assertions |
|---|---|
| [`tests/test_nextjs_e2e_playwright.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/tests/test_nextjs_e2e_playwright.py) | **11 Next.js Playwright E2E Tests**: Tests branding, collapsible sidebar, zero-mock project creation, GitHub fetching, BA studio with Gherkin and docx downloads, Feature Builder auto-patching, Bug Diagnostic, QE Hub, HITL ledger verification, Observability traces, Platform Settings, and Copilot Stream. |
| [`tests/test_e2e_playwright.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/tests/test_e2e_playwright.py) | **9 Static UI E2E Tests**: Tests full navigation, sidebar rail toggle, Home GitHub connect, BRD generation, feature debugging, QE lifecycle, and ledger verification. |
| [`tests/test_maf_unit.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/tests/test_maf_unit.py) | **16 MAF Unit Tests**: Tests Shannon entropy, secret scanner, `guard_write`, `guard_bash`, hash chain determinism, gate controller, HITL flow, JSON patch, stream broker, and Pregel superstep execution. |
| [`tests/test_maf_governance.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/tests/test_maf_governance.py) | **10 Governance Tests**: Tests secret scanning in payloads, destructive bash command blocking, ledger chaining, gate prerequisites, and HITL nonces. |
| [`tests/test_maf_evaluation.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/tests/test_maf_evaluation.py) | **4 Evaluation Tests**: Tests completeness, quote verification, syntax validation, composite evaluation, and evaluation REST endpoints. |
| [`tests/test_maf_integration.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/tests/test_maf_integration.py) | **3 Integration Tests**: Tests full governed SDLC lifecycle, workflow run endpoints, and HITL approval lifecycle. |
| [`tests/test_ba_engine.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/tests/test_ba_engine.py) | **4 BA Engine Tests**: Tests BRD/PRD generation, reviewer agent critique, Word .docx, Markdown .md, Gherkin .feature export, and Save Document versioning. |
| [`tests/test_feature_builder.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/tests/test_feature_builder.py) | **3 Feature Builder Tests**: Tests feature code synthesis, interactive debugger AST patch, and feature workflow API lifecycle. |
| [`tests/test_github_client.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/tests/test_github_client.py) | **3 GitHub Client Tests**: Tests unauthenticated fallback, PR creation simulation, and GitHub API endpoints. |
| [`tests/test_api.py`](file:///Users/sarveshtalele/Downloads/atlas-ba-mvp/tests/test_api.py) | **8 Core API Tests**: Tests health checks, project persistence, document uploads, story traceability, and command output redaction. |
