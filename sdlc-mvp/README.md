# ForgeSDLC Studio — Governed Multi-Agent SDLC & Quality Engineering Workspace

**ForgeSDLC Studio** is a local-first software development lifecycle (SDLC) and Quality Engineering (QE) platform. It unifies the graph-based multi-agent orchestration of the **Microsoft Agent Framework (MAF)** with the multi-gate quality governance, pre-tool guardrails, and cryptographic audit ledger of **Agentic-QE**.

---

## 1. Key Capabilities & Architecture

### Microsoft Agent Framework (MAF) Engine
- **Pregel Superstep Execution**: Graph execution proceeds in deterministic supersteps ($S_k$) with barrier synchronization.
- **Pre-built Multi-Agent Orchestrations**:
  - `MagenticBuilder`: Dynamic central manager delegating subtasks to specialists.
  - `SequentialBuilder`: Linear specialist pipeline ($A_1 \to A_2 \to \dots \to A_n$).
  - `ConcurrentBuilder`: Fan-out parallel execution with `FanInBarrier`.
  - `HandoffBuilder`: Specialist-to-specialist routing based on intent.
- **Specialist Agent Fleet**:
  1. `RequirementsAnalystAgent`: Observable requirements with mandatory evidence quotes and Gherkin user stories.
  2. `RepoIntelligenceAgent`: Deep repository inspection, tech stack identification, security heuristics.
  3. `PrincipalTestArchitectAgent`: Cross-language test strategies, risk rankings (P0-P3), level fit (Gate 2).
  4. `TestDesignEngineerAgent`: ISTQB test cases with 4 deterministic test oracles (Gate 3).
  5. `TestAutomationEngineerAgent`: Executable pytest/playwright test code synthesis.
  6. `QAExecutionEngineerAgent`: Sandboxed isolated test runner with timeout and log capture (Gate 4).
  7. `ConfidenceReviewerAgent`: Independent quality scoring (0-100 scale) and release sign-off (Gate 5).
  8. `MagenticOrchestratorAgent`: Dynamic coordinator decomposing tasks and aggregating deliverables.

### Agentic-QE 6-Gate Quality Governance Model
- **Gate 0 (Discovery & Context)**: Scope & greenfield/brownfield classification.
- **Gate 1 (Requirements Baseline)**: Freezes requirements and user stories with Given/When/Then acceptance criteria.
- **Gate 2 (Test Architecture)**: Risk strategy and test level allocation without duplication.
- **Gate 3 (Test Design & Oracles)**: ISTQB boundary values and 4 deterministic test oracles (`specified`, `derived`, `metamorphic`, `golden`).
- **Gate 4 (Execution & Sandboxing)**: Sandboxed test runner with timeout enforcement.
- **Gate 5 (Release Sign-off)**: Confidence score must meet or exceed 85/100 across 3 dimensions.

### Safety Guardrails & Cryptographic Audit Ledger
- **`CTL-HITL-01`**: PreToolUse hook blocks unauthorized file mutations.
- **`CTL-HITL-02`**: PreToolUse hook blocks destructive shell commands (`rm`, `chmod`, `curl | bash`).
- **`CTL-HITL-03`**: Cryptographic one-time nonce authorization for human decisions.
- **`CTL-SEC-01`**: High-entropy secret & API key leakage scanner.
- **`CTL-SEC-02`**: Strict workspace directory boundary and path traversal enforcement.
- **`CTL-AUD-01`**: Cryptographic Tamper-Evident Ledger dual-written to SQLite and append-only `ledger.jsonl` with SHA-256 hash chaining.
- **`CTL-AUD-02`**: RFC 6902 JSON Patch state delta synchronization.

### AG-UI Protocol (Agentic Generative UI)
- Real-time Server-Sent Events stream (`/api/ag-ui/stream/{session_id}`).
- Streaming thoughts, agent messages, tool call previews, and interactive generative approval cards.
- Persistent flyout drawer with one-click approval buttons and prompt guidance.

---

## 2. Quick Start

### Prerequisites
- Python 3.10+ (Python 3.14 recommended).
- Git (optional, for metadata).

### Running Locally
```bash
# In the sdlc-mvp directory:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Start server
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Open:
- Application UI: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- OpenAPI Documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 3. Automated Verification

Run the full automated test suite covering MAF engine, governance gates, and API endpoints:

```bash
pytest tests/
```

**Verification Results: 17 Passed in 0.58s**
- `tests/test_api.py`: 8 baseline workspace tests passed.
- `tests/test_maf_governance.py`: 9 integration tests covering SHA-256 audit chaining, gate prerequisites, secret scanner, path traversal, bash guards, MAF Pregel sequential execution, and RFC 6902 state patching.

---

## 4. Seeding Demo Data

To populate a complete demo project with documents, extracted requirements, approved gates, designed test cases, and a verified audit ledger:

```bash
python scripts/seed_demo.py
```
