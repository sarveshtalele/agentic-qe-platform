"""Pre-run checks for generated tests. Port of the idea behind emit-tests.ts: nothing a model wrote is run to find out it was wrong.

Python tests are read with `ast` only. Imports must resolve, imported names must exist, calls must fit the real signatures,
and third-party packages must be installed in the sandbox. When something cannot be known, nothing is reported: a false alarm
would send a correct test back to the model.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from backend.qe import execution

SIGNATURE_BUDGET = 6000  # characters of real signatures added to one generation request
PASS_THROUGH = {"staticmethod", "classmethod", "abstractmethod", "lru_cache", "cache", "override", "final", "overload"}  # decorators that keep a function's signature
RAISES = {"raises", "assertRaises", "assertRaisesRegex", "warns", "assertWarns"}
ALIASES = {"yaml": "pyyaml", "pil": "pillow", "cv2": "opencv-python", "sklearn": "scikit-learn", "bs4": "beautifulsoup4", "dateutil": "python-dateutil", "jwt": "pyjwt", "dotenv": "python-dotenv", "jose": "python-jose"}
INVENTORY = (
    "import json, sys\nfrom importlib import metadata as m\n"
    "versions = {}\nfor d in m.distributions():\n    n = d.metadata['Name']\n    if n:\n        versions[n.lower().replace('_', '-')] = d.version\n"
    "print(json.dumps({'modules': sorted(m.packages_distributions()), 'versions': versions, 'stdlib': sorted(sys.stdlib_module_names), 'python': sys.version.split()[0]}))\n"
)


def inventory(python: str) -> dict | None:
    """What the sandbox Python really has, read by that Python itself. None when it cannot be read, and then the third-party check is skipped.

    ponytail: one subprocess per call, no cache, because an install between two calls changes the answer.
    """
    try:
        done = subprocess.run([python, "-I", "-c", INVENTORY], capture_output=True, text=True, timeout=30, env=execution.clean_env(), errors="replace")
        data = json.loads(done.stdout) if done.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if not isinstance(data, dict) or not {"modules", "versions", "stdlib"} <= set(data):
        return None
    return {"modules": set(data["modules"]), "versions": data["versions"], "stdlib": set(data["stdlib"]), "python": data.get("python", "")}


def _normal(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def declared_dependencies(worktree: Path) -> set[str]:
    """Distribution names the repository declares, for runs that will install them. Normalized, without versions or extras."""
    found: set[str] = set()
    take = lambda spec: found.add(_normal(m.group(0))) if (m := re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", spec.strip())) else None
    for path in worktree.glob("requirements*.txt"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip() and not line.lstrip().startswith(("#", "-")):
                take(line)
    try:
        data = tomllib.loads((worktree / "pyproject.toml").read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return found
    project = data.get("project", {})
    for spec in [*project.get("dependencies", []), *(s for group in project.get("optional-dependencies", {}).values() for s in group), *(s for group in data.get("dependency-groups", {}).values() for s in group if isinstance(s, str))]:
        take(spec)
    found |= {_normal(k) for k in data.get("tool", {}).get("poetry", {}).get("dependencies", {})}
    return found


@dataclass
class Sig:
    name: str
    pos: list[str]  # positional parameters, positional-only first, `self` already dropped for methods
    posonly: int
    defaults: set[str]
    kwonly: list[str]
    kw_required: set[str]
    vararg: bool
    kwarg: bool
    text: str


def _sig(name: str, a: ast.arguments, drop: bool = False) -> Sig:
    posonly = [x.arg for x in a.posonlyargs]
    pos = posonly + [x.arg for x in a.args]
    nodes: list = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
    if drop and pos:
        pos, nodes, posonly = pos[1:], nodes[1:], posonly[1:]
    parts = []
    for i, (n, d) in enumerate(zip(pos, nodes)):
        parts.append(n if d is None else f"{n}={ast.unparse(d)}")
        if posonly and i == len(posonly) - 1:
            parts.append("/")
    kwonly = [x.arg for x in a.kwonlyargs]
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    elif kwonly:
        parts.append("*")
    for n, d in zip(kwonly, a.kw_defaults):
        parts.append(n if d is None else f"{n}={ast.unparse(d)}")
    if a.kwarg:
        parts.append("**" + a.kwarg.arg)
    return Sig(name, pos, len(posonly), {n for n, d in zip(pos, nodes) if d is not None}, kwonly, {n for n, d in zip(kwonly, a.kw_defaults) if d is None}, bool(a.vararg), bool(a.kwarg), f"{name}({', '.join(parts)})")


def _decorator_names(node) -> list[str]:
    names = []
    for d in node.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        names.append(target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "?"))
    return names


def _transparent(node) -> bool:
    return all(n in PASS_THROUGH for n in _decorator_names(node))


def _function_sig(node: ast.FunctionDef | ast.AsyncFunctionDef, drop: bool = False) -> Sig | None:
    return _sig(node.name, node.args, drop) if _transparent(node) else None


def _class_sig(cls: ast.ClassDef) -> Sig | None:
    body = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if any(n.name == "__new__" for n in body) or cls.keywords:
        return None
    init = next((n for n in body if n.name == "__init__"), None)
    if init:
        return _sig(cls.name, init.args, drop=True) if _transparent(init) else None
    decorators = _decorator_names(cls)
    if decorators == ["dataclass"] and not cls.bases and not any(isinstance(d, ast.Call) and d.keywords for d in cls.decorator_list):
        fields = [n for n in cls.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and "ClassVar" not in ast.unparse(n.annotation)
                  and not (isinstance(n.value, ast.Call) and any(k.arg == "init" for k in n.value.keywords))]
        text = ", ".join(f.target.id if f.value is None else f"{f.target.id}=..." for f in fields)
        return Sig(cls.name, [f.target.id for f in fields], 0, {f.target.id for f in fields if f.value is not None}, [], set(), False, False, f"{cls.name}({text})")
    if not cls.bases and not decorators:
        return Sig(cls.name, [], 0, set(), [], set(), False, False, f"{cls.name}()")  # a plain class with no __init__ takes no arguments
    return None


def _method_sig(cls: ast.ClassDef, name: str) -> Sig | None:
    method = next((n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name), None)
    if method is None or not _transparent(method):
        return None
    return _sig(f"{cls.name}.{name}", method.args, drop="staticmethod" not in _decorator_names(method))


def call_problem(call: ast.Call, sig: Sig) -> str | None:
    """What is wrong with this call against the signature, or None when it fits or cannot be known."""
    starred = any(isinstance(a, ast.Starred) for a in call.args)
    spread = any(k.arg is None for k in call.keywords)
    given = len(call.args)
    names = [k.arg for k in call.keywords if k.arg]
    if not starred and not sig.vararg and given > len(sig.pos):
        return f"passes {given} positional arguments but it accepts {len(sig.pos)}"
    if not sig.kwarg:
        allowed = set(sig.pos[sig.posonly:]) | set(sig.kwonly)
        if bad := [n for n in names if n not in allowed]:
            return f"passes the keyword argument {', '.join(repr(n) for n in bad)}, which it does not accept"
    if not starred and (twice := [n for n in names if n in sig.pos[:given] and sig.pos.index(n) >= sig.posonly]):
        return f"gives {twice[0]!r} twice, by position and by keyword"
    if not starred and not spread:
        missing = [n for i, n in enumerate(sig.pos) if n not in sig.defaults and i >= given and n not in names] + [n for n in sig.kw_required if n not in names]
        if missing:
            return f"does not pass the required argument {', '.join(repr(n) for n in missing)}"
    return None


def _shallow(statements):
    """Statements of a module level, including those inside if, try, with, and loops, but not inside functions or classes."""
    for node in statements:
        yield node
        if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.AsyncWith, ast.AsyncFor)):
            yield from _shallow(node.body)
            yield from _shallow(getattr(node, "orelse", []))
        elif isinstance(node, ast.Try):
            for block in (node.body, node.orelse, node.finalbody, *(h.body for h in node.handlers)):
                yield from _shallow(block)


@lru_cache(maxsize=512)
def _parse_cached(path: str, stamp: tuple) -> ast.Module | None:
    try:
        return ast.parse(Path(path).read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError, OSError):
        return None


def _parsed(path: Path) -> ast.Module | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return _parse_cached(str(path), (stat.st_mtime_ns, stat.st_size))


class Project:
    """Where local modules live: the repository root, `src/`, and the folder of the test itself (pytest puts that on the path)."""

    def __init__(self, worktree: Path, test_dir: Path):
        self.roots = [worktree, worktree / "src", test_dir]

    @staticmethod
    def locate(base: Path) -> Path | None:
        if base.with_suffix(".py").is_file():
            return base.with_suffix(".py")
        if (base / "__init__.py").is_file():
            return base / "__init__.py"
        return base if base.is_dir() else None

    def module(self, dotted: str) -> Path | None:
        for root in self.roots:
            if found := self.locate(root.joinpath(*dotted.split("."))):
                return found
        return None

    def is_local(self, top: str) -> bool:
        return any((root / f"{top}.py").is_file() or (root / top).is_dir() for root in self.roots)

    def resolve_from(self, path: Path, node: ast.ImportFrom) -> Path | None:
        if node.level:
            base = path.parent
            for _ in range(node.level - 1):
                base = base.parent
            return self.locate(base.joinpath(*node.module.split("."))) if node.module else self.locate(base)
        return self.module(node.module) if node.module else None

    def names(self, path: Path, depth: int = 0) -> set[str] | None:
        """Names a module offers. None when they cannot be known (a module `__getattr__`, a star import that cannot be followed)."""
        if path.is_dir():
            return {p.stem for p in path.glob("*.py")} | {p.name for p in path.iterdir() if p.is_dir()}
        tree = _parsed(path)
        if tree is None:
            return None
        names: set[str] = set()
        for node in ast.walk(tree):  # deliberately generous: a name defined anywhere counts, so a real name is never reported missing
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names.add(node.id)
            elif isinstance(node, ast.Import):
                names.update((a.asname or a.name).split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name != "*":
                        names.add(alias.asname or alias.name)
                        continue
                    target = self.resolve_from(path, node)
                    sub = self.names(target, depth + 1) if target and depth < 4 else None
                    if sub is None:
                        return None
                    names |= sub
        if "__getattr__" in names:
            return None
        if path.name == "__init__.py":
            names |= {p.stem for p in path.parent.glob("*.py")} | {p.name for p in path.parent.iterdir() if p.is_dir()}
        return names

    def find(self, path: Path, name: str, depth: int = 0) -> tuple[ast.AST, Path] | None:
        """The function or class `name` of a module, following re-exports."""
        tree = _parsed(path) if path.is_file() else None
        if tree is None or depth > 6:
            return None
        found = None
        for node in _shallow(tree.body):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
                found = node
        if found is not None:
            return found, path
        for node in _shallow(tree.body):
            if not isinstance(node, ast.ImportFrom):
                continue
            target = self.resolve_from(path, node)
            if target is None:
                continue
            for alias in node.names:
                if alias.name == "*":
                    if hit := self.find(target, name, depth + 1):
                        return hit
                elif (alias.asname or alias.name) == name:
                    return self.find(target, alias.name, depth + 1)
        return None


def _guarded_imports(tree: ast.Module) -> set[int]:
    """Imports inside `try` with an ImportError handler: the author expected them to fail."""
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(h.type is None or "ImportError" in ast.unparse(h.type) or "ModuleNotFoundError" in ast.unparse(h.type) or "Exception" in ast.unparse(h.type) for h in node.handlers):
            guarded |= {id(n) for stmt in node.body for n in ast.walk(stmt)}
    return guarded


def _chain(node: ast.AST) -> list[str] | None:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        return [node.id, *reversed(parts)]
    return None


def check_python(worktree: Path, path: str, code: str, env: dict | None = None, declared: set[str] | frozenset = frozenset()) -> list[str]:
    """Findings for one generated Python test. Each says where, what, and the real signature when there is one."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []  # execution.syntax_error reports this
    project = Project(worktree, (worktree / path).parent)
    stdlib = env["stdlib"] if env else set(sys.stdlib_module_names)
    guarded = _guarded_imports(tree)
    findings: list[str] = []
    classes: dict[str, tuple[ast.ClassDef, Path]] = {}
    functions: dict[str, tuple[ast.AST, Path]] = {}
    modules: dict[str, str] = {}  # local name to a dotted local module
    third: dict[str, str] = {}  # local name to the dotted name it has in a third-party package

    for node in ast.walk(tree):
        if id(node) in guarded:
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if project.is_local(top):
                    if project.module(alias.name) is None:
                        findings.append(f"{path}:{node.lineno}: module {alias.name} does not exist in this repository")
                    else:
                        modules[alias.asname or top] = alias.name if alias.asname else top
                elif top not in stdlib:
                    third[alias.asname or top] = alias.name if alias.asname else top
                    findings += _third_party(path, node.lineno, top, env, declared)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            top = node.module.split(".")[0]
            if not project.is_local(top):
                if top not in stdlib:
                    findings += _third_party(path, node.lineno, top, env, declared)
                    for alias in node.names:
                        third[alias.asname or alias.name] = f"{node.module}.{alias.name}"
                continue
            target = project.module(node.module)
            if target is None:
                findings.append(f"{path}:{node.lineno}: module {node.module} does not exist in this repository")
                continue
            available = project.names(target)
            for alias in node.names:
                if alias.name == "*":
                    continue
                if available is not None and alias.name not in available:
                    findings.append(f"{path}:{node.lineno}: {node.module} has no name {alias.name!r}" + (f". It has: {', '.join(sorted(n for n in available if not n.startswith('_'))[:30])}" if available else ""))
                    continue
                local = alias.asname or alias.name
                if hit := project.find(target, alias.name):
                    (classes if isinstance(hit[0], ast.ClassDef) else functions)[local] = hit  # type: ignore[assignment]
                elif project.module(f"{node.module}.{alias.name}") is not None:
                    modules[local] = f"{node.module}.{alias.name}"

    instances: dict[str, ast.ClassDef | None] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id in classes:
            made, name = classes[node.value.func.id][0], node.targets[0].id
            instances[name] = made if instances.get(name, made) is made else None  # a name assigned two different classes is not tracked

    def resolve(call: ast.Call) -> Sig | None:
        chain = _chain(call.func)
        if not chain:
            return None
        if len(chain) == 1:
            if chain[0] in functions:
                node = functions[chain[0]][0]
                return _function_sig(node) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else None
            return _class_sig(classes[chain[0]][0]) if chain[0] in classes else None
        if chain[0] in classes and len(chain) == 2:
            return _method_sig(classes[chain[0]][0], chain[1])
        if chain[0] in instances and instances[chain[0]] is not None and len(chain) == 2:
            return _method_sig(instances[chain[0]], chain[1])
        if chain[0] in modules:
            dotted = [*modules[chain[0]].split("."), *chain[1:]]
            for cut in range(len(dotted) - 1, 0, -1):  # the longest module prefix that exists, then the function or class in it
                target = project.module(".".join(dotted[:cut]))
                if target is None or not target.is_file():
                    continue
                hit = project.find(target, dotted[cut])
                rest = dotted[cut + 1:]
                if hit is None:
                    return None
                if isinstance(hit[0], ast.ClassDef):
                    return _class_sig(hit[0]) if not rest else _method_sig(hit[0], rest[0]) if len(rest) == 1 else None
                return _function_sig(hit[0]) if not rest and isinstance(hit[0], (ast.FunctionDef, ast.AsyncFunctionDef)) else None
        return None

    httpx_version = tuple(int(x) for x in re.findall(r"\d+", (env or {}).get("versions", {}).get("httpx", ""))[:2])

    class Calls(ast.NodeVisitor):
        def visit_With(self, node):
            if any(isinstance(i.context_expr, ast.Call) and (c := _chain(i.context_expr.func)) and c[-1] in RAISES for i in node.items):
                return  # a test may call a function wrongly on purpose to see it raise
            self.generic_visit(node)

        def visit_Try(self, node):
            catches = any(h.type is not None and "TypeError" in ast.unparse(h.type) for h in node.handlers)
            for block in ([] if catches else node.body, node.orelse, node.finalbody, *(h.body for h in node.handlers)):
                for stmt in block:
                    self.visit(stmt)

        def visit_Call(self, node):
            chain = _chain(node.func)
            if chain and chain[0] in third and httpx_version >= (0, 28):
                full = ".".join([third[chain[0]], *chain[1:]])
                if full in {"httpx.AsyncClient", "httpx.Client"} and any(k.arg == "app" for k in node.keywords):
                    findings.append(f"{path}:{node.lineno}: {full}(app=...) was removed in httpx 0.28 and this environment has {'.'.join(map(str, httpx_version))}. Use transport=httpx.ASGITransport(app=app) for an ASGI app or httpx.WSGITransport(app=app) for a WSGI app, with base_url='http://test'")
            if (sig := resolve(node)) and (problem := call_problem(node, sig)):
                findings.append(f"{path}:{node.lineno}: the call {ast.unparse(node.func)}(...) {problem}. Real signature: {sig.text}")
            self.generic_visit(node)

    Calls().visit(tree)
    return findings


