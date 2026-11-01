"""Deterministic requirements checks. They cap the reviewer's score, so a model cannot pass a weak document."""
from __future__ import annotations

import re

from backend.core.files import template_headings

VAGUE = re.compile(r"\b(fast|quickly|user[- ]friendly|easy to use|easily|robust|seamless(ly)?|intuitive|as needed|as appropriate|where appropriate|work well|etc\.?)\b", re.I)
HAS_NUMBER = re.compile(r"\d")


def check(document: str, template_body: str = "") -> dict:
    issues: list[str] = []
    cap = 100
    sections = re.split(r"^#{2,3}\s+(.+?)\s*$", document, flags=re.M)
    bodies = {sections[i].strip().lower(): sections[i + 1].strip() for i in range(1, len(sections) - 1, 2)}
    empty = [name for name, body in bodies.items() if not body]
    if empty:
        issues.append(f"Empty sections: {', '.join(empty)}")
        cap -= 15 * len(empty)
    functional = next((body for name, body in bodies.items() if "functional requirement" in name and "non-functional" not in name), None)
    if functional is not None:
        ids = re.findall(r"\bFR-\d+\b", functional)
        if not ids:
            issues.append("Functional Requirements has no numbered FR ids")
            cap -= 30
        elif len(ids) != len(set(ids)):
            issues.append("Functional Requirements repeats an FR id")
            cap -= 10
    vague = [line.strip()[:90] for line in document.splitlines() if VAGUE.search(line) and not HAS_NUMBER.search(line) and not line.lstrip().startswith("#")]
    if vague:
        issues.append(f"Untestable wording without a measure ({len(vague)}): {vague[0]}")
        cap -= min(25, 5 * len(vague))
    if template_body:
        guidance = [line.strip() for line in template_body.splitlines() if len(line.strip()) > 25 and not line.startswith("#")]
        left = [g for g in guidance if g in document]
        if left:
            issues.append(f"Template guidance left in the document: {left[0][:80]}")
            cap -= 20
        headings = template_headings(template_body)
        missing = [h for h in headings if h.lower() not in bodies]
        if missing:
            issues.append(f"Missing template sections: {', '.join(missing)}")
            cap -= 10 * len(missing)
    return {"score_cap": max(cap, 0), "issues": issues}


MEASURE = re.compile(r"(?<![\w.-])(\d+(?:[.,]\d+)?)\s?(%|ms\b|milliseconds?\b|seconds?\b|minutes?\b|hours?\b|days?\b|weeks?\b|months?\b|years?\b|[kmg]b\b|users?\b|requests?\b|concurrent\b)", re.I)


def invented_measures(document: str, sources: str) -> list[str]:
    """Measures the document states that its brief and sources do not, unless marked as proposed."""
    known = {m.group(1) for m in MEASURE.finditer(sources)} | set(re.findall(r"\d+(?:[.,]\d+)?", sources))
    found = []
    for line in document.splitlines():
        if "proposed" in line.lower() or line.lstrip().startswith("#"):
            continue
        found += [m.group(0) for m in MEASURE.finditer(line) if m.group(1) not in known]
    return sorted(set(found))


def apply(review: dict, document: str, template_body: str = "", sources: str | None = None) -> dict:
    """Combine a model review with the deterministic result. The lower score wins."""
    result = check(document, template_body)
    if sources is not None:
        invented = invented_measures(document, sources)
        if invented:
            result["issues"].append(f"Measures not in the brief or sources: {', '.join(invented[:8])}. Mark each as (proposed) or remove it")
            result["score_cap"] = min(result["score_cap"], 70)
    score = min(review["score"], result["score_cap"])
    verdict = "APPROVED" if score >= 85 else "REVISE" if score >= 60 else "REJECTED"
    return {**review, "score": score, "verdict": verdict, "model_score": review["score"], "issues": [*result["issues"], *review.get("issues", [])]}
