# Agentic QE Platform: Comprehensive User Stories & Test Scenarios

**Document Version:** 2.0.0  
**Product Name:** Agentic QE Platform  
**Architecture:** Microsoft Agent Framework (MAF) + Agentic-QE Protocol + AG-UI / CopilotKit Protocol  
**Scope:** Greenfield Business Analysis, Brownfield Application Synthesis, Autonomous Feature Implementation, Interactive Bug Fixing, GitHub Pull Request Automation, and 6-Gate Quality Engineering.

---

## 1. Persona Taxonomy

| Persona ID | Role | Key Responsibilities | Primary Needs in Platform |
| :--- | :--- | :--- | :--- |
| **PER-01** | **Business Analyst (BA)** | Gathers requirements, defines business rules, drafts BRD/PRDs, breaks down epics into user stories. | Strict enterprise document formatting, automated peer review, missing edge case detection, `.docx` and `.md` downloads. |
| **PER-02** | **Software Developer** | Implements features, refactors legacy codebases, debugs failing tests, builds PRs. | Repository context analysis, automated feature scaffolding, interactive error pasting with auto-patching, downloadable local test ZIPs, automated GitHub PR creation. |
| **PER-03** | **Quality Engineer (QE)** | Designs test architecture, engineers boundary test oracles, ensures continuous quality gates. | ISTQB 4-oracle test design (specified, derived, metamorphic, golden), automated test code synthesis, sandboxed test execution, gate sign-off confidence scores. |
| **PER-04** | **Release Manager / Lead Architect** | Governs production deployments, reviews audit logs, enforces security and compliance barriers. | 6-Gate governance (Gates 0-5), Human-in-the-Loop (HITL) approval gates, SHA-256 tamper-evident cryptographic audit ledger. |

---

## 2. Core User Stories & Test Matrix

### Module 1: Modern Minimal UI & Collapsible Navigation Shell

#### `US-NAV-01`: Adjustable Navigation Sidebar (Icons-Only Rail vs Expanded)
- **Persona:** All Personas
- **Story:**  
  *As a* platform user,  
  *I want to* toggle the left navigation panel between an expanded sidebar (full labels, headers, badges) and a compact icons-only rail (64px width with tooltip guidance),  
  *so that* I can maximize my workspace screen real estate when reviewing code, reading documents, or interacting with agent streams.
- **Acceptance Criteria (Gherkin):**
  ```gherkin
  Given the user is on any screen of the Agentic QE Platform
  When the user clicks the sidebar collapse toggle button ("◀" or icon toggle)
  Then the sidebar transitions smoothly to a 64px width rail showing only icons
  And tooltips display on hover over each icon
  And the collapsed preference is saved to localStorage
  And when the user clicks expand ("▶"), the full sidebar is restored with labels and section headers
  ```
- **Positive Test Scenarios:**
  - `TC-NAV-001`: Click collapse button; verify CSS class `.sidebar-collapsed` is added, sidebar width becomes 64px, labels are hidden.
  - `TC-NAV-002`: Reload page; verify collapsed state persists from `localStorage`.
  - `TC-NAV-003`: Click expand button; verify full sidebar text and section headers reappear.
- **Negative & Boundary Test Scenarios:**
  - `TC-NAV-004`: Fast double-clicking collapse toggle does not cause animation glitches or broken layout.
  - `TC-NAV-005`: In viewport widths under 768px (mobile), sidebar auto-collapses or slides as an overlay without overlapping main content.
- **Integration Test Scenarios:**
  - `TC-NAV-006`: Active project badge and gate status ribbon remain perfectly visible and aligned regardless of sidebar state.
- **Control ID:** `CTL-UI-01`

---

### Module 2: Home Page & GitHub Repository Hub

#### `US-HUB-01`: Connect GitHub Account & Fetch Repositories
- **Persona:** Developer, Quality Engineer
- **Story:**  
  *As a* developer or QE engineer,  
  *I want to* connect my GitHub account using a personal access token (or workspace credential) to fetch my repositories and branches,  
  *so that* agents can directly analyze the repository code, create feature branches, and submit Pull Requests.
- **Acceptance Criteria (Gherkin):**
  ```gherkin
  Given the user is on the Platform Home page
  When the user enters a valid GitHub Personal Access Token (or selects configured GitHub integration)
  And clicks "Connect & Fetch Repositories"
  Then the system authenticates against GitHub REST API (`GET /user/repos`)
  And displays the authenticated user's profile and a searchable repository dropdown
  And allows selecting a repository and branch for analysis
  ```
