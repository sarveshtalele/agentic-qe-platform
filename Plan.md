# Agentic QE Platform: Master Product Implementation Plan

**Plan Version:** 2.0.0  
**Tracking Mode:** Task IDs (`TSK-xxx`) & Governance Control IDs (`CTL-xxx`)  
**Target Architecture:** Microsoft Agent Framework (MAF) + Agentic-QE Protocol + AG-UI / CopilotKit Protocol  
**Status:** ALL MILESTONES COMPLETED (55/55 Tests Passing: Unit, Integration, Playwright E2E)  

---

## 1. Executive Tracking Summary

| Milestone | Phase Name | Task Count | Status | Associated Control IDs |
| :--- | :--- | :---: | :---: | :--- |
| **M1** | Specification & Architecture Baseline | 3 Tasks | **COMPLETED** | `CTL-GATE-00` - `CTL-GATE-05`, `CTL-AUD-01` |
| **M2** | Database & Persistence Schema Extension | 3 Tasks | **COMPLETED** | `CTL-AUD-01`, `CTL-AUD-02`, `CTL-GATE-00` |
| **M3** | Agentic-QE Governance & Guardrails Engine | 5 Tasks | **COMPLETED** | `CTL-HITL-01`, `CTL-HITL-02`, `CTL-HITL-03`, `CTL-SEC-01`, `CTL-SEC-02` |
| **M4** | MAF Graph & Pregel Multi-Agent Engine | 6 Tasks | **COMPLETED** | `CTL-GATE-01`, `CTL-GATE-02`, `CTL-GATE-03`, `CTL-GATE-04`, `CTL-GATE-05` |
| **M5** | AG-UI Protocol & SSE Streaming Engine | 4 Tasks | **COMPLETED** | `CTL-AUD-02`, `CTL-HITL-03` |
| **M6** | Frontend Multi-Screen UI & Graph Visualizer | 8 Tasks | **COMPLETED** | `CTL-GATE-00` - `CTL-GATE-05`, `CTL-HITL-01` |
| **M7** | End-to-End Workflow & Traceability Integration | 3 Tasks | **COMPLETED** | `CTL-AUD-03`, `CTL-SEC-03` |
| **M8** | Verification, Automated Testing & Playwright | 4 Tasks | **COMPLETED** | All Baseline Controls (42/42 Tests) |
| **M9** | **GitHub Integration & Real Repo Workspaces** | 3 Tasks | **COMPLETED** | `CTL-GIT-01`, `CTL-GIT-02`, `CTL-GIT-03` |
| **M10** | **Greenfield BA Studio (.docx / .md + Reviewer)** | 3 Tasks | **COMPLETED** | `CTL-DOC-01`, `CTL-DOC-02`, `CTL-DOC-03` |
| **M11** | **Feature Builder, Error Pasting & PR Automation** | 3 Tasks | **COMPLETED** | `CTL-FEAT-01`, `CTL-FEAT-02`, `CTL-FEAT-03` |
| **M12** | **Minimalist UI Refactor (Icons Rail & Home Switchboard)** | 3 Tasks | **COMPLETED** | `CTL-UI-01`, `CTL-UI-02` |
| **M13** | **Product Verification & Extended E2E Browser Tests** | 4 Tasks | **COMPLETED** | All Product Controls (55/55 Tests) |

---

## 2. Detailed Task Breakdown & Control Mapping

### Phase 9: GitHub Integration & Real Repo Workspaces (M9)

#### `TSK-201`: GitHub REST API Client & Repository Fetcher
- **Scope**: Authenticate with GitHub using PAT or environment credentials. List user repositories, branches, commits, and tree structures. Provide fallback to local git repository exploration when offline.
- **Associated Controls**: `CTL-GIT-01`, `CTL-GIT-02`.
- **Target File**: `backend/github/client.py`.
- **Verification**: `pytest tests/test_github_client.py`.

#### `TSK-202`: Automated Pull Request Creation & Merge Engine
- **Scope**: Push git branches to GitHub, format Pull Request titles and descriptions with acceptance criteria checklists, and execute PR merge API calls with squash/commit options.
- **Associated Controls**: `CTL-GIT-03`.
- **Target File**: `backend/github/client.py`.
- **Verification**: Tested in integration tests.

---

### Phase 10: Greenfield BA Studio (.docx / .md + Reviewer Agent) (M10)

