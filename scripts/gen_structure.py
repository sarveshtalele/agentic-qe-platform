"""Write docs/PROJECT_STRUCTURE.md from the code itself: each file's purpose and its real import links.

  python scripts/gen_structure.py
"""
from __future__ import annotations

import ast
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "docs" / "PROJECT_STRUCTURE.md"
SKIP = ("legacy/", "docs/evidence/", "src/frontend/public/", "dist/")
GROUPS = [
    ("Backend application", "src/backend/app.py", "src/backend/config.py", "src/backend/db.py"),
    ("REST API", "src/backend/api/"),
    ("Agents", "src/backend/maf/agents/"),
    ("Tools", "src/backend/maf/tools/"),
    ("Workflows", "src/backend/maf/workflows/"),
    ("Agent runtime and governance", "src/backend/maf/"),
    ("Core services", "src/backend/core/"),
    ("Repositories", "src/backend/repos/"),
    ("Quality engineering", "src/backend/qe/"),
    ("Database migrations", "src/backend/migrations/"),
    ("Agent prompts", "prompts/"),
    ("Agent evaluations", "evals/"),
    ("Document templates", "templates/"),
    ("Frontend pages", "src/frontend/app/"),
    ("Frontend components and content", "src/frontend/components/", "src/frontend/lib/", "src/frontend/content/"),
    ("Frontend configuration", "src/frontend/"),
    ("Tests", "tests/"),
    ("Scripts and deployment", "scripts/", "deploy/", "start-"),
    ("Documentation", "docs/"),
]
PURPOSE = {
    "README.md": "Project overview, setup, and links", "CLAUDE.md": "Rules for changing this project", "plan.md": "Design decisions and reuse audit", "specs.md": "Requirements with acceptance checks",
    "tasks.md": "Status of all work", "Design.md": "UI design rules", "maf-guide.md": "Microsoft Agent Framework features used, by file", "progress.md": "Timestamped activity log written by hooks",
    "requirements.txt": "Python dependencies", "pytest.ini": "Test settings", ".env.example": "Settings template", ".gitignore": "Files kept out of Git", ".mcp.json": "Developer MCP servers for Claude Code",
    ".github/workflows/ci.yml": "Tests on Windows, macOS, and Linux", ".claude/settings.json": "Hooks that write progress.md", "start-windows.bat": "Double-click launcher for Windows", "start-mac.command": "Double-click launcher for macOS",
    "src/frontend/package.json": "Node dependencies and scripts", "src/frontend/package-lock.json": "Exact Node dependency versions", "src/frontend/next.config.ts": "Next.js settings and the API proxy", "src/frontend/tsconfig.json": "TypeScript settings",
    "src/frontend/eslint.config.mjs": "Lint rules", "src/frontend/postcss.config.mjs": "CSS build settings", "src/frontend/app/globals.css": "Design tokens and document styles", "src/frontend/app/layout.tsx": "Root HTML layout, theme, and toasts",
    "src/frontend/app/api/copilotkit/[[...path]]/route.ts": "CopilotKit runtime, connecting chat to the AG-UI endpoint", "src/frontend/components/AppShell.tsx": "Workspace sidebar and header", "src/frontend/components/ProjectShell.tsx": "Project sidebar and header",
    "src/frontend/components/RunPanel.tsx": "Live run view, approval card, and past runs", "src/frontend/components/Chat.tsx": "Chat threads and conversation", "src/frontend/components/ApprovalsList.tsx": "List of pending approvals",
    "src/frontend/components/DocumentEditor.tsx": "Formatted document with in-place editing, table grids, and images", "src/frontend/components/Observability.tsx": "Log with filters, run trace, and download", "src/frontend/components/ui.tsx": "Shared buttons, cards, badges, fields, and toasts", "src/frontend/lib/api.ts": "Browser calls to the API", "src/frontend/content/docs.ts": "All documentation pages",
    "deploy/azure/frontend_startup.js": "App Service startup for the frontend: builds when needed, then serves", "docs/ARCHITECTURE.md": "Plugin to platform mapping and workflow details", "docs/AZURE_DEPLOY.md": "Portal guide for Azure with INR costs",
    "docs/REUSE_AUDIT.md": "Which earlier code was reused and which was replaced", "docs/SYSTEM_DESIGN.md": "End-to-end system design", "src/backend/__init__.py": "Marks the backend package", "src/frontend/.gitignore": "Frontend files kept out of Git",
    "src/frontend/AGENTS.md": "Notes for coding agents about this Next.js version", "src/frontend/app/projects/[id]/layout.tsx": "Wraps project pages in the project sidebar", "tests/__init__.py": "Marks the tests package", "tests/e2e/__init__.py": "Marks the end-to-end tests package",
    "src/frontend/app/docs/layout.tsx": "Documentation site frame: search and sidebar", "docs/PROJECT_STRUCTURE.md": "This file",
}


def listed() -> list[str]:
    names = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, check=True, timeout=60).stdout.splitlines()
    return sorted(n for n in names if (ROOT / n).is_file() and not n.startswith(SKIP))