- **Positive Test Scenarios:**
  - `TC-HUB-001`: Valid GitHub token returns repository list with name, stars, visibility, default branch.
  - `TC-HUB-002`: Selecting a repository triggers background shallow inspection and branch list retrieval.
- **Negative & Boundary Test Scenarios:**
  - `TC-HUB-003`: Invalid or expired GitHub token displays an error toast with exact failure reason (HTTP 401 Unauthorized) without crashing.
  - `TC-HUB-004`: Rate-limited GitHub token (HTTP 403) displays rate limit reset time gracefully.
  - `TC-HUB-005`: Repositories with zero commits or empty branches are handled with an informative empty state.
- **Integration Test Scenarios:**
  - `TC-HUB-006`: Selected GitHub repository coordinates (`owner`, `repo`, `branch`) are stored in project SQLite record and audit ledger (`CTL-AUD-01`).
- **Control ID:** `CTL-SEC-01`, `CTL-AUD-01`

---

#### `US-HUB-02`: Four Core Action Intent Switchboard
- **Persona:** All Personas
- **Story:**  
  *As a* user on the Home page,  
  *I want to* choose between 4 primary execution paths: (1) Add a Feature, (2) Scan Repo Bugs & Bug Fix, (3) Test Feature or Complete GitHub Repo, (4) Greenfield BA Document Studio,  
  *so that* I can immediately launch into the exact autonomous workflow needed.
- **Acceptance Criteria (Gherkin):**
  ```gherkin
  Given the user is on the Home page
  When the user views the Primary Action Switchboard
  Then four distinct cards are presented with clear enterprise descriptions, badges, and action buttons
  And clicking any card routes directly to the specialized workflow with the active repository pre-selected
  ```
- **Positive Test Scenarios:**
  - `TC-HUB-007`: Click "Add a Feature"; transitions to Feature Implementation Studio with upload bay and error chat.
  - `TC-HUB-008`: Click "Scan Repo Bugs"; transitions to Security & Bug Diagnostic view.
  - `TC-HUB-009`: Click "Test Feature or Complete Repo"; transitions to Quality Engineering Hub.
  - `TC-HUB-010`: Click "Greenfield BA Studio"; transitions to Business Requirements & Document Studio.
- **Negative & Boundary Test Scenarios:**
  - `TC-HUB-011`: If no repository is connected when clicking code-dependent actions, system prompts user to connect GitHub or select a local workspace first.
- **Integration Test Scenarios:**
  - `TC-HUB-012`: Routing preserves current project context and gate statuses.
- **Control ID:** `CTL-UI-02`

---

### Module 3: Greenfield BA Document Studio (BRD, PRD, User Stories & Reviewer Agent)

#### `US-BA-01`: Generate Enterprise BRD (Business Requirements Document)
- **Persona:** Business Analyst (BA)
- **Story:**  
  *As a* Business Analyst,  
  *I want to* input business objectives or upload source notes to generate a strictly formatted enterprise BRD,  
  *so that* business stakeholders have a comprehensive specification of objectives, scope, current vs proposed state, business rules, and KPIs.
- **Acceptance Criteria (Gherkin):**
  ```gherkin
  Given the BA has entered raw business requirements or project notes
  When the BA clicks "Generate BRD"
  Then the Requirements Analyst Agent synthesizes a complete BRD conforming to strict enterprise structure:
    | Section | Contents |
    | 1. Executive Summary | Project vision, problem statement, business justification |
    | 2. Stakeholder Matrix | Key personas, roles, responsibilities, RACI |
    | 3. Current vs Proposed State | Process workflows, gap analysis, pain points |
    | 4. Business Scope & Exclusions | In-scope capabilities, out-of-scope boundaries |
    | 5. Functional Business Rules | Numbered business rules (BR-001..BR-nnn) with enforcement |
    | 6. Non-Functional Constraints | Security, compliance, latency, volume assumptions |
    | 7. Success Metrics & KPIs | Quantifiable target metrics and ROI drivers |
  And the document renders in real-time in the viewer
  ```
- **Positive Test Scenarios:**
  - `TC-BA-001`: Input business prompt for e-commerce checkout; agent produces all 7 sections with structured tables and numbered business rules.
