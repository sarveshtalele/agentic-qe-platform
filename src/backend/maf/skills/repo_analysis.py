from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from .base import AgentSkill, maf_skill

SKIP_DIRS = {".git", "node_modules", "dist", "build", ".venv", ".qe", "docs", "bin", "obj", ".next", "__pycache__"}
SOURCE_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".py", ".java", ".go", ".rs", ".rb", ".cs", ".astro"}
TEST_RE = re.compile(r"(\.(test|spec)\.[a-z]+$|^test_.*\.py$|_test\.(py|go)$|Test\.java$|Tests?\.cs$)", re.IGNORECASE)


@maf_skill(name="analyzing_repositories", description="Scans repository layout, files, and detected frameworks")
class RepoAnalysisSkill(AgentSkill):
    """
    Ported from sarveshtalele/agentic-qe skills/analyzing-repositories/scripts/scan-repo.ts.
    Analyzes project tree to detect frameworks, count source vs test files, and detect package manifests.
    """

    def __init__(self):
        super().__init__(
            name="analyzing_repositories",
            description="Deep filesystem traversal to detect stack signals, test ratios, and manifests.",
            category="Discovery"
        )

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        repo_dir = context.get("repo_dir") or context.get("workspace_dir") or "."
        p = Path(repo_dir).expanduser().resolve()

        if not p.exists() or not p.is_dir():
            return {
                "valid": False,
                "error": f"Repository directory {repo_dir} does not exist",
                "source_files": 0,
                "test_files": 0,
                "frameworks": [],
            }

        source_count = 0
        test_count = 0
        sln_files = []
        csproj_files = []
        manifests = []
        detected_frameworks = set()

        for root, dirs, files in os.walk(str(p)):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fn in files:
                ext = Path(fn).suffix.lower()
                full_path = os.path.join(root, fn)
                rel_path = os.path.relpath(full_path, str(p))

                if fn in {"package.json", "pnpm-lock.yaml", "requirements.txt", "pyproject.toml", "Cargo.toml", "go.mod"}:
                    manifests.append(rel_path)

                if ext in {".sln", ".slnx"}:
                    sln_files.append(rel_path)
                elif ext == ".csproj":
                    csproj_files.append(rel_path)

                if ext in SOURCE_EXTS:
                    if TEST_RE.search(fn):
                        test_count += 1
                    else:
                        source_count += 1

                # Stack signals
                if fn == "astro.config.mjs" or ext == ".astro":
                    detected_frameworks.add("Astro")
                elif fn == "package.json":
                    detected_frameworks.add("Node.js")
                elif ext == ".py":
                    detected_frameworks.add("Python")
                elif ext in {".ts", ".tsx"}:
                    detected_frameworks.add("TypeScript")

        test_ratio = round((test_count / max(source_count, 1)) * 100, 1)

        return {
            "valid": True,
            "root_path": str(p),
            "source_files": source_count,
            "test_files": test_count,
            "source_files_count": source_count,
            "test_files_count": test_count,
            "test_to_source_ratio_pct": test_ratio,
            "frameworks": sorted(list(detected_frameworks)),
            "manifests": manifests[:10],
            "dotnet_sln": sln_files,
            "dotnet_csproj": csproj_files,
        }
