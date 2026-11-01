"""Evidence-only repository analysis: every field comes from files on disk. Port of plugin scan-repo.ts, extended."""
from __future__ import annotations

import ast
import json
import re
import tomllib
from collections import Counter
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", "target", "coverage", ".pytest_cache", ".mypy_cache", ".ruff_cache", "vendor", ".idea", ".vscode", "out", ".turbo", ".gradle"}
LANGUAGES = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".java": "Java", ".kt": "Kotlin", ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".swift": "Swift", ".c": "C", ".cpp": "C++", ".h": "C", ".astro": "Astro", ".vue": "Vue", ".svelte": "Svelte", ".sql": "SQL", ".sh": "Shell", ".html": "HTML", ".css": "CSS", ".scss": "CSS"}
TEST_NAME = re.compile(r"(^|/)(tests?|__tests__|spec|e2e)/|(^|/)test_[^/]+\.py$|_test\.(py|go)$|\.(test|spec)\.[jt]sx?$|Test\.java$")
ROUTE_PATTERNS = [
    (re.compile(r"@(?:app|router|\w+)\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)"), "py"),
    (re.compile(r"\b(?:app|router)\.(get|post|put|patch|delete)\(\s*['\"`]([^'\"`]+)"), "js"),
    (re.compile(r"@(Get|Post|Put|Patch|Delete)Mapping\(\s*(?:value\s*=\s*)?\"([^\"]+)"), "java"),
]
FRAMEWORK_DEPS = {"fastapi": "FastAPI", "flask": "Flask", "django": "Django", "next": "Next.js", "react": "React", "vue": "Vue", "svelte": "Svelte", "astro": "Astro", "express": "Express", "@nestjs/core": "NestJS", "spring-boot-starter-web": "Spring Boot", "angular": "Angular", "@angular/core": "Angular"}
RUNNER_DEPS = {"pytest": "pytest", "vitest": "vitest", "jest": "jest", "@playwright/test": "playwright", "playwright": "playwright", "mocha": "mocha", "junit": "junit", "junit-jupiter": "junit", "cypress": "cypress"}
MAX_PARSE_BYTES = 400_000


def iter_files(root: Path):
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in SKIP_DIRS:
                    stack.append(entry)
            elif entry.is_file():
                yield entry


def _read(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_PARSE_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        return ""


def _manifests(root: Path) -> dict:
    deps: dict[str, dict] = {}
    package_json = root / "package.json"
    scripts: dict = {}
    if package_json.exists():
        try:
            data = json.loads(_read(package_json) or "{}")
            deps["package.json"] = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            scripts = data.get("scripts", {})
        except json.JSONDecodeError:
            pass
    requirements = root / "requirements.txt"
    if requirements.exists():
        found = {}
        for line in _read(requirements).splitlines():
            match = re.match(r"^\s*([A-Za-z0-9_.\-]+)\s*(.*)$", line.split("#")[0])
            if match and match.group(1):
                found[match.group(1).lower()] = match.group(2).strip()
        deps["requirements.txt"] = found
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            data = tomllib.loads(_read(pyproject) or "")
            project = data.get("project", {})
            names = list(project.get("dependencies", []))
            for group in project.get("optional-dependencies", {}).values():
                names += group
            names += list(data.get("dependency-groups", {}).get("dev", [])) if isinstance(data.get("dependency-groups", {}).get("dev", []), list) else []
            deps["pyproject.toml"] = {re.split(r"[\s<>=!~\[;]", str(n))[0].lower(): str(n) for n in names}
            deps["pyproject.toml"].update({k.lower(): str(v) for k, v in data.get("tool", {}).get("poetry", {}).get("dependencies", {}).items()})
        except tomllib.TOMLDecodeError:
            pass
    pom = root / "pom.xml"
    if pom.exists():
        deps["pom.xml"] = {m: "" for m in re.findall(r"<artifactId>([^<]+)</artifactId>", _read(pom))}
    return {"dependencies": deps, "scripts": scripts}


def _python_symbols(text: str) -> tuple[list[str], list[str]]:
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return [], []
    symbols = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports += [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            imports.append(node.module.split(".")[0])
    return symbols, imports


def _js_symbols(text: str) -> tuple[list[str], list[str]]:
    symbols = re.findall(r"^export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|interface|type)\s+(\w+)", text, re.M)
    imports = re.findall(r"""(?:from|require\()\s*['"]([^'"]+)""", text)
    return symbols, [i for i in imports if not i.startswith(".")]


def analyze(root: Path) -> dict:
    languages: Counter = Counter()
    lines: Counter = Counter()
    tests: list[str] = []
    sources: list[dict] = []
    routes: list[dict] = []
    ci: list[str] = []
    docs: list[str] = []
    imports: Counter = Counter()
    entrypoints: list[str] = []
    total = 0
    for path in iter_files(root):
        total += 1
        relative = path.relative_to(root).as_posix()
        language = LANGUAGES.get(path.suffix.lower())
        if relative.startswith(".github/workflows/") or relative in {".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile"}:
            ci.append(relative)
        if path.suffix.lower() in {".md", ".rst"} and len(docs) < 30:
            docs.append(relative)
        if not language:
            continue
        text = _read(path)
        count = text.count("\n") + 1 if text else 0
        languages[language] += 1
        lines[language] += count
        if TEST_NAME.search(relative):
            tests.append(relative)
            continue
        symbols, deps = _python_symbols(text) if language == "Python" else _js_symbols(text) if language in {"TypeScript", "JavaScript"} else ([], [])
        imports.update(deps)
        sources.append({"path": relative, "language": language, "lines": count, "symbols": symbols[:40]})
        if path.name in {"main.py", "app.py", "manage.py", "wsgi.py", "asgi.py", "index.ts", "index.js", "main.ts", "main.go", "server.js", "server.ts", "Main.java", "page.tsx", "layout.tsx", "index.astro"} or "if __name__ ==" in text:
            entrypoints.append(relative)
        for pattern, _ in ROUTE_PATTERNS:
            for match in pattern.finditer(text):
                routes.append({"method": match.group(1).upper(), "path": match.group(2), "file": relative, "line": text[: match.start()].count("\n") + 1})
    manifest = _manifests(root)
    all_deps = {name.lower() for group in manifest["dependencies"].values() for name in group}
    frameworks = sorted({label for dep, label in FRAMEWORK_DEPS.items() if dep in all_deps})
    runners = sorted({label for dep, label in RUNNER_DEPS.items() if dep in all_deps})
    if not runners and any(t.endswith(".py") for t in tests):
        runners = ["pytest"]
    sources.sort(key=lambda s: -s["lines"])
    return {
        "mode": "brownfield" if languages else "greenfield",
        "total_files": total,
        "source_files": len(sources),
        "languages": dict(languages.most_common()),
        "lines_of_code": dict(lines.most_common()),
        "frameworks": frameworks,
        "test_runners": runners,
        "test_files": tests[:300],
        "test_file_count": len(tests),
        "entrypoints": entrypoints[:40],
        "routes": routes[:200],
        "ci": ci,
        "docs": docs,
        "dependencies": manifest["dependencies"],
        "scripts": manifest["scripts"],
        "top_imports": dict(imports.most_common(25)),
        "largest_sources": sources[:150],
    }


def tree(root: Path, limit: int = 2000) -> list[str]:
    out = []
    for path in iter_files(root):
        out.append(path.relative_to(root).as_posix())
        if len(out) >= limit:
            break
    return sorted(out)