- **Negative & Boundary Test Scenarios:**
  - `TC-BA-002`: Submitting blank or whitespace-only requirements shows validation warning.
  - `TC-BA-003`: Extremely large input text (50,000 words) chunks safely without memory exhaustion.
- **Integration Test Scenarios:**
  - `TC-BA-004`: BRD generation event is written to SHA-256 cryptographic audit ledger (`CTL-AUD-01`).
- **Control ID:** `CTL-GATE-01`, `CTL-AUD-01`

---

#### `US-BA-02`: Generate Enterprise PRD (Product Requirements Document)
- **Persona:** Business Analyst, Product Manager
- **Story:**  
  *As a* BA or Product Manager,  
  *I want to* transform business requirements or an approved BRD into an enterprise PRD,  
  *so that* engineering teams have explicit user personas, user journey workflows, feature epics, API schemas, and technical release criteria.
- **Acceptance Criteria (Gherkin):**
  ```gherkin
  Given a project with business requirements or an existing BRD
  When the user clicks "Generate PRD"
  Then the agent synthesizes a strict PRD document:
    | Section | Contents |
    | 1. Product Overview | Product name, value proposition, strategic alignment |
    | 2. User Personas & Journey Maps | Detailed user profiles, journeys, pain points |
    | 3. Feature Epics & Functional Specs | Decomposed epics, interaction diagrams, edge cases |
    | 4. Technical Architecture Contracts | API payload definitions, data schemas, security |
    | 5. Non-Functional Requirements | Performance SLAs, WCAG accessibility, browser support |
    | 6. Release Phasing & Milestones | MVP vs Phase 2 feature flags |
  ```
- **Positive Test Scenarios:**
  - `TC-BA-005`: Valid requirements produce a complete PRD with API JSON schema drafts and user journey matrices.
- **Negative & Boundary Test Scenarios:**
  - `TC-BA-006`: Contradictory business rules in prompt are flagged as risks in PRD Section 1.
- **Integration Test Scenarios:**
  - `TC-BA-007`: PRD auto-links to Gate 1 (Requirements Baseline Approval) for formal HITL sign-off.
- **Control ID:** `CTL-GATE-01`

---

#### `US-BA-03`: Autonomous Document Reviewer Agent & Iterative Refinement
- **Persona:** Business Analyst, Lead Architect
- **Story:**  
  *As a* Business Analyst,  
  *I want to* run an autonomous Reviewer Agent on my drafted BRD or PRD,  
  *so that* the agent rigorously critiques the document for ambiguity, missing edge cases, testability, and enterprise compliance, providing a 0–100 quality score and 1-click refinement.
- **Acceptance Criteria (Gherkin):**
  ```gherkin
  Given a drafted BRD or PRD in the document viewer
  When the BA clicks "Run Autonomous Review"
  Then the Document Reviewer Agent analyzes the specification against 5 quality dimensions:
    - Completeness (0-20)
    - Ambiguity & Clarity (0-20)
    - Testability & Verifiability (0-20)
    - Edge Case Coverage (0-20)
    - Compliance & Security (0-20)
  And displays an Overall Score (0-100), structured critique points, and specific missing scenarios
  And provides a "Refine Document with Recommendations" button that auto-rewrites the document incorporating all fixes
  ```
- **Positive Test Scenarios:**
  - `TC-BA-008`: Run review on PRD; reviewer produces composite score, itemized critique cards, and missing edge cases.
  - `TC-BA-009`: Click "Refine Document with Recommendations"; document is regenerated with the fixes, and the review score increases.
- **Negative & Boundary Test Scenarios:**
  - `TC-BA-010`: If document score is below 60, Gate 1 sign-off is blocked until refined.
- **Integration Test Scenarios:**
  - `TC-BA-011`: Each review critique and document revision is tracked with SHA-256 hash chaining in the audit ledger.
- **Control ID:** `CTL-GATE-01`, `CTL-AUD-01`

---

#### `US-BA-04`: Real Microsoft Word (`.docx`) & Markdown (`.md`) Export
- **Persona:** Business Analyst, Developer
- **Story:**  
  *As a* Business Analyst,  
  *I want to* download my finalized BRD, PRD, or User Stories as a styled `.docx` Microsoft Word document or `.md` file,  
  *so that* I can share official enterprise-ready files directly with executives, clients, and Jira/Confluence.