def _python(name: str, source: str, known: set[str]) -> tuple[str, set[str]]:
    tree = ast.parse(source)
    doc = (ast.get_docstring(tree) or "").split("\n")[0]
    uses = set()
    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            modules = [node.module, *(f"{node.module}.{a.name}" for a in node.names)]
        elif isinstance(node, ast.Import):
            modules = [a.name for a in node.names]
        for module in modules:
            base = "src/" + module.replace(".", "/") if module.startswith("backend") else module.replace(".", "/")
            for candidate in (f"{base}.py", f"{base}/__init__.py"):
                if candidate in known and candidate != name:
                    uses.add(candidate)
    return doc, uses


def _script(name: str, source: str, known: set[str]) -> set[str]:
    uses = set()
    for target in re.findall(r"""(?:from|import)\s+['"](\.[^'"]+)['"]""", source):
        base = (Path(name).parent / target).as_posix()
        parts: list[str] = []
        for part in base.split("/"):
            if part == "..":
                parts.pop()
            elif part != ".":
                parts.append(part)
        resolved = "/".join(parts)
        uses |= {c for c in (resolved, f"{resolved}.ts", f"{resolved}.tsx", f"{resolved}/index.ts") if c in known}
    return uses


def _purpose(name: str, doc: str) -> str:
    if name in PURPOSE:
        return PURPOSE[name]
    if doc:
        return doc
    path = Path(name)
    if name.startswith("src/frontend/app/") and path.name == "page.tsx":
        route = "/" + "/".join(path.parts[3:-1])
        return f"Page at `{route if route != '/' else '/'}`".replace("[", "{").replace("]", "}")
    if name.startswith("prompts/"):
        return f"System prompt for the {path.stem} agent"
    if name.startswith("evals/"):
        return f"Quality and safety cases for the {path.stem} agent"
    if name.startswith("templates/"):
        return f"Built-in {path.stem} template"
    if name.startswith("src/backend/migrations/"):
        return f"Database change: {path.stem.split('_', 1)[-1].replace('_', ' ')}"
    return ""


def _short(name: str) -> str:
    return "`" + name.replace("src/backend/", "").replace("src/frontend/", "ui/") + "`"


def main() -> None:
    names = listed()
    known = set(names)
    purposes, uses = {}, {}
    for name in names:
        source = (ROOT / name).read_text(encoding="utf-8", errors="replace")
        doc, links = "", set()
        if name.endswith(".py"):
            doc, links = _python(name, source, known)
        elif name.endswith((".ts", ".tsx")):
            links = _script(name, source, known)
        purposes[name], uses[name] = _purpose(name, doc), links
    used_by = defaultdict(set)
    for name, links in uses.items():
        for link in links:
            used_by[link].add(name)
    lines = ["# Project structure", "", "Generated by `python scripts/gen_structure.py`, so links come from the real imports. Run it again after adding files.", "",
             "In this table, `ui/` means `src/frontend/`, and backend paths start from `src/backend/`.", "", "## How the parts connect", "", "```mermaid", "flowchart LR",
             "  UI[Next.js pages and components] -->|/api proxy| API[api routers]", "  UI -->|CopilotKit route| AGUI[maf/agui.py]", "  API --> ENGINE[maf/engine.py]", "  API --> CORE[core services]", "  ENGINE --> WF[maf/workflows]",
             "  WF --> RT[maf/runtime.py]", "  AGUI --> RT", "  RT --> AG[maf/agents policies]", "  RT --> TOOLS[maf/tools]", "  RT --> GOV[maf/governance.py]", "  RT --> LLM[maf/llm.py]", "  WF --> REPOS[repos]", "  WF --> QE[qe]", "  WF --> CORE",
             "  GOV --> OBS[maf/observability.py]", "  TOOLS --> OBS", "  CORE --> DB[(SQLite)]", "  OBS --> DB", "  REPOS --> SBX[(Project sandbox)]", "  QE --> SBX", "```", "", f"The project has {len(names)} files, not counting `legacy/` and screenshots.", ""]
    remaining = list(names)
    for title, *prefixes in [*GROUPS, ("Project root", "")]:
        members = [n for n in remaining if any(n.startswith(p) for p in prefixes)]
        if not members:
            continue
        remaining = [n for n in remaining if n not in members]
        lines += [f"## {title}", "", "| File | What it does | Uses | Used by |", "|---|---|---|---|"]
        for name in members:
            shown = lambda items: ", ".join(_short(i) for i in sorted(items)[:8]) + (f", and {len(items) - 8} more" if len(items) > 8 else "") if items else ""
            lines.append(f"| `{name}` | {purposes[name].replace('|', '/')} | {shown(uses[name])} | {shown(used_by[name])} |")
        lines.append("")
    TARGET.write_text("\n".join(lines), encoding="utf-8")
    missing = [n for n in names if not purposes[n]]
    print(f"Wrote {TARGET.relative_to(ROOT)}: {len(names)} files, {len(missing)} without a description: {missing}")


if __name__ == "__main__":
    main()