#### `TSK-203`: Enterprise BRD & PRD Document Generator
- **Scope**: Strict document generators for BRD (7 enterprise sections, numbered `BR-001`+ business rules) and PRD (user journeys, API contracts, release phases).
- **Associated Controls**: `CTL-DOC-01`.
- **Target File**: `backend/ba/doc_generator.py`.
- **Verification**: `pytest tests/test_ba_engine.py`.

#### `TSK-204`: Autonomous Document Reviewer Agent & Refinement
- **Scope**: Autonomous Reviewer Agent scoring documents across 5 dimensions (0-100 total), generating actionable critiques, and iteratively rewriting/refining documents.
- **Associated Controls**: `CTL-DOC-02`.
- **Target File**: `backend/maf/agents/doc_reviewer.py`.
- **Verification**: `pytest tests/test_ba_engine.py`.

#### `TSK-205`: Real Microsoft Word (`.docx`) & Markdown Exporter
- **Scope**: Uses `python-docx` to synthesize styled Microsoft Word binary files (`.docx`) with headings, tables, and metadata blocks, alongside clean UTF-8 `.md` files.
- **Associated Controls**: `CTL-DOC-03`.
- **Target File**: `backend/ba/doc_generator.py`.
- **Verification**: Verify binary file generation and MIME types in tests.

---

### Phase 11: Feature Builder, Error Pasting & PR Automation (M11)

#### `TSK-206`: Autonomous Feature Builder & Code Synthesizer
- **Scope**: Ingests BA specifications, creates dedicated feature branches, generates source code, runs sandboxed tests, and enforces write guardrails.
- **Associated Controls**: `CTL-FEAT-01`.
- **Target File**: `backend/maf/agents/feature_builder.py`.
- **Verification**: `pytest tests/test_feature_builder.py`.

#### `TSK-207`: Interactive Copilot Error Pasting & Patch Engine
- **Scope**: Chat endpoint accepting pasted error stack traces and failing test logs, diagnosing root causes, generating code patches, and re-running test suites.
- **Associated Controls**: `CTL-FEAT-02`.
- **Target File**: `backend/maf/agents/feature_builder.py`.
- **Verification**: `pytest tests/test_feature_builder.py`.

#### `TSK-208`: Local Testable ZIP Exporter with Manifest
- **Scope**: Packages modified repository code and test files into a ZIP archive for local developer testing before PR submission.
- **Associated Controls**: `CTL-FEAT-03`.
- **Target File**: `backend/ba/doc_generator.py`.
- **Verification**: Validate ZIP archive contents and checksums.

---

### Phase 12: Minimalist UI Refactor (Icons Rail & Home Switchboard) (M12)

#### `TSK-301`: Collapsible Rail (Icons-Only 64px vs Expanded 260px)
- **Scope**: Responsive sidebar toggle between 64px icons-only rail and 260px expanded sidebar with localStorage persistence, SVG icons, and hover tooltips.
- **Associated Controls**: `CTL-UI-01`.
- **Target Files**: `frontend/styles.css`, `frontend/app.js`.
- **Verification**: Playwright browser test asserts class changes and widths.

#### `TSK-302`: Home Hub Screen with GitHub Card & 4-Action Switchboard
- **Scope**: Redesigned Home page with GitHub token input, repository selector dropdown, and 4 primary action cards (Feature, Bug Fix, Test Hub, Greenfield BA).
- **Associated Controls**: `CTL-UI-02`.
- **Target Files**: `frontend/app.js`.
- **Verification**: Playwright browser test clicks through switchboard.

#### `TSK-303`: Greenfield BA Document Studio Screen
- **Scope**: Live document editor and previewer, Reviewer Agent critique drawer, 1-click Refine action, and instant `.docx` / `.md` download buttons.
- **Associated Controls**: `CTL-DOC-01`, `CTL-DOC-02`.
- **Target Files**: `frontend/app.js`.
- **Verification**: Playwright browser test tests generation and download.

#### `TSK-304`: Feature Implementation & Error Chat Screen
- **Scope**: Workspace view with terminal, diff preview, error log paste box, local test ZIP download button, and GitHub PR modal.
- **Associated Controls**: `CTL-FEAT-01`, `CTL-FEAT-02`.
- **Target Files**: `frontend/app.js`.
- **Verification**: Playwright browser test tests paste and patch.

---

### Phase 13: Product Verification & Extended E2E Browser Tests (M13)

#### `TSK-401` - `TSK-404`: Comprehensive Automated Test Suite
- **Scope**: Run unit tests, integration tests, and Playwright Chromium E2E browser tests across all new modules and user stories.
- **Associated Controls**: All Controls.
- **Verification**: 100% test pass rate across all suites.
