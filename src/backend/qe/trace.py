"""Traceability matrix and release score, ported from build-matrix.ts and the plugin's verdict rules."""
from __future__ import annotations

import re

CASE_ID = re.compile(r"TC[-_][\w-]*\d+", re.I)


def _norm(value: str) -> str:
    return value.upper().replace("_", "-")


def build_matrix(requirements: list[dict], cases: list[dict], tests: list[dict], results: list[dict]) -> dict:
    """Requirement to case to generated test to executed result, with gaps and orphans called out."""
    executed: dict[str, str] = {}
    for suite in results:
        for case in suite.get("cases", []):
            for match in CASE_ID.findall(f"{case['classname']} {case['name']}"):
                key = _norm(match)
                executed[key] = "failed" if case["status"] == "failed" or executed.get(key) == "failed" else case["status"]
    by_case = {_norm(t["case_id"]): t for t in tests}
    rows = []
    for requirement in requirements:
        linked = [c for c in cases if c["requirement_id"] == requirement["id"]]
        cells = [{"case_id": c["id"], "type": c["type"], "level": c["level"], "test_file": by_case.get(_norm(c["id"]), {}).get("path", ""),
                  "result": executed.get(_norm(c["id"]), "not run")} for c in linked]
        rows.append({"requirement_id": requirement["id"], "title": requirement["title"], "priority": requirement.get("priority", "P1"), "cases": cells,
                     "covered": any(c["result"] == "passed" for c in cells)})
    known = {_norm(c["id"]) for c in cases}
    gaps = [r["requirement_id"] for r in rows if r["priority"] in ("P0", "P1") and not r["covered"]]
    return {"rows": rows, "gaps": gaps, "orphan_tests": sorted(k for k in executed if k not in known),
            "unlinked_cases": [c["id"] for c in cases if c["requirement_id"] not in {r["id"] for r in requirements}]}


def release_summary(matrix: dict, results: list[dict], defects: list[dict]) -> dict:
    total = sum(s["passed"] + s["failed"] for s in results)
    passed = sum(s["passed"] for s in results)
    failed = sum(s["failed"] for s in results)
    if total == 0:
        overall = "INCONCLUSIVE"
    elif failed or matrix["gaps"]:
        overall = "FAIL"
    else:
        overall = "PASS"
    rows = matrix["rows"]
    return {"verdict": overall, "executed": total, "passed": passed, "failed": failed, "pass_rate": round(100 * passed / total, 1) if total else 0,
            "requirements": len(rows), "requirements_covered": sum(r["covered"] for r in rows),
            "coverage": round(100 * sum(r["covered"] for r in rows) / len(rows), 1) if rows else 0, "gaps": matrix["gaps"], "defects": len(defects)}
