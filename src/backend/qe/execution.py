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


def _pytest(worktree: Path, target: str, junit: Path, extra: tuple[str, ...] = ()) -> list[str]:
    return [detect_python(worktree), "-m", "pytest", target, "-q", "--tb=short", "-p", "no:cacheprovider", "--continue-on-collection-errors", f"--junitxml={junit}", *extra]


def _node_tool(name: str, *args: str) -> list[str] | None:
    npx = shutil.which("npx")
    return [npx, "--no-install", name, *args] if npx else None


def build_command(runner: str, worktree: Path, target: str, junit: Path, extra: tuple[str, ...] = ()) -> tuple[list[str] | None, dict]:
    env: dict = {}
    if runner == "pytest":
        return _pytest(worktree, target, junit, extra), env
    if runner == "vitest":
        return _node_tool("vitest", "run", target, "--reporter=junit", f"--outputFile={junit}"), env
    if runner == "jest":
        return _node_tool("jest", target, "--ci", "--reporters=default", "--reporters=jest-junit"), {"JEST_JUNIT_OUTPUT_FILE": str(junit)}
    if runner == "playwright":
        return _node_tool("playwright", "test", target, "--reporter=junit"), {"PLAYWRIGHT_JUNIT_OUTPUT_NAME": str(junit)}
    return None, env


REGISTERED = ("pytest", "vitest", "jest", "playwright")


def run_suite(runner: str, worktree: Path, target: str, results_dir: Path, timeout: int = 300, extra: tuple[str, ...] = ()) -> dict:
    """`extra` is added to the pytest command line only, so the setup step can set options for generated tests without editing the repository's config."""
    if runner not in REGISTERED:
        return {"runner": runner, "target": target, "verdict": "INCONCLUSIVE", "reason": f"Runner {runner} is not registered", "exit_code": None, "total": 0, "passed": 0, "failed": 0, "skipped": 0, "cases": [], "output": ""}
    results_dir.mkdir(parents=True, exist_ok=True)
    junit = results_dir / f"{runner}-{int(time.time() * 1000)}.xml"
    command, env = build_command(runner, worktree, target, junit, extra)
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


def invalid_test_code(worktree: Path, path: str, code: str, async_ok: bool = False) -> list[str]:
    """Generated tests must import names that exist and use only plugins the repository has. Agents invent both.

    `async_ok` is true when the platform will make pytest-asyncio available (it is installed, or the run installs dependencies)."""
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
    if not async_ok and re.search(r"pytest\.mark\.asyncio|^\s*async def test_", code, re.M):
        manifests = " ".join(p.read_text(encoding="utf-8", errors="replace") for p in worktree.glob("*") if p.name.startswith(("requirements", "pyproject", "setup")) and p.is_file())
        if "pytest-asyncio" not in manifests and "pytest_asyncio" not in manifests:
            issues.append(f"{path}: this repository does not have pytest-asyncio. Write a normal test and call asyncio.run() if needed")
    return issues


CLASSIFICATION = {"DEFECT": "defect", "SELECTOR_DRIFT": "test problem", "FIXTURE_DRIFT": "test problem", "ENVIRONMENT": "environment"}
ENV_EVIDENCE = re.compile(
    r"modulenotfounderror|importerror|command not found|connection refused|econnrefused|cannot find module|no module named|browser.*not found|timed out waiting for server|not natively supported"
    r"|connecterror|all connection attempts failed|max retries exceeded with url|errno 111|errno 61|winerror 10061|actively refused|name or service not known|nodename nor servname"
    r"|429 too many requests")
ASSERTION_LINE = re.compile(r"(?i)^(assert\b|assertionerror\b)")


def _first_line(message: str) -> str:
    return next((line.strip() for line in message.splitlines() if line.strip()), "")


def _rate_limited(message: str) -> bool:
    """A test that expected another status and got 429 was stopped by the application's rate limiter, which is the environment."""
    first = _first_line(message)
    for pattern in (r"(?i)^assert\s+429\s*==\s*(\d{3})\b", r"(?i)^assertionerror:\s*429\s*!=\s*(\d{3})\b"):
        if (found := re.match(pattern, first)) and found.group(1) != "429":
            return True
    if (found := re.match(r"(?i)^assert\s+(\d{3})\s*==\s*429\b", first)) and found.group(1) != "429":
        return "where 429 =" in message  # the 429 is the response, not the expectation
    listed = re.match(r"(?i)^assert\s+429\s+in\s+[(\[]([^)\]]*)[)\]]", first)
    return bool(listed) and "429" not in listed.group(1)