- **Acceptance Criteria (Gherkin):**
  ```gherkin
  Given a generated BRD, PRD, or User Stories document
  When the user clicks "Download .docx"
  Then the backend generates a valid Microsoft Word `.docx` binary file using `python-docx`
  And includes formatted headings, styled tables, metadata header (Project, Author, Date, Version), and table formatting
  And triggers an immediate browser file download
  And when the user clicks "Download .md", a raw UTF-8 Markdown file is downloaded
  ```
- **Positive Test Scenarios:**
  - `TC-BA-012`: Download BRD as `.docx`; verify binary content type `application/vnd.openxmlformats-officedocument.wordprocessingml.document` and non-empty size > 2KB.
  - `TC-BA-013`: Download PRD as `.md`; verify valid markdown structure with headings and tables.
- **Negative & Boundary Test Scenarios:**
  - `TC-BA-014`: Exporting an empty document returns HTTP 400 Bad Request with descriptive message.
- **Integration Test Scenarios:**
  - `TC-BA-015`: Downloaded `.docx` opens cleanly in Microsoft Word, LibreOffice, and Google Docs without formatting errors.
- **Control ID:** `CTL-AUD-03`

---

### Module 4: Autonomous Feature Implementation & GitHub Integration

#### `US-FEAT-01`: Upload BA Document & Autonomous Feature Implementation
- **Persona:** Developer
- **Story:**  
  *As a* developer,  
  *I want to* upload a feature document from a BA, select a connected GitHub repo, and have agents autonomously inspect the codebase, plan code modifications, implement feature files, and run tests,  
  *so that* routine feature scaffolding and code integration are automated without manual boilerplate.
- **Acceptance Criteria (Gherkin):**
  ```gherkin
  Given a connected GitHub repository and an uploaded BA feature document
  When the developer clicks "Implement Feature Autonomously"
  Then the Repo Intelligence Agent analyzes the AST, dependencies, and file structure
  And the Feature Builder Agent creates a dedicated git branch (`feature/{feature-slug}`)
  And applies code changes respecting pre-tool guardrails (`guard-write`)
  And runs automated tests inside an isolated sandbox
  And bundles the complete working code into a downloadable ZIP archive for local testing
  ```
- **Positive Test Scenarios:**
  - `TC-FEAT-001`: Upload feature spec; agent creates files, updates routes, runs test suite, and outputs test execution logs.
  - `TC-FEAT-002`: Downloadable ZIP contains modified source code, test files, and an inclusion/exclusion manifest.
- **Negative & Boundary Test Scenarios:**
  - `TC-FEAT-003`: Attempted write outside repository workspace root is intercepted and blocked by `CTL-SEC-02` (`guard-write`).
- **Integration Test Scenarios:**
  - `TC-FEAT-004`: Branch creation and file edits are verified via local git commands.
- **Control ID:** `CTL-HITL-01`, `CTL-SEC-02`, `CTL-AUD-01`

---

#### `US-FEAT-02`: Interactive Copilot Chat for Error Pasting & Autonomous Code Patching
- **Persona:** Developer
- **Story:**  
  *As a* developer testing the feature locally,  
  *I want an* interactive Copilot chat window where I can paste runtime errors, stack traces, or failing test output,  
  *so that* the agent immediately diagnoses the root cause, edits the code, re-runs tests, and outputs a clean working patch.
- **Acceptance Criteria (Gherkin):**
  ```gherkin
  Given the feature implementation is complete and the developer observes a local error
  When the developer pastes the error log / traceback into the Feature Workspace Chat
  And clicks "Analyze & Fix Error"
  Then the agent parses the stack trace, identifies the faulting file and line number
  And generates an RFC 6902 JSON patch or targeted replacement
  And executes the test runner to verify the fix
  And streams the reasoning, diff preview, and test outcome in real-time
  ```
- **Positive Test Scenarios:**
  - `TC-FEAT-005`: Paste `ZeroDivisionError` or missing attribute traceback; agent identifies offending function, inserts guard/fix, and confirms tests pass.
- **Negative & Boundary Test Scenarios:**
  - `TC-FEAT-006`: Pasting non-error conversational text receives helpful guidance without corrupting code files.
- **Integration Test Scenarios:**
  - `TC-FEAT-007`: Applied patches are recorded in the SHA-256 audit ledger (`CTL-AUD-01`).
- **Control ID:** `CTL-HITL-01`, `CTL-AUD-02`

---

