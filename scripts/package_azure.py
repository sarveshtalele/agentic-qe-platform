"""Make the Azure ZIPs and a clean production repository in dist/. Nothing outside dist/ changes.

  python scripts/package_azure.py          backend and frontend ZIPs
  python scripts/package_azure.py --repo   also dist/agentic-qe-platform, a clean copy of the project
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"__pycache__", "node_modules", ".pytest_cache", ".ruff_cache", ".venv", "test-results"}
SKIP_NAMES = {".env", ".env.local", ".DS_Store"}
NOT_IN_REPO = ("agent-framework.pdf", "dist/", ".mcp.json")


def _files(folder: Path):
    for path in sorted(folder.rglob("*")):
        parts = path.relative_to(ROOT).parts
        if path.is_file() and path.name not in SKIP_NAMES and not path.is_symlink() and not any(p in SKIP_DIRS or p.startswith(".next") for p in parts):
            yield path


def _write(target: Path, entries: dict[str, Path]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, source in sorted(entries.items()):
            archive.write(source, name)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    print(f"{target.relative_to(ROOT)}  {target.stat().st_size / 1_048_576:.1f} MB  {len(entries)} files  sha256 {digest[:16]}")


def backend_entries() -> dict[str, Path]:
    entries = {"startup.py": ROOT / "deploy/azure/backend_startup.py", "requirements.txt": ROOT / "requirements.txt"}
    for folder in ("src/backend", "prompts", "templates", "evals", "skills"):
        entries.update({path.relative_to(ROOT).as_posix(): path for path in _files(ROOT / folder)})
    return entries


def frontend_entries() -> dict[str, Path]:
    base = ROOT / "src/frontend"
    return {"startup.js": ROOT / "deploy/azure/frontend_startup.js", **{path.relative_to(base).as_posix(): path for path in _files(base)}}


def export_repo(target: Path) -> None:
    listed = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True, check=True, timeout=60).stdout.splitlines()
    if target.exists():
        shutil.rmtree(target)
    count = 0
    for name in listed:
        source = ROOT / name
        if name.startswith(NOT_IN_REPO) or not source.is_file():
            continue
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        count += 1
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=target, check=True, timeout=30)
    print(f"{target.relative_to(ROOT)}  {count} files, new git repository with no commits")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", action="store_true", help="also export a clean repository to dist/agentic-qe-platform")
    args = parser.parse_args()
    dist = ROOT / "dist"
    _write(dist / "agentic-qe-backend.zip", backend_entries())
    _write(dist / "agentic-qe-frontend.zip", frontend_entries())
    if args.repo:
        export_repo(dist / "agentic-qe-platform")


if __name__ == "__main__":
    main()
