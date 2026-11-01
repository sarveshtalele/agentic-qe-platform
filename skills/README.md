# Skills

These 11 skills come from agentic-qe v1.4.0, commit `bf2452a`. They are copied to `skills/<name>/` so that MAF's `FileSkillsSource` can load them.

## What was copied and what was not

- Copied from each folder: `SKILL.md`, `references/`, `assets/` and `evals/` where present.
- Not copied: `scripts/` and every `.ts` file. Their logic is ported to Python, or comes in a later phase. The qe-* command folders are not copied.
- `SKILL.md` edits: the `compatibility` and `allowed-tools` lines that name Node, Bash or `${CLAUDE_SKILL_DIR}` are removed. Script-run instructions now say the platform runs the step in code, and `${CLAUDE_SKILL_DIR}/references/` became `references/`. The `name`, `description` and `metadata` lines are unchanged.

## Python port of each script

Mapping from `docs/PLUGIN_AND_UI_PLAN.md`, Part 1, "Skills". Status is checked against the files in `src/backend` on 2 November 2026.

| Skill | Used by agent | Python port of its script | Status |
|---|---|---|---|
| `analyzing-repositories` | `repo-intelligence-analyst` | `repos/scan.py` (`scan-repo.ts`) | Built (`analyze`) |
| `extracting-requirements` | `requirements-analyst` | `qe/contracts.py` (`extract-contracts.ts`) | **Planned, not built** |
| `authoring-user-stories` | `business-analyst` | `api/documents.py` (`export-cases.ts`) | Partly built: CSV helper only. Validating export is not ported |
| `planning-tests` | `principal-test-architect` | `qe/model.py` (`calculate-risk.ts`) | Built (`plan_confidence`). Verdict word is `REJECTED`, skill text says `REJECT` |
| `designing-test-cases` | `test-design-architect` | `qe/confidence.py` (`check-confidence.ts`) | **Planned, not built**. `generate-cases.ts` has no port named in the plan |
| `generating-test-data` | `test-design-architect` | `qe/test_data.py` (`synthesize-data.ts`) | **Planned, not built** |
| `generating-test-code` | `test-automation-engineer` | `qe/emit.py` (`emit-tests.ts`) | **Planned, not built**. `invalid_test_code` exists in `qe/execution.py` |
| `executing-tests` | `qa-execution-engineer` | `qe/execution.py` (`run-isolated.ts`, `parse-junit.ts`) | Built for runs, JUnit and verdict. **Evidence collection** (`collect-evidence.ts`, `mcp-evidence.ts`) **planned, not built** |
| `healing-tests` | `defect-diagnostician` | `qe/execution.py` (`diagnose-failure.ts`, `apply-healing.ts`) | Built for classification and assertion check (`classify_failure`, `assertions_preserved`) |
| `tracing-coverage` | `confidence-reviewer` | `qe/trace.py` (`build-matrix.ts`) | Built (`build_matrix`) |
| `building-qe-dashboard` | None (QE Studio UI) | `qe/reports.py` (`gate-report-md.ts`, `build-trace-report.ts`) | **Planned, not built** |

## Notes

- The plugin's `evals/evals.json` files are copied with each skill and now join their agent's eval set (`maf/evals.py`, `skill_cases`). They hold `expected_behavior` sentences for a person or grader. Only 5 of the 33 cases have literal code checks (`evals/skills/checks.json`); the other 28 are listed as needing a grader and are neither passed nor failed until phase 6. `executing-tests` and `building-qe-dashboard` have no agent yet, so their cases do not run.
- Nothing in this folder is run by the plugin's scripts, and nothing here runs Node or TypeScript.
