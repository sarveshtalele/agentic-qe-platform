"""Registered test runners, JUnit parsing, honest verdicts. No shell, bounded time, scrubbed environment."""
from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

SENSITIVE_ENV = re.compile(r"(?i)key|token|secret|password|credential|auth|cookie")
TAIL = 6000
GIT_AUTHOR = "Agentic QE Platform"


def clean_env(extra: dict | None = None) -> dict:
    """Test code from the target repo must never see this platform's credentials."""
    env = {k: v for k, v in os.environ.items() if not SENSITIVE_ENV.search(k)}
    env.update(extra or {})
    return env


def parse_junit(xml_text: str) -> dict:
    empty = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "cases": []}
    if not xml_text.strip():
        return empty
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return empty
    cases = []
    for node in root.iter("testcase"):
        failure = node.find("failure")
        if failure is None:
            failure = node.find("error")
        skipped = node.find("skipped") is not None
        cases.append({
            "name": node.get("name", ""), "classname": node.get("classname", ""), "time": float(node.get("time") or 0),
            "status": "failed" if failure is not None else "skipped" if skipped else "passed",
            "message": ((failure.get("message") or "") + "\n" + (failure.text or ""))[:3000] if failure is not None else "",
        })
    failed = sum(c["status"] == "failed" for c in cases)
    skipped = sum(c["status"] == "skipped" for c in cases)
    return {"total": len(cases), "passed": len(cases) - failed - skipped, "failed": failed, "skipped": skipped, "cases": cases}


def verdict(result: dict, exit_code: int | None) -> str:
    """Port of run-isolated.ts: zero executed tests is INCONCLUSIVE, never PASS."""
    executed = result["passed"] + result["failed"]
    if exit_code is None or executed == 0:
        return "INCONCLUSIVE"
    return "FAIL" if result["failed"] or exit_code != 0 else "PASS"


def detect_python(worktree: Path) -> str:
    venv = worktree.parent / ".venv"
    candidate = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(candidate) if candidate.exists() else sys.executable


def _pytest(worktree: Path, target: str, junit: Path) -> list[str]:
    return [detect_python(worktree), "-m", "pytest", target, "-q", "--tb=short", "-p", "no:cacheprovider", f"--junitxml={junit}"]


def _node_tool(name: str, *args: str) -> list[str] | None:
    npx = shutil.which("npx")
    return [npx, "--no-install", name, *args] if npx else None


def build_command(runner: str, worktree: Path, target: str, junit: Path) -> tuple[list[str] | None, dict]:
    env: dict = {}
    if runner == "pytest":
        return _pytest(worktree, target, junit), env
    if runner == "vitest":
        return _node_tool("vitest", "run", target, "--reporter=junit", f"--outputFile={junit}"), env
    if runner == "jest":
        return _node_tool("jest", target, "--ci", "--reporters=default", "--reporters=jest-junit"), {"JEST_JUNIT_OUTPUT_FILE": str(junit)}
    if runner == "playwright":
        return _node_tool("playwright", "test", target, "--reporter=junit"), {"PLAYWRIGHT_JUNIT_OUTPUT_NAME": str(junit)}
    return None, env


REGISTERED = ("pytest", "vitest", "jest", "playwright")