def _third_party(path: str, line: int, top: str, env: dict | None, declared: set[str] | frozenset) -> list[str]:
    if env is None or top in env["modules"] or _normal(top) in declared or ALIASES.get(top.lower(), "") in declared:
        return []  # without an inventory nothing can be said
    return [f"{path}:{line}: the package {top!r} is not installed in the test environment. Use only the standard library, pytest, and what the repository's code already imports"]


JS_EXTENSIONS = ("", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs", ".json", "/index.js", "/index.ts")
JS_IMPORT = re.compile(r"""(?:\bfrom\s+|\brequire\(\s*|\bimport\(\s*|\bimport\s+)['"](\.{1,2}/[^'"]*)['"]""")


def check_js(worktree: Path, path: str, code: str) -> list[str]:
    """ponytail: JavaScript and TypeScript get only a check that a relative import path exists. Names and calls are not checked, because that needs the TypeScript compiler. Add it with a Node step."""
    base = (worktree / path).parent
    return [f"{path}: the import {target!r} does not exist" for target in dict.fromkeys(JS_IMPORT.findall(code)) if not any((base / (target + ext)).is_file() for ext in JS_EXTENSIONS)]


def check(worktree: Path, path: str, code: str, env: dict | None = None, declared: set[str] | frozenset = frozenset()) -> list[str]:
    if path.endswith(".py"):
        return check_python(worktree, path, code, env, declared)
    if path.endswith((".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs")):
        return check_js(worktree, path, code)
    return []


def signatures(worktree: Path, paths: list[str], budget: int = SIGNATURE_BUDGET) -> str:
    """The real signatures of the public functions and classes in the files under test, so a test is written against them. Bounded by `budget`."""
    lines, used = [], 0
    for rel in paths:
        file = worktree / rel
        tree = _parsed(file) if rel.endswith(".py") and file.is_file() else None
        if tree is None:
            continue
        dotted = ".".join(Path(rel[4:] if rel.startswith("src/") else rel).with_suffix("").parts).removesuffix(".__init__")
        entries = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_") and _transparent(node):
                entries.append(("async " if isinstance(node, ast.AsyncFunctionDef) else "") + _sig(node.name, node.args).text)
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                sig = _class_sig(node)
                methods = [("async " if isinstance(m, ast.AsyncFunctionDef) else "") + _sig(m.name, m.args, drop="staticmethod" not in _decorator_names(m)).text
                           for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("_") and _transparent(m)]
                entries.append(f"class {sig.text if sig else node.name + '(...)'}" + (f" with methods {'; '.join(methods[:12])}" if methods else ""))
        if not entries:
            continue
        block = f"from {dotted} import ...  ({rel})\n" + "\n".join(f"  {e}" for e in entries) + "\n"
        if used + len(block) > budget:
            break
        lines.append(block)
        used += len(block)
    return ("REAL SIGNATURES. Call these exactly, with these parameter names:\n" + "\n".join(lines)) if lines else ""