def classify_failure(message: str) -> str:
    """Port of diagnose-failure.ts, with the failures seen on real repositories. Only drift classes may be healed; DEFECT stays a failing test.

    A failure whose first line is an assertion is never ENVIRONMENT, so words inside an assertion cannot hide a real failure.
    The one exception is a 429 where the test expected another status: the application's own rate limiter answered.
    """
    text = message.lower()
    if _rate_limited(message):
        return "ENVIRONMENT"
    if ASSERTION_LINE.match(_first_line(message)):
        return "SELECTOR_DRIFT" if re.search(r"locator|selector|getby|strict mode violation", text) else "DEFECT"
    if "cannot import name" in text:  # the module exists but the test asks for a wrong name: the test is wrong, not the machine
        return "FIXTURE_DRIFT"
    if ENV_EVIDENCE.search(text):
        return "ENVIRONMENT"
    if re.search(r"locator|selector|getby|element not found|no element|waiting for|strict mode violation", text):
        return "SELECTOR_DRIFT"
    if re.search(r"fixture|keyerror|filenotfounderror|seed|attributeerror: 'nonetype'|typeerror: .*(argument|keyword)", text):
        return "FIXTURE_DRIFT"
    return "DEFECT"


# The rows of skills/healing-tests/references/HEALING_PATTERNS.md, plus the environment signatures seen on real repositories.
HEALING_PATTERNS = {
    "DEFECT": {"pattern": "Real App Bug", "cause": "The test ran and its assertion about the application's behaviour failed.",
               "fix": "Fix the application so it meets the requirement. The test is not changed and stays failing until then. Forbidden: weakening the assertion."},
    "SELECTOR_DRIFT": {"pattern": "Selector Drift", "cause": "The page no longer has the element the test looks for.",
                       "fix": "Update the selector to a stable one such as getByRole or getByTestId. Forbidden: deleting the interaction step."},
    "FIXTURE_DRIFT": {"pattern": "Fixture Outdated", "cause": "The test passes data or arguments the code does not accept, or reads data that is not there.",
                      "fix": "Correct the fixture or the call to match the real signature or schema. Forbidden: removing the request or the assertion."},
    "ENVIRONMENT": {"pattern": "Environment", "cause": "The test could not run properly in this environment.",
                    "fix": "Fix the environment: install the missing package, or provide the service. The application is not at fault."},
}
SPECIFIC = (  # evidence signature to a more exact cause and fix; the first match wins
    (re.compile(r"(?i)429 too many|assert 429|where 429"), "The application's rate limiter answered 429 because the test sent more requests than it allows.", "Reset or disable the limiter in a fixture, or send fewer requests. Expect 429 only when the case says so."),
    (re.compile(r"(?i)no module named '([^']+)'"), "The package '{0}' is not installed in the test environment.", "Install '{0}' as a dependency of the repository, or stop importing it in the test."),
    (re.compile(r"(?i)not natively supported|pytest.mark.asyncio"), "The test is async and pytest-asyncio is not installed.", "Install pytest-asyncio and run with asyncio_mode=auto, or write a synchronous test."),
    (re.compile(r"(?i)connecterror|connection refused|econnrefused|all connection attempts failed|errno 111|errno 61|winerror 10061"), "The test needs a running server and nothing is listening.", "Call the application object through a test client, or start the application before the test."),
    (re.compile(r"(?i)got an unexpected keyword argument '([^']+)'"), "The test passes the keyword '{0}', which the function or class does not accept.", "Call it with the parameter names of the real signature."),
    (re.compile(r"(?i)missing (\d+) required (?:positional|keyword-only) arguments?"), "The test omits arguments the function requires.", "Pass every required argument of the real signature."),
    (re.compile(r"(?i)cannot import name '([^']+)'"), "The test imports the name '{0}', which the module does not have.", "Import a name the module really defines."),
)


def failure_record(case: dict, klass: str, healed: bool = False, note: dict | None = None) -> dict:
    """One failed test as a defect record: what failed, how it is classified, the evidence, and the cause and fix from the healing patterns.

    `note` may carry sharper `cause` and `fix` text from the defect diagnostician. The classification is never taken from it.
    """
    from backend.core.security import redact

    message = case.get("message", "")
    pattern = HEALING_PATTERNS[klass]
    cause, fix = pattern["cause"], pattern["fix"]
    for regex, specific_cause, specific_fix in SPECIFIC:
        if klass != "DEFECT" and (found := regex.search(message)):
            cause, fix = specific_cause.format(*found.groups()), specific_fix.format(*found.groups())
            break
    if note:
        cause, fix = (str(note.get("cause") or cause)[:600], str(note.get("fix") or fix)[:600])
    case_id = next(iter(re.findall(r"TC[-_][\w-]*\d+", f"{case.get('classname', '')} {case.get('name', '')}", re.I)), "")
    return {"test": f"{case.get('classname', '')}::{case.get('name', '')}", "case_id": case_id.upper().replace("_", "-"), "classification": CLASSIFICATION[klass], "class": klass,
            "evidence": redact(message)[:600], "cause": cause, "fix": fix, "pattern": pattern["pattern"], "healed": healed}


