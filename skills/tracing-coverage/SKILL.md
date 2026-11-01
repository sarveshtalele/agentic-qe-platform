---
name: tracing-coverage
description: Computes requirements-to-test traceability, surfaces unmapped critical requirements and orphan tests, and reports executed results per case. Use when auditing test coverage or checking the traceability gate.
metadata:
  author: Sarvesh Talele
  version: "1.4.0"
---

# Tracing Coverage

Builds an end-to-end Traceability Matrix mapping Requirements -> Test Cases -> Executable Files -> Test Results.

## When to use
Activate during test planning review, prior to release dashboard generation, or when auditing QE coverage.

## Verification Gate
- **100% Critical Requirements Mapping:** Every P0 and P1 requirement MUST link to at least 1 verified test case.
- **Orphan Test Detection:** Flags test cases that do not map to an approved requirement ID.

## Platform code step
The platform builds the matrix in code (`build_matrix` in `qe/trace.py`). From the requirements, the cases and the results, it returns the traceability matrix as JSON (entries with per-case results, coverage percent, uncovered count, orphan cases). It writes nothing.
