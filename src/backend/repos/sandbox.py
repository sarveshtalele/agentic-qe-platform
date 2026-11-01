"""Each project's sandbox: its own folder with a full clone, one worktree per run, its own Python environment.

Test code runs with clean_env(), so it cannot see platform secrets.
ponytail: this isolates by folder and environment, not by operating system. Use a container per project before running repositories you do not trust.
"""
from __future__ import annotations

from backend.config import project_dir, repo_dir
from backend.db import db, row
from backend.repos import git, github


def complete_history(project_id: str) -> bool:
    """Older clones were shallow. Returns True when missing history was fetched."""
    repo = repo_dir(project_id)
    if not git.is_shallow(repo):
        return False
    with db() as con:
        source = row(con.execute("SELECT credential_id FROM repo_sources WHERE project_id=?", (project_id,)))
    git.run(["fetch", "--unshallow", "--no-tags", "origin"], cwd=repo, token=github.token_for(source["credential_id"]) if source else None, timeout=600)
    return True


def info(project_id: str) -> dict:
    root, repo = project_dir(project_id), repo_dir(project_id)
    worktrees = root / "worktrees"
    runs = [p.name for p in worktrees.iterdir() if p.is_dir() and p.name.startswith("run_") and not p.name.endswith(("-results", "-baseline"))] if worktrees.exists() else []
    size = sum(p.stat().st_size for p in root.rglob("*") if p.is_file() and not p.is_symlink() and ".venv" not in p.parts)
    return {"path": str(root), "commit": git.head(repo), "complete_history": not git.is_shallow(repo), "commits": git.run(["rev-list", "--count", "HEAD"], cwd=repo, check=False),
            "run_worktrees": len(runs), "python_environment": (worktrees / ".venv").exists(), "size_mb": round(size / 1_048_576, 1)}
