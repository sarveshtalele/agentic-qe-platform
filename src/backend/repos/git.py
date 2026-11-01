"""Git via subprocess without a shell. Tokens travel in env-scoped config, never in argv, URLs, or .git/config."""
from __future__ import annotations

import base64
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from backend.core.security import redact


class GitError(RuntimeError):
    pass


def _env(token: str | None) -> dict:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"}
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.extraHeader", "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}"})
    return env


def run(args: list[str], cwd: Path | None = None, token: str | None = None, timeout: int = 300, check: bool = True) -> str:
    git = shutil.which("git")
    if not git:
        raise GitError("git is not installed or not on PATH")
    try:
        done = subprocess.run([git, *args], cwd=cwd, env=_env(token), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git {args[0]} timed out after {timeout}s") from exc
    if check and done.returncode != 0:
        raise GitError(redact(done.stderr.strip() or done.stdout.strip() or f"git {args[0]} failed"))
    return done.stdout.strip()


def validate_url(url: str) -> str:
    """Accept https remotes only: file://, ssh:// and ext:: transports could read or execute locally."""
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise GitError("Only https:// git URLs are accepted")
    if parsed.username or parsed.password:
        raise GitError("Remove credentials from the URL. Use a saved connection instead")
    return url.strip()


def clone(url: str, target: Path, ref: str = "", token: str | None = None) -> None:
    """A full clone: scans, history, and fixes all work from the complete repository."""
    url = validate_url(url)
    args = ["-c", "core.symlinks=false", "clone", "--no-tags"]
    if ref:
        args += ["--branch", ref]
    run([*args, "--", url, str(target)], token=token, timeout=600)


def is_shallow(repo: Path) -> bool:
    return run(["rev-parse", "--is-shallow-repository"], cwd=repo, check=False) == "true"


def head(repo: Path) -> str:
    return run(["rev-parse", "HEAD"], cwd=repo, check=False)


def is_repo(repo: Path) -> bool:
    return (repo / ".git").exists()


def init_snapshot(repo: Path, message: str) -> None:
    """Give uploaded archives a baseline commit so changes can be diffed and reviewed."""
    if not is_repo(repo):
        run(["init", "-q", "-b", "main"], cwd=repo)
    commit_all(repo, message)


def commit_all(repo: Path, message: str) -> str:
    run(["add", "-A"], cwd=repo)
    if run(["status", "--porcelain"], cwd=repo):
        run(["-c", "user.name=Agentic QE Platform", "-c", "user.email=agentic-qe@localhost", "commit", "-q", "--no-verify", "-m", message], cwd=repo)
    return head(repo)


def add_worktree(repo: Path, target: Path, branch: str) -> None:
    run(["worktree", "prune"], cwd=repo)
    run(["worktree", "add", "-q", "-B", branch, str(target), "HEAD"], cwd=repo)


def remove_worktree(repo: Path, target: Path) -> None:
    run(["worktree", "remove", "--force", str(target)], cwd=repo, check=False)


def diff(worktree: Path) -> str:
    run(["add", "-A", "-N"], cwd=worktree)
    return run(["diff", "--no-color"], cwd=worktree)


def log(repo: Path, limit: int = 15) -> list[dict]:
    out = run(["log", f"-{limit}", "--pretty=format:%h\x1f%an\x1f%ad\x1f%s", "--date=short"], cwd=repo, check=False)
    return [dict(zip(("sha", "author", "date", "subject"), line.split("\x1f"))) for line in out.splitlines() if "\x1f" in line]


def push(worktree: Path, branch: str, token: str) -> None:
    run(["push", "-u", "origin", f"HEAD:refs/heads/{branch}"], cwd=worktree, token=token, timeout=300)
