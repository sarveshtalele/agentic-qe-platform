---
name: analyzing-repositories
description: Analyzes repository structures, detects programming languages, frameworks, package managers, and existing test inventory. Use when assessing a new codebase or preparing for test generation.
metadata:
  author: Sarvesh Talele
  version: "1.4.0"
---

# Analyzing Repositories

Inspects a target repository codebase to produce a deterministic architecture manifest and stack profile.

## When to use
Activate this skill at the beginning of any test engineering engagement, or when the discover or start stage runs (plugin commands `qe-discover` and `qe-start`).

## Workflow
1. **Tree Scanning:** Enumerate all files, excluding `node_modules`, `.git`, `dist`, `build`, and `.venv`.
2. **Manifest Parsing:** Read `package.json`, `pyproject.toml`, `pom.xml`, `go.mod`, `Cargo.toml`.
3. **Signal Detection:** Match tokens against [references/STACK_SIGNALS.md](references/STACK_SIGNALS.md).
4. **Test Inventory:** Identify existing test suites, file naming patterns (`*.test.ts`, `test_*.py`), and runner scripts.
5. **Output Generation:** Emit `01-discovery/architecture.json` in the target documentation folder.

## Mode detection
`--mode auto` detects; an explicit `greenfield` or `brownfield` wins.
- **Brownfield:** source files or tests exist. Record the existing test count as the regression baseline. Run nothing.
- **Greenfield:** no source code yet. Skip scanning. Record the intended stack from the user's stated stack, or ask. Next step is the stories stage.

## Platform code step
The platform runs the scan in code, not as a skill script. Given the repository directory, it returns JSON (languages, frameworks, test runners, manifests, source/test file counts, detected `mode`) and writes nothing. Implemented in `repos/scan.py`.

## Edge Cases
- **Monorepos:** Detect workspace roots (`pnpm-workspace.yaml`, lerna, cargo workspaces) and shard analysis per package.
- **Minified Files:** Flag minified bundles and request unminified source code.