def failure_counts(results: list[dict]) -> dict:
    """Failed tests by class, from the JUnit results. Every failure is counted once and none is hidden."""
    counts = {"defect": 0, "test problem": 0, "environment": 0}
    for suite in results:
        for case in suite.get("cases", []):
            if case["status"] == "failed":
                counts[CLASSIFICATION[classify_failure(case["message"])]] += 1
    return counts


def environment_facts(worktree: Path, declared: set[str] | frozenset = frozenset()) -> dict:
    """What the sandbox Python has, read without changing anything: httpx version, pytest-asyncio, and rate limiters in the application."""
    from backend.qe import emit
    from backend.repos import scan

    python = detect_python(worktree)
    inv = emit.inventory(python)
    versions = inv["versions"] if inv else {}
    limiters = [{"kind": name, "where": "dependency"} for name in LIMITER_PACKAGES if name in versions or name in declared]
    sources = [p for p in scan.tree(worktree, 5000) if p.endswith(".py") and not p.startswith(("tests/", "test/")) and "/tests/" not in p]
    for rel in sources[:600]:
        text = scan._read(worktree / rel)
        if found := LIMITER_CODE.search(text):
            limiters.append({"kind": "in-repository", "where": f"{rel}:{text.count(chr(10), 0, found.start()) + 1}"})
        if len(limiters) >= 6:
            break
    return {"python": python, "inventory": inv is not None, "httpx": versions.get("httpx"), "httpx_declared": "httpx" in declared, "pytest_asyncio": "pytest-asyncio" in versions,
            "pytest_asyncio_declared": "pytest-asyncio" in declared, "rate_limiters": limiters}


LIMITER_PACKAGES = ("slowapi", "flask-limiter", "fastapi-limiter", "django-ratelimit", "ratelimit")
LIMITER_CODE = re.compile(r"\bLimiter\(|@\w*limiter\.limit|\bRateLimit\w*\(|\brate_limit\w*|\bratelimit\b|slowapi|flask_limiter|status_code\s*=\s*429|HTTP_429")


def environment_notes(facts: dict, install_deps: bool = False) -> str:
    """Instructions for the generation prompt, built only from what was detected."""
    notes = []
    version = tuple(int(x) for x in re.findall(r"\d+", facts.get("httpx") or "")[:2])
    if version >= (0, 28):
        notes.append(f"httpx {facts['httpx']} is installed. It no longer accepts app=. For an ASGI app use httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test'); for a WSGI app use httpx.WSGITransport(app=app).")
    elif version:
        notes.append(f"httpx {facts['httpx']} is installed. Use app= only if that version accepts it; httpx.ASGITransport(app=app) works on it too.")
    elif facts.get("httpx_declared"):
        notes.append("httpx is a dependency but its version is not known yet. Use transport=httpx.ASGITransport(app=app) and never app=, which new versions removed.")
    if facts.get("pytest_asyncio"):
        notes.append("pytest-asyncio is available and the platform runs with asyncio_mode=auto, so async def tests need no marker.")
    elif install_deps:
        notes.append("pytest-asyncio will be installed before the tests run, and the platform runs with asyncio_mode=auto, so async def tests need no marker.")
    else:
        notes.append("pytest-asyncio is NOT available. Write only synchronous tests and call asyncio.run() for any coroutine.")
    if facts.get("rate_limiters"):
        where = ", ".join(f"{x['kind']} ({x['where']})" for x in facts["rate_limiters"][:4])
        notes.append(f"The application has a rate limiter: {where}. Reset or disable it in a fixture (for example limiter.reset() or limiter.enabled = False) and send as few requests as the case needs. Never expect 429 unless the case says so.")
    notes.append("Do not assume a server is running on any port. Call the application object through its test client.")
    return "ENVIRONMENT (detected on this machine):\n" + "\n".join(f"- {n}" for n in notes)


