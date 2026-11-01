"""Deterministic, free evaluation metrics. A metric with nothing to measure has the value None, never 0 and never 1."""
from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Callable

from agent_framework import evaluator

from backend.core.security import safe_path
from backend.qe import execution
from backend.repos import static_analysis

PATH_LINE = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+\.[A-Za-z]{1,5}):(\d+)\b")
SKIP_COPY = shutil.ignore_patterns(".git", "node_modules", "__pycache__", ".venv", ".pytest_cache")


# ---- the arithmetic ----------------------------------------------------------------------------

def ratio(part: float, whole: float) -> float | None:
    """None when the whole is zero: nothing was there to measure."""
    return None if not whole else part / whole


def precision(tp: int, fp: int) -> float | None:
    return ratio(tp, tp + fp)


def recall(tp: int, fn: int) -> float | None:
    return ratio(tp, tp + fn)


def f1(tp: int, fp: int, fn: int) -> float | None:
    return ratio(2 * tp, 2 * tp + fp + fn)


def match(found: list[dict], key: list[dict], same: Callable[[dict, dict], bool]) -> dict:
    """One-to-one matching of found items to key items. Returns the counts and the lists behind them."""
    left = list(key)
    hits, extras = [], []
    for item in found:
        target = next((k for k in left if same(item, k)), None)
        if target is None:
            extras.append(item)
        else:
            left.remove(target)
            hits.append({"found": item, "key": target})
    tp, fp, fn = len(hits), len(extras), len(left)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision(tp, fp), "recall": recall(tp, fn), "f1": f1(tp, fp, fn), "missed": left, "extra": extras}


def at_location(item: dict, key: dict) -> bool:
    """Same file and a line within `tolerance` of the key's line."""
    same_file = str(item.get("file", "")).replace("\\", "/") == key.get("file")
    return same_file and abs(int(item.get("line") or 0) - int(key.get("line") or 0)) <= int(key.get("tolerance", 3))


def has_keywords(item: dict, key: dict) -> bool:
    """Every keyword of the key appears in the item's text, which is how requirements and answers are matched."""
    text = json.dumps(item, default=str).lower()
    return bool(key.get("keywords")) and all(word.lower() in text for word in key["keywords"])


def coverage(text: str, key: list[dict]) -> dict:
    """Facts-in-text key: which labelled facts appear in a prose answer. Extras cannot be counted in prose, so fp is None and only recall has a value."""
    hits = [k for k in key if has_keywords({"text": text}, k)]
    return {"tp": len(hits), "fp": None, "fn": len(key) - len(hits), "precision": None, "recall": recall(len(hits), len(key) - len(hits)), "f1": None,
            "missed": [k for k in key if k not in hits], "extra": []}


# ---- groundedness ---------------------------------------------------------------------------------

def citations(reply: str) -> list[dict]:
    """Every file, line, and quote the reply cites: from JSON objects when it has them, else path:line in prose."""
    from backend.maf import runtime as agents  # late: runtime imports the model layer

    found: list[dict] = []

    def walk(node):
        if isinstance(node, dict):
            path = node.get("file") or node.get("path")
            if isinstance(path, str) and (node.get("quote") or node.get("line")):
                found.append({"file": path, "line": int(node["line"]) if str(node.get("line") or "").isdigit() else 0, "quote": str(node.get("quote") or "")})
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    try:
        walk(agents.extract_json(reply))
    except ValueError:
        pass
    if not found:
        found = [{"file": path, "line": int(line), "quote": ""} for path, line in PATH_LINE.findall(reply)]
    return found