#### `US-FEAT-03`: Automated GitHub Pull Request Creation & Merge
- **Persona:** Developer, Lead Architect
- **Story:**  
  *As a* developer or lead architect,  
  *I want to* review the final diff and test evidence, click "Create Pull Request", and optionally merge the PR once approved,  
  *so that* verified features flow smoothly into the GitHub mainline with full governance traceability.
- **Acceptance Criteria (Gherkin):**
  ```gherkin
  Given all tests pass and Gate 4 (Sandboxed Test Execution) is approved
  When the user clicks "Create GitHub Pull Request"
  Then the system pushes the feature branch to GitHub via REST API (`POST /repos/{owner}/{repo}/pulls`)
  And populates the PR title, detailed description, acceptance criteria checklist, and test evidence
  And displays the live GitHub PR link in the UI
  And when authorized by the user, calls `PUT /repos/{owner}/{repo}/pulls/{number}/merge` to merge the PR
  ```
- **Positive Test Scenarios:**
  - `TC-FEAT-008`: Create PR succeeds; returns PR # and html_url on github.com.
  - `TC-FEAT-009`: Merge PR succeeds; status changes to MERGED with commit SHA.
- **Negative & Boundary Test Scenarios:**
  - `TC-FEAT-010`: If branch has merge conflicts on GitHub, system notifies user with conflict details instead of crashing.
- **Integration Test Scenarios:**
  - `TC-FEAT-011`: PR creation and merge events are logged to the cryptographic ledger with PR URL and commit SHA.
- **Control ID:** `CTL-GATE-05`, `CTL-AUD-01`

---

### Module 5: Autonomous Bug Scanner & Targeted Bug Fix Workflow

#### `US-BUG-01`: Scan GitHub Repository for Bugs & Vulnerabilities
- **Persona:** Developer, Quality Engineer
- **Story:**  
  *As a* QE engineer,  
  *I want to* scan an entire connected GitHub repository or specific subdirectory for code bugs, security flaws, and logic anti-patterns,  
  *so that* I can inspect detected issues with severity, affected line numbers, and automated fix proposals.
- **Acceptance Criteria (Gherkin):**
  ```gherkin
  Given an active repository workspace
  When the user clicks "Scan Repository Bugs"
  Then the Repo Intelligence Agent scans code files for:
    - Resource leaks, unclosed connections, and unhandled exceptions
    - High-entropy secrets and hardcoded API credentials
    - Path traversal and unvalidated input vulnerabilities
    - Missing test coverage on critical routes
  And renders an itemized Bug & Vulnerability Diagnostic table with severity badges (Critical, High, Medium, Low)
  ```
- **Positive Test Scenarios:**
  - `TC-BUG-001`: Scan repository with injected test flaw; agent detects pattern and flags severity correctly.
- **Negative & Boundary Test Scenarios:**
  - `TC-BUG-002`: Scanning empty directory returns clean diagnostic report with 0 findings.
- **Integration Test Scenarios:**
  - `TC-BUG-003`: Diagnostic scan findings are attached as evidence to Gate 0 (Discovery & Context Validation).
- **Control ID:** `CTL-GATE-00`, `CTL-SEC-01`

---

#### `US-BUG-02`: Autonomous Targeted Bug Fix & Regression Test Generation
- **Persona:** Developer, Quality Engineer
- **Story:**  
  *As a* developer,  
  *I want to* select a detected bug or provide a natural language bug description,  
  *so that* the agent synthesizes a reproducing regression test case, fixes the bug in source code, verifies the test passes, and packages the fix for review.
- **Acceptance Criteria (Gherkin):**
  ```gherkin
  Given a detected bug or user-provided bug description
  When the user clicks "Diagnose & Auto-Fix"
  Then the Test Design Engineer writes a regression test reproducing the failure
  And the Feature Builder Agent patches the application code
  And the QA Execution Engineer runs the test suite confirming the regression test passes
  And the UI presents a before/after code diff and test terminal output
  ```
- **Positive Test Scenarios:**
  - `TC-BUG-004`: Select bug; agent writes reproducing test, fixes code, and asserts test suite passes.
- **Negative & Boundary Test Scenarios:**
  - `TC-BUG-005`: If bug cannot be fixed within 3 supersteps, agent pauses, emits explanation, and requests operator guidance.
- **Integration Test Scenarios:**
  - `TC-BUG-006`: Regression test case is linked to Gate 3 & Gate 4 in the traceability matrix.
- **Control ID:** `CTL-GATE-03`, `CTL-GATE-04`, `CTL-AUD-01`