def async_test_files(worktree: Path, target: str = "tests/agentic_qe") -> list[str]:
    folder = worktree / target
    if not folder.is_dir():
        return []
    return sorted(p.relative_to(worktree).as_posix() for p in folder.rglob("*.py") if re.search(r"^\s*async def test_|pytest\.mark\.asyncio", p.read_text(encoding="utf-8", errors="replace"), re.M))


def install_pytest_asyncio(worktree: Path, log) -> bool:
    """Argument list, no shell, a timeout, and the scrubbed environment. Only reached after the run's install opt-in."""
    python = detect_python(worktree)
    done = subprocess.run([python, "-m", "pip", "install", "-q", "pytest-asyncio"], cwd=worktree, env=clean_env(), capture_output=True, text=True, errors="replace", timeout=300)
    log(f"pip exit {done.returncode}: pytest-asyncio" + (f" {done.stderr.strip()[-200:]}" if done.returncode else ""))
    return done.returncode == 0


def code_summary(result: dict) -> str:
    """The summary code writes itself. It is what is shown when the agent's summary is missing or refused."""
    text = f"{result['runner']}: {result['verdict']}. {result['passed']} passed, {result['failed']} failed, {result['skipped']} skipped."
    if result["failed"]:
        counts = failure_counts([result])
        text += f" Failures by class: {counts['defect']} defect, {counts['test problem']} test problem, {counts['environment']} environment. Environment failures count as not passed."
    return text + (f" {result['reason']}." if result.get("reason") else "")


def summary_evidence(result: dict, limit: int = 15) -> dict:
    """What the qa-execution-engineer is given: counts, the verdict, and the first failures with their class. Nothing else."""
    failures = [{"test": f"{c['classname']}::{c['name']}", "class": CLASSIFICATION[classify_failure(c["message"])], "first_line": _first_line(c["message"])[:200]}
                for c in result["cases"] if c["status"] == "failed"]
    return {"runner": result["runner"], "verdict": result["verdict"], "exit_code": result["exit_code"], "reason": result.get("reason", ""), "executed": result["passed"] + result["failed"],
            "passed": result["passed"], "failed": result["failed"], "skipped": result["skipped"], "failures_by_class": failure_counts([result]), "failures": failures[:limit], "failures_not_shown": max(0, len(failures) - limit)}


def summary_problems(claim: dict, result: dict) -> list[str]:
    """Checks the agent's summary against the JUnit counts. Any problem means the summary is refused."""
    problems = [f"it says {key} {claim.get(key)} but the report has {result[key]}" for key in ("passed", "failed", "skipped") if claim.get(key) != result[key]]
    if str(claim.get("verdict", "")).upper() != result["verdict"]:
        problems.append(f"it says the verdict is {claim.get('verdict')} but it is {result['verdict']}")
    text = str(claim.get("summary", ""))
    counted = {"passed": result["passed"], "failed": result["failed"], "errors": result["failed"], "error": result["failed"], "skipped": result["skipped"]}
    for number, word in re.findall(r"(\d+)\s+(passed|failed|skipped|errors?)\b", text, re.I):
        if int(number) != counted[word.lower()]:
            problems.append(f"its text says {number} {word} but the report has {counted[word.lower()]}")
    totals = {result["passed"] + result["failed"], result["passed"] + result["failed"] + result["skipped"]}
    for number in re.findall(r"(\d+)\s+(?:tests?|test cases)\b", text, re.I):
        if int(number) not in totals:
            problems.append(f"its text says {number} tests but the report has {' or '.join(map(str, sorted(totals)))}")
    for word in set(re.findall(r"\b(PASS|FAIL|INCONCLUSIVE)\b", text)):
        if word != result["verdict"]:
            problems.append(f"its text says {word} but the verdict is {result['verdict']}")
    return problems


def heal_allowed(failures: list[dict], path: str) -> bool:
    """Healing may change only a test file whose failure is drift, or a support file of the generated tests (fixtures, conftest). Never application code, never a test that found a defect."""
    path = path.replace("\\", "/")
    if not path.startswith("tests/"):
        return False
    if not re.search(r"(^|/)test_[^/]*\.py$|\.test\.[jt]sx?$|\.spec\.[jt]sx?$", path):
        return True
    norm = lambda text: re.sub(r"[^a-z0-9]+", "_", text.lower())
    mine = re.compile(rf"(?<![a-z0-9]){re.escape(norm(Path(path).stem))}(?![a-z0-9])")
    return any(f["class"] in {"SELECTOR_DRIFT", "FIXTURE_DRIFT"} and mine.search(norm(f"{f['classname']} {f['name']}")) for f in failures)