def _context_files(context: str) -> dict[str, str]:
    """Files in a supplied context written as `--- FILE name ---` blocks, with or without `N: ` line prefixes."""
    parts = re.split(r"^--- FILE (.+?) ---\s*$", context, flags=re.M)
    return {parts[i].strip(): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def _check_one(cite: dict, root: Path | None, files: dict[str, str]) -> str:
    """"" when the citation is real, else why not."""
    path, line, quote = cite["file"].replace("\\", "/"), cite["line"], cite["quote"]
    if root is not None:
        try:
            target = safe_path(root, path)
        except ValueError:
            return f"{path} is outside the repository"
        if not target.is_file():
            return f"{path} does not exist"
        if quote.strip():
            return "" if static_analysis.verify_quote(root, path, line, quote)[0] else f"the quote is not in {path}"
        count = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
        return "" if 1 <= line <= count else f"{path} has no line {line}"
    text = files.get(path)
    if text is None:
        return f"{path} is not in the given context"
    body = "\n".join(re.sub(r"^\s*\d+:\s?", "", row) for row in text.strip("\n").splitlines())
    if quote.strip():
        return "" if " ".join(quote.split()) in " ".join(body.split()) else f"the quote is not in {path}"
    return "" if 1 <= line <= len(body.splitlines()) else f"{path} has no line {line}"


def groundedness(reply: str, *, root: Path | None = None, context: str = "") -> dict:
    """Share of the reply's citations that exist. Checks the repository on disk when `root` is given, else the given context text.

    `value` is None when the reply cites nothing: that is "not measured", not a perfect score.
    """
    cites = citations(reply)
    files = _context_files(context)
    bad = []
    for cite in cites:
        why = _check_one(cite, root, files)
        if why:
            bad.append({**cite, "reason": why})
    return {"value": ratio(len(cites) - len(bad), len(cites)), "n": len(cites), "bad": bad}


# ---- mutation score -----------------------------------------------------------------------------------

def mutation_score(repo: Path, tests: dict[str, str], mutants: list[dict], *, runner: str = "pytest", target: str = "tests", timeout: int = 120) -> dict:
    """Plant each bug in a temporary copy of the repository and run the generated tests with `execution.run_suite`.

    A mutant is killed when a test fails. Zero executed tests, or tests that already fail on the unchanged code, give INCONCLUSIVE and no score.
    A mutant whose text is not found exactly once is "not applied" and is left out of the score.
    """
    with tempfile.TemporaryDirectory(prefix="atlas-mutation-") as tmp:
        work = Path(tmp) / "repo"
        shutil.copytree(repo, work, ignore=SKIP_COPY)
        for name, body in tests.items():
            path = safe_path(work, name, for_write=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        results = Path(tmp) / "results"
        base = execution.run_suite(runner, work, target, results, timeout)
        if base["verdict"] != "PASS":
            reason = "No test was executed" if base["verdict"] == "INCONCLUSIVE" else "The tests already fail on the unchanged code, so a failure would prove nothing"
            return {"verdict": "INCONCLUSIVE", "score": None, "reason": reason, "baseline": base["verdict"], "executed": base["passed"] + base["failed"], "killed": 0, "survived": 0, "not_applied": 0, "mutants": []}
        report, killed, survived, skipped = [], 0, 0, 0
        for mutant in mutants:
            path = safe_path(work, mutant["file"])
            original = path.read_text(encoding="utf-8") if path.is_file() else ""
            if original.count(mutant["find"]) != 1:
                skipped += 1
                report.append({"id": mutant["id"], "status": "not_applied"})
                continue
            path.write_text(original.replace(mutant["find"], mutant["replace"]), encoding="utf-8")
            try:
                done = execution.run_suite(runner, work, target, results, timeout)
            finally:
                path.write_text(original, encoding="utf-8")
            status = "killed" if done["failed"] else "survived"
            killed, survived = killed + (status == "killed"), survived + (status == "survived")
            report.append({"id": mutant["id"], "status": status, "failed_tests": [c["name"] for c in done["cases"] if c["status"] == "failed"][:5]})
        score = ratio(killed, killed + survived)
        return {"verdict": "INCONCLUSIVE" if score is None else "MEASURED", "score": score, "reason": "No mutant could be applied" if score is None else "", "baseline": "PASS",
                "executed": base["passed"], "killed": killed, "survived": survived, "not_applied": skipped, "mutants": report}


# ---- the same metrics as MAF checks ---------------------------------------------------------------------

def metric_check(name: str, measure: Callable[[str], float | None], threshold: float = 0.5):
    """A MAF @evaluator check around one measure. MAF checks are pass or fail, so nothing to measure fails with the reason "Not measured"; the number itself is `measure`'s."""

    def check(response: str) -> dict:
        value = measure(response)
        if value is None:
            return {"score": 0.0, "passed": False, "reason": f"Not measured: {name} has nothing to measure in this reply"}
        return {"score": value, "passed": value >= threshold, "reason": f"{name}={value:.3f}"}

    return evaluator(check, name=name)


def groundedness_check(*, root: Path | None = None, context: str = ""):
    return metric_check("groundedness", lambda reply: groundedness(reply, root=root, context=context)["value"], threshold=1.0)