---

### Module 6: Quality Engineering & 6-Gate Governance

#### `US-QE-01`: 6-Gate Governance State Machine & Prerequisites
- **Persona:** Release Manager, Lead Architect
- **Story:**  
  *As a* governance lead,  
  *I want* every project to strictly enforce Gates 0 through 5 in sequence,  
  *so that* untested or non-compliant code cannot be released to production without verifiable evidence and sign-off.
- **Acceptance Criteria (Gherkin):**
  ```gherkin
  Given a project workspace
  When an actor attempts to approve Gate N
  Then the system verifies Gate N-1 is APPROVED
  And verifies all prerequisite evidence items are present
  And records the decision, actor, reason, timestamp, and SHA-256 hash in the audit ledger
  ```
- **Positive Test Scenarios:**
  - `TC-QE-001`: Sequential approval of Gates 0, 1, 2, 3, 4, 5 succeeds.
- **Negative & Boundary Test Scenarios:**
  - `TC-QE-002`: Attempting to approve Gate 2 before Gate 1 is approved raises `ValueError: Prerequisite Gate 1 must be approved`.
- **Integration Test Scenarios:**
  - `TC-QE-003`: Audit ledger verification confirms zero tampering across all gate decisions.
- **Control ID:** `CTL-GATE-00` through `CTL-GATE-05`, `CTL-AUD-01`

---

## 3. End-to-End Traceability Matrix

| User Story ID | Feature Description | Primary Screen | Positive Tests | Negative Tests | Integration Tests | Governance Controls |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `US-NAV-01` | Collapsible Icons-Only Sidebar | App Shell | `TC-NAV-001`..003 | `TC-NAV-004`..005 | `TC-NAV-006` | `CTL-UI-01` |
| `US-HUB-01` | GitHub Connect & Repo Fetch | Home Hub | `TC-HUB-001`..002 | `TC-HUB-003`..005 | `TC-HUB-006` | `CTL-SEC-01`, `CTL-AUD-01` |
| `US-HUB-02` | 4-Action Switchboard | Home Hub | `TC-HUB-007`..010 | `TC-HUB-011` | `TC-HUB-012` | `CTL-UI-02` |
| `US-BA-01` | Enterprise BRD Synthesis | BA Studio | `TC-BA-001` | `TC-BA-002`..003 | `TC-BA-004` | `CTL-GATE-01`, `CTL-AUD-01` |
| `US-BA-02` | Enterprise PRD Synthesis | BA Studio | `TC-BA-005` | `TC-BA-006` | `TC-BA-007` | `CTL-GATE-01` |
| `US-BA-03` | Reviewer Agent Critique & Refine | BA Studio | `TC-BA-008`..009 | `TC-BA-010` | `TC-BA-011` | `CTL-GATE-01`, `CTL-AUD-01` |
| `US-BA-04` | `.docx` & `.md` Real Export | BA Studio | `TC-BA-012`..013 | `TC-BA-014` | `TC-BA-015` | `CTL-AUD-03` |
| `US-FEAT-01` | Autonomous Feature Implementation | Feature Studio | `TC-FEAT-001`..002| `TC-FEAT-003` | `TC-FEAT-004` | `CTL-HITL-01`, `CTL-SEC-02` |
| `US-FEAT-02` | Error Pasting & Auto-Patch Chat | Feature Studio | `TC-FEAT-005` | `TC-FEAT-006` | `TC-FEAT-007` | `CTL-HITL-01`, `CTL-AUD-02` |
| `US-FEAT-03` | GitHub PR Creation & Merge | Feature Studio | `TC-FEAT-008`..009| `TC-FEAT-010` | `TC-FEAT-011` | `CTL-GATE-05`, `CTL-AUD-01` |
| `US-BUG-01` | Repo Bug & Vulnerability Scan | Bug Studio | `TC-BUG-001` | `TC-BUG-002` | `TC-BUG-003` | `CTL-GATE-00`, `CTL-SEC-01` |
| `US-BUG-02` | Autonomous Bug Fix & Regression | Bug Studio | `TC-BUG-004` | `TC-BUG-005` | `TC-BUG-006` | `CTL-GATE-03`, `CTL-GATE-04` |
| `US-QE-01` | 6-Gate State Machine | Governance Hub | `TC-QE-001` | `TC-QE-002` | `TC-QE-003` | `CTL-GATE-00`..05, `CTL-AUD-01` |
