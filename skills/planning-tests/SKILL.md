---
name: planning-tests
description: Formulates risk-weighted test strategies, decomposing requirements across Unit, Integration, API, and UI/E2E levels without duplication. Use when organizing testing strategy.
metadata:
  author: Sarvesh Talele
  version: "1.4.0"
---

# Planning Tests

Architects the smallest, most complete test strategy for a target application, ranking test areas by risk.

## When to use
Activate when the plan stage runs (plugin command `qe-plan`), or when scoping and allocating test levels for approved requirements.

## Workflow
1. **Requirement Risk Scoring:** Score business impact, change volatility, and technical risk (P0, P1, P2).
2. **Level Allocation:** Assign each scenario to the lowest proving level according to [references/LEVEL_GUIDELINES.md](references/LEVEL_GUIDELINES.md).
3. **Three Levels Required:** Every plan allocates **Unit** (pure functions/classes, no I/O), **Integration** (API/service/DB boundary, in-process or with a test client) and **E2E** (browser via Playwright) cases. Skip a level only with a written reason in the plan (e.g. "no UI").
4. **De-duplication Check:** Eliminate scenarios duplicated across unit, API, and E2E layers.
5. **Independent Confidence Scoring:** Calculate `controls_covered`, `level_fit`, and `scenarios_derivable`.
6. **Output Delivery:** Produce `03-plan/strategy.md` and `03-plan/plan.json`.

## Platform code step
The platform scores the plan in code (`qe/model.py`). Given `{"controlsCovered": 0-40, "levelFit": 0-30, "scenariosDerivable": 0-30}`, it returns `{score, verdict}`: `APPROVED` at 100, `REVISE` from 70, otherwise `REJECT`. It writes nothing. The Python verdict word is `REJECTED`; see `skills/README.md`.
