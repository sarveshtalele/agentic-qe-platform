"""Deterministic scanners. A finding exists only with a file, a line, and the quoted line from disk."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from backend.core.security import redact_value, safe_path, scan_secrets
from backend.repos import scan
from backend.repos.scan import _read, iter_files

SEVERITY_BY_PREFIX = {"S": "high", "F": "medium", "B": "medium", "E9": "high", "PL": "low", "UP": "info"}
JS_RULES = [
    (re.compile(r"\beval\s*\("), "JS001", "high", "eval executes arbitrary strings"),
    (re.compile(r"\.innerHTML\s*="), "JS002", "medium", "innerHTML assignment can introduce XSS"),
    (re.compile(r"dangerouslySetInnerHTML"), "JS003", "medium", "dangerouslySetInnerHTML needs sanitized input"),
    (re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}"), "JS004", "medium", "Empty catch block swallows errors"),
    (re.compile(r"\bfetch\(.*http://(?!localhost|127\.0\.0\.1)"), "JS005", "low", "Plain-HTTP request to a remote host"),
    (re.compile(r"child_process.*exec\("), "JS006", "high", "Shell execution through child_process.exec"),
]
JS_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro"}


def _ruff() -> list[str]:
    binary = shutil.which("ruff") or shutil.which("ruff", path=str(Path(sys.executable).parent))
    return [binary] if binary else [sys.executable, "-m", "ruff"]


def run_ruff(root: Path) -> list[dict]:
    command = [*_ruff(), "check", ".", "--isolated", "--exit-zero", "--output-format", "json", "--select", "F,E9,B,S,PLE", "--ignore", "S101,S311", "--exclude", "tests,test,**/test_*.py"]
    done = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env={**os.environ, "NO_COLOR": "1"})
    if done.returncode != 0 or not done.stdout.strip():
        return []
    findings = []
    for item in json.loads(done.stdout):
        path = Path(item["filename"]).resolve().relative_to(root.resolve()).as_posix()
        line = item["location"]["row"]
        code = item.get("code") or "syntax"
        severity = next((v for k, v in SEVERITY_BY_PREFIX.items() if code.startswith(k)), "medium")
        findings.append(_finding("ruff", code, severity, item["message"], path, line, root))
    return findings


def _finding(source: str, rule: str, severity: str, title: str, path: str, line: int, root: Path, evidence: str | None = None) -> dict:
    return {"source": source, "rule": rule, "severity": severity, "title": title, "file": path, "line": line,
            "evidence": evidence if evidence is not None else line_at(root, path, line), "explanation": ""}


def line_at(root: Path, relative: str, line: int) -> str:
    text = _read(safe_path(root, relative))
    lines = text.splitlines()
    return lines[line - 1].strip()[:300] if 0 < line <= len(lines) else ""


def run_secrets(root: Path) -> list[dict]:
    findings = []
    for path in iter_files(root):
        if path.suffix.lower() in {".lock", ".svg", ".map", ".min.js"} or path.name in {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "uv.lock", "poetry.lock"}:
            continue
        relative = path.relative_to(root).as_posix()
        for hit in scan_secrets(_read(path)):
            findings.append(_finding("secrets", "SEC001", "critical", f"{hit['type']} committed to the repository", relative, hit["line"], root, evidence=f"[redacted: {hit['redacted']}]"))
    return findings


def run_js_rules(root: Path) -> list[dict]:
    findings = []
    for path in iter_files(root):
        if path.suffix.lower() not in JS_SUFFIXES or ".min." in path.name:
            continue
        relative = path.relative_to(root).as_posix()
        for number, line in enumerate(_read(path).splitlines(), 1):
            if len(line) > 1000 or line.lstrip().startswith(("//", "*")):
                continue
            for pattern, rule, severity, title in JS_RULES:
                if pattern.search(line):
                    findings.append(_finding("js-rules", rule, severity, title, relative, number, root))
    return findings


def run_manifests(root: Path) -> list[dict]:
    findings = []
    package_json = root / "package.json"
    if package_json.exists():
        text = _read(package_json)
        lock = any((root / n).exists() for n in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock"))
        if text and not lock:
            findings.append(_finding("manifest", "DEP001", "medium", "package.json has no lockfile, so installs are not reproducible", "package.json", 1, root))
    for workflow in (root / ".github" / "workflows").glob("*.y*ml") if (root / ".github" / "workflows").exists() else []:
        relative = workflow.relative_to(root).as_posix()
        for number, line in enumerate(_read(workflow).splitlines(), 1):
            match = re.search(r"uses:\s*([\w./-]+)@(main|master|latest)\b", line)
            if match:
                findings.append(_finding("manifest", "CI001", "medium", f"Action {match.group(1)} follows a moving ref", relative, number, root))
    return findings


def run_all(root: Path) -> list[dict]:
    return run_ruff(root) + run_secrets(root) + run_js_rules(root) + run_manifests(root)


def verify_quote(root: Path, relative: str, line: int, quote: str) -> tuple[bool, int]:
    """Reject hallucinated evidence: the quote must exist in the file near the claimed line.

    Returns (verified, corrected line). Whitespace is normalized because models reflow code.
    """
    try:
        text = _read(safe_path(root, relative))
    except ValueError:
        return False, line
    if not text or not quote.strip():
        return False, line
    wanted = " ".join(quote.split())
    lines = [" ".join(l.split()) for l in text.splitlines()]
    first = wanted.split(" \n")[0]
    candidates = [i + 1 for i, l in enumerate(lines) if wanted in l or (len(l) > 8 and l in wanted)]
    if not candidates:
        joined = " ".join(lines)
        if first and first in joined:
            return True, line
        return False, line
    return True, min(candidates, key=lambda n: abs(n - line))


def rank_files_for_review(root: Path, analysis: dict, limit: int = 12) -> list[str]:
    """Pick the files most worth an LLM read: entry points, routes, auth, data, payment code, big modules."""
    risky = re.compile(r"auth|login|token|secret|payment|checkout|db|sql|upload|exec|shell|admin|session|crypto|api|route", re.I)
    score: dict[str, int] = {}
    for source in analysis.get("largest_sources", []):
        path = source["path"]
        score[path] = min(source["lines"], 600) // 60 + (6 if risky.search(path) else 0)
    for path in analysis.get("entrypoints", []):
        if path in score:
            score[path] += 5
    for route in analysis.get("routes", []):
        if route["file"] in score:
            score[route["file"]] += 2
    return [p for p, _ in sorted(score.items(), key=lambda kv: -kv[1])][:limit]


NOT_REVIEWED = {".css", ".scss", ".html", ".md", ".json", ".yaml", ".yml", ".toml"}


def review_targets(root: Path) -> list[str]:
    """Every source file in the repository. Tests are left out because they are not what ships."""
    files = [f for f in scan.tree(root, limit=100_000) if Path(f).suffix.lower() in scan.LANGUAGES and Path(f).suffix.lower() not in NOT_REVIEWED]
    return [f for f in files if not scan.TEST_NAME.search(f)]


__all__ = ["run_all", "verify_quote", "rank_files_for_review", "review_targets", "line_at", "redact_value"]
