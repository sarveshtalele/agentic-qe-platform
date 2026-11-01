"""A scripted confidence reviewer for tests. It answers the per-case review requests the QE workflow sends, standing in for the model.

`grade(kind, key)` may return None for a perfect record, or a dict of changes: `scores`, `flaws`, `component`, `file`, `total`, `verdict`, `skip` (send no record for this item).
Application code never imports this.
"""
import json
import re

PERFECT = {
    "design": {"source_proven": 30, "correct_target": 25, "expected_derivable": 25, "fixture_validity": 20},
    "code": {"compilable": 30, "assertion_integrity": 30, "import_safety": 20, "traceability_present": 20},
    "plan": {"controls_covered": 40, "level_fit": 30, "scenarios_derivable": 30},
}
KINDS = {"design cases": "design", "generated tests": "code", "plan": "plan"}


def asked(text: str) -> tuple[str, list[tuple[str, str]]] | None:
    """The review kind and the (key, item text) pairs of a per-case review request, or None for any other request."""
    found = re.search(r"Review type: (design cases|generated tests|plan)\.", text)
    if not found:
        return None
    items = text.split("ITEMS:", 1)[1].split("\n\nEVIDENCE:")[0]
    parts = re.split(r"(?m)^\[([^\]\n]+)\]$", items)
    return KINDS[found.group(1)], list(zip(parts[1::2], parts[2::2]))


def record(kind: str, key: str, body: str, change: dict | None, source: str = "calc.py", line: int = 2) -> dict:
    scores = {**PERFECT[kind], **(change or {}).get("scores", {})}
    total = sum(scores.values())
    verdict = "APPROVED" if total == 100 else "REVISE" if total >= 70 else "REJECT"
    item = {"tc_id": key, "scores": scores, "total": total, "verdict": verdict, "flaws": []}
    if kind == "design":
        item["component"] = {"file": source, "line": line, "symbol": "add"}
    if kind == "code":
        item["file"] = (re.search(r"TEST FILE (\S+)", body) or [None, ""])[1]
    if total < 100:
        item["flaws"] = [{"dimension": next(d for d, v in scores.items() if v < PERFECT[kind][d]), "evidence": f"{source}:{line}", "fix": "Make it exact"}]
    return {**item, **{k: v for k, v in (change or {}).items() if k not in {"scores", "skip"}}}


def reviewer(grade=None, seen=None):
    """A reply function for ScriptedClient rules. `seen` collects (kind, keys) for each request."""

    def reply(text: str) -> str:
        kind, items = asked(text)
        if seen is not None:
            seen.append((kind, [key for key, _ in items], text))
        records = []
        for key, body in items:
            change = grade(kind, key) if grade else None
            if change and change.get("skip"):
                continue
            records.append(record(kind, key, body, change))
        return json.dumps({"kind": kind, "items": records})

    return reply


def rules(grade=None, seen=None):
    """ScriptedClient rules for the three review types, placed before any generic reviewer rule."""
    return [(f"Review type: {label}.", reviewer(grade, seen)) for label in KINDS]