def run_suite(runner: str, worktree: Path, target: str, results_dir: Path, timeout: int = 300) -> dict:
    if runner not in REGISTERED:
        return {"runner": runner, "target": target, "verdict": "INCONCLUSIVE", "reason": f"Runner {runner} is not registered", "exit_code": None, "total": 0, "passed": 0, "failed": 0, "skipped": 0, "cases": [], "output": ""}
    results_dir.mkdir(parents=True, exist_ok=True)
    junit = results_dir / f"{runner}-{int(time.time() * 1000)}.xml"
    command, env = build_command(runner, worktree, target, junit)
    if not command:
        return {"runner": runner, "target": target, "verdict": "INCONCLUSIVE", "reason": "Node.js tooling not found on PATH", "exit_code": None, "total": 0, "passed": 0, "failed": 0, "skipped": 0, "cases": [], "output": ""}
    started = time.time()
    try:
        # no bytecode: a same-size edit within a second could otherwise run stale code, and cache files would enter the reviewed diff
        done = subprocess.run(command, cwd=worktree, env=clean_env({**env, "PYTHONDONTWRITEBYTECODE": "1"}), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        exit_code, output, reason = done.returncode, done.stdout + done.stderr, ""
    except subprocess.TimeoutExpired as exc:
        exit_code, output, reason = None, str(exc.stdout or ""), f"Timed out after {timeout}s"
    except OSError as exc:
        exit_code, output, reason = None, "", f"Could not start {runner}: {exc}"
    result = parse_junit(junit.read_text(encoding="utf-8", errors="replace")) if junit.exists() else parse_junit("")
    return {"runner": runner, "target": target, "verdict": verdict(result, exit_code), "reason": reason, "exit_code": exit_code,
            "duration_s": round(time.time() - started, 2), "command": " ".join(Path(command[0]).name if i == 0 else c for i, c in enumerate(command)),
            "output": output[-TAIL:], **result}


def _commit_date(worktree: Path) -> str:
    """Date of the newest commit this app did not make. Its own commit moments ago would remove the date limit."""
    done = subprocess.run([shutil.which("git") or "git", "log", "-50", "--format=%an|%cI"], cwd=worktree, capture_output=True, text=True, timeout=30)
    dates = [line.rsplit("|", 1) for line in done.stdout.splitlines() if "|" in line]
    return next((date for author, date in dates if author != GIT_AUTHOR), "")


def _test_extras(worktree: Path) -> str:
    """The repository's own test plugins usually live in dev or test extras, and tests cannot run without them."""
    try:
        extras = tomllib.loads((worktree / "pyproject.toml").read_text(encoding="utf-8")).get("project", {}).get("optional-dependencies", {})
    except (tomllib.TOMLDecodeError, OSError):
        return ""
    wanted = [name for name in extras if name.lower() in {"dev", "test", "tests", "testing"}]
    return f"[{','.join(wanted)}]" if wanted else ""


def install_dependencies(worktree: Path, analysis: dict, log) -> None:
    """Runs repo-defined install scripts, so callers only reach this after explicit human opt-in.

    Unpinned dependencies install as they were at the repository's last commit, because a later major
    release can break code that was fine when written.
    """
    if (worktree / "requirements.txt").exists() or (worktree / "pyproject.toml").exists():
        venv = worktree.parent / ".venv"
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not python.exists():
            subprocess.run([sys.executable, "-m", "venv", str(venv)], check=False, timeout=120)
        subprocess.run([str(python), "-m", "pip", "install", "-q", "-U", "pip"], env=clean_env(), capture_output=True, timeout=180)
        supported = "--uploaded-prior-to" in subprocess.run([str(python), "-m", "pip", "install", "--help"], capture_output=True, text=True, errors="replace", timeout=60).stdout
        date = _commit_date(worktree)
        dated = ["--uploaded-prior-to", date] if supported and date else []
        log(f"Installing dependencies as of {date}" if dated else "Installing latest dependencies; this pip cannot limit by date")
        steps = []
        if (worktree / "requirements.txt").exists():
            steps.append([str(python), "-m", "pip", "install", "-q", *dated, "-r", "requirements.txt"])
        if (worktree / "pyproject.toml").exists():
            steps.append([str(python), "-m", "pip", "install", "-q", *dated, "-e", f".{_test_extras(worktree)}"])
        steps += [[str(python), "-m", "pip", "install", "-q", *dated, "-r", path.name] for path in sorted(worktree.glob("requirements*dev*.txt")) + sorted(worktree.glob("requirements*test*.txt"))]
        steps.append([str(python), "-m", "pip", "install", "-q", *dated, "pytest"])
        for step in steps:
            done = subprocess.run(step, cwd=worktree, env=clean_env(), capture_output=True, text=True, errors="replace", timeout=600)
            log(f"pip exit {done.returncode}: {' '.join(step[4:])[:120]}" + (f" {done.stderr.strip()[-200:]}" if done.returncode else ""))
    npm = shutil.which("npm")
    if (worktree / "package.json").exists() and npm:
        command = [npm, "ci"] if (worktree / "package-lock.json").exists() else [npm, "install"]
        done = subprocess.run(command, cwd=worktree, env=clean_env(), capture_output=True, text=True, errors="replace", timeout=900)
        log(f"{' '.join(command[1:])} exit {done.returncode}")


def failed_names(result: dict) -> list[str]:
    return [f"{c['classname']}::{c['name']}" for c in result.get("cases", []) if c["status"] == "failed"]


def compare_to_baseline(results: list[dict], baseline: dict) -> dict:
    """Judge a change by what it broke. Failures that existed before it are reported but are not its fault."""
    if not results or not any(r["passed"] + r["failed"] for r in results):
        return {"verdict": "INCONCLUSIVE", "reason": "No test ran", "new_failures": [], "existing_failures": 0}
    new, existing = [], 0
    for result in results:
        before = set(baseline.get(result["runner"], []))
        for case in result["cases"]:
            if case["status"] != "failed":
                continue
            if f"{case['classname']}::{case['name']}" in before:
                existing += 1
            else:
                new.append(case)
    if new:
        environment = all(classify_failure(c["message"]) == "ENVIRONMENT" for c in new)
        return {"verdict": "INCONCLUSIVE" if environment else "FAIL", "reason": "Tests could not run in this environment" if environment else "", "new_failures": new, "existing_failures": existing}
    if existing:
        return {"verdict": "NO NEW FAILURES", "reason": f"{existing} tests were already failing before this change", "new_failures": [], "existing_failures": existing}
    return {"verdict": "PASS", "reason": "", "new_failures": [], "existing_failures": 0}


def choose_runners(analysis: dict) -> list[str]:
    runners = [r for r in analysis.get("test_runners", []) if r in REGISTERED]
    return runners or (["pytest"] if "Python" in analysis.get("languages", {}) else [])


def syntax_error(path: str, code: str) -> str | None:
    if path.endswith(".py"):
        try:
            ast.parse(code)
        except SyntaxError as exc:
            return f"{path}:{exc.lineno}: {exc.msg}"
    return None


ASSERTION = re.compile(r"\bassert\b|\bexpect\(|\.assert\w*\(|\bshould\b")
WEAKENING = re.compile(r"assert\s+True\b|expect\(\s*true\s*\)|pytest\.skip|\.skip\(|xfail|@Disabled|\.only\(")


def assertions_preserved(old: str, new: str) -> tuple[bool, str]:
    """Port of apply-healing.ts: healing may repair selectors or fixtures, never weaken an assertion."""
    before = [l.strip() for l in old.splitlines() if ASSERTION.search(l)]
    after = [l.strip() for l in new.splitlines() if ASSERTION.search(l)]
    if WEAKENING.search(new) and not WEAKENING.search(old):
        return False, "Patch introduces a skip or a tautological assertion"
    if len(after) < len(before):
        return False, f"Patch removes assertions ({len(before)} to {len(after)})"
    if [l for l in before if l not in after]:
        return False, "Patch changes an existing assertion"
    return True, ""


def _module_names(path: Path) -> set[str] | None:
    """Names a Python module defines at top level. None when it cannot be known, such as with star imports."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return None
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":
                    return None
                names.add((alias.asname or alias.name).split(".")[0])
    return None if "__getattr__" in names else names


def invalid_test_code(worktree: Path, path: str, code: str) -> list[str]:
    """Generated tests must import names that exist and use only plugins the repository has. Agents invent both."""
    if not path.endswith(".py"):
        return []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []  # syntax_error reports this
    issues = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level or not node.module:
            continue
        base = worktree.joinpath(*node.module.split("."))
        module = base.with_suffix(".py") if base.with_suffix(".py").is_file() else base / "__init__.py"
        if not module.is_file():
            if (worktree / node.module.split(".")[0]).exists():
                issues.append(f"{path}: module {node.module} does not exist")
            continue
        available = _module_names(module)
        submodules = {p.stem for p in base.glob("*.py")} | {p.name for p in base.iterdir() if p.is_dir()} if base.is_dir() else set()
        missing = [a.name for a in node.names if available is not None and a.name != "*" and a.name not in available and a.name not in submodules]
        if missing:
            issues.append(f"{path}: {node.module} has no {', '.join(missing)}")
    if re.search(r"pytest\.mark\.asyncio|^\s*async def test_", code, re.M):
        manifests = " ".join(p.read_text(encoding="utf-8", errors="replace") for p in worktree.glob("*") if p.name.startswith(("requirements", "pyproject", "setup")) and p.is_file())
        if "pytest-asyncio" not in manifests and "pytest_asyncio" not in manifests:
            issues.append(f"{path}: this repository does not have pytest-asyncio. Write a normal test and call asyncio.run() if needed")
    return issues


def classify_failure(message: str) -> str:
    """Port of diagnose-failure.ts. Only drift classes may be healed; DEFECT stays a failing test."""
    text = message.lower()
    if "cannot import name" in text:  # the module exists but the test asks for a wrong name: the test is wrong, not the machine
        return "FIXTURE_DRIFT"
    if re.search(r"modulenotfounderror|importerror|command not found|connection refused|econnrefused|cannot find module|no module named|browser.*not found|timed out waiting for server|not natively supported", text):
        return "ENVIRONMENT"
    if re.search(r"locator|selector|getby|element not found|no element|waiting for|strict mode violation", text):
        return "SELECTOR_DRIFT"
    if re.search(r"fixture|keyerror|filenotfounderror|seed|attributeerror: 'nonetype'|typeerror: .*argument", text):
        return "FIXTURE_DRIFT"
    return "DEFECT"
