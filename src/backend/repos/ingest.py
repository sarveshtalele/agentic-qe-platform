"""Bring code into a project: clone a git URL (public or with a saved token) or unpack a ZIP safely."""
from __future__ import annotations

import json
import re
import shutil
import stat
import zipfile
from pathlib import Path

from backend.config import MAX_UPLOAD_BYTES, project_dir, repo_dir
from backend.core import ledger
from backend.db import db, now, row
from backend.repos import git, github, scan

MAX_ZIP_FILES = 100_000
MAX_RATIO = 200


class IngestError(ValueError):
    pass


def _rm_tree(path: Path) -> None:
    def retry(func, target, _exc):  # git pack files are read-only, which blocks deletion on Windows
        Path(target).chmod(stat.S_IWRITE)
        func(target)

    if path.exists():
        shutil.rmtree(path, onexc=retry)


def _record(project_id: str, kind: str, url: str, ref: str, credential_id: str | None, actor: str) -> dict:
    repo = repo_dir(project_id)
    analysis = scan.analyze(repo)
    commit = git.head(repo)
    with db() as con:
        con.execute("INSERT OR REPLACE INTO repo_sources VALUES (?,?,?,?,?,?,?,?)", (project_id, kind, url, ref, credential_id, commit, json.dumps(analysis), now()))
    ledger.append(project_id, actor, "repo.ingested", url or "zip", {"kind": kind, "commit": commit, "files": analysis["total_files"]})
    return get(project_id)


def from_git(project_id: str, url: str, ref: str = "", credential_id: str | None = None, actor: str = "user") -> dict:
    if re.fullmatch(r"[\w.-]+/[\w.-]+", url.strip()):  # owner/repo shorthand
        url = f"https://github.com/{url.strip()}"
    token = github.token_for(credential_id)
    project_dir(project_id).mkdir(parents=True, exist_ok=True)
    staging = project_dir(project_id) / "repo.incoming"
    _rm_tree(staging)
    git.clone(url, staging, ref, token)  # the current repo survives a failed clone
    _rm_tree(repo_dir(project_id))
    staging.replace(repo_dir(project_id))
    return _record(project_id, "git", url, ref, credential_id, actor)


def from_zip(project_id: str, archive: Path, filename: str, actor: str = "user") -> dict:
    project_dir(project_id).mkdir(parents=True, exist_ok=True)
    staging = project_dir(project_id) / "repo.incoming"
    _rm_tree(staging)
    staging.mkdir(parents=True)
    safe_extract(archive, staging)
    entries = [p for p in staging.iterdir() if p.name != "__MACOSX"]
    root = entries[0] if len(entries) == 1 and entries[0].is_dir() else staging  # unwrap "project-main/" folders
    _rm_tree(repo_dir(project_id))
    root.replace(repo_dir(project_id))
    _rm_tree(staging)
    _rm_tree(repo_dir(project_id) / "__MACOSX")
    git.init_snapshot(repo_dir(project_id), f"Agentic QE Platform snapshot of {filename}")
    return _record(project_id, "zip", filename, "", None, actor)


def from_local(project_id: str, folder: str, actor: str = "user") -> dict:
    """Copy a local folder into the project. The original is never modified and symlinks are not followed."""
    source = Path(folder).expanduser()
    if not source.is_dir():
        raise IngestError(f"Not a folder: {folder}")
    project_dir(project_id).mkdir(parents=True, exist_ok=True)
    staging = project_dir(project_id) / "repo.incoming"
    _rm_tree(staging)
    shutil.copytree(source, staging, symlinks=True, ignore=lambda _d, names: [n for n in names if n in scan.SKIP_DIRS and n != ".git"] + [n for n in names if (Path(_d) / n).is_symlink()])
    _rm_tree(repo_dir(project_id))
    staging.replace(repo_dir(project_id))
    if git.is_repo(repo_dir(project_id)):
        return _record(project_id, "local", str(source), "", None, actor)
    git.init_snapshot(repo_dir(project_id), f"Agentic QE Platform snapshot of {source.name}")
    return _record(project_id, "local", str(source), "", None, actor)


def safe_extract(archive: Path, target: Path) -> None:
    """Refuse traversal, absolute paths, symlinks, and zip bombs before anything reaches disk."""
    try:
        bundle = zipfile.ZipFile(archive)
    except zipfile.BadZipFile as exc:
        raise IngestError("The file is not a valid ZIP archive") from exc
    with bundle:
        infos = bundle.infolist()
        if len(infos) > MAX_ZIP_FILES:
            raise IngestError(f"ZIP has more than {MAX_ZIP_FILES} entries")
        total = sum(i.file_size for i in infos)
        if total > MAX_UPLOAD_BYTES * 10 or total > max(archive.stat().st_size, 1) * MAX_RATIO + 50_000_000:
            raise IngestError("ZIP expands too far and looks like a zip bomb")
        base = target.resolve()
        for info in infos:
            name = info.filename.replace("\\", "/")
            if stat.S_ISLNK(info.external_attr >> 16):
                continue  # symlinks can point outside the workspace, so they are dropped
            destination = (base / name).resolve()
            if not destination.is_relative_to(base):
                raise IngestError(f"ZIP entry escapes the workspace: {info.filename}")
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as source, destination.open("wb") as sink:
                shutil.copyfileobj(source, sink)


def resync(project_id: str, actor: str = "user") -> dict:
    current = get(project_id)
    if not current:
        raise IngestError("No repository connected")
    if current["kind"] != "git":
        raise IngestError("Only Git sources can re-sync. Upload a new ZIP or import the folder again")
    return from_git(project_id, current["url"], current["ref"], current["credential_id"], actor)


def get(project_id: str) -> dict | None:
    with db() as con:
        found = row(con.execute("SELECT * FROM repo_sources WHERE project_id=?", (project_id,)))
    if not found:
        return None
    found["analysis"] = json.loads(found["analysis"])
    found["log"] = git.log(repo_dir(project_id)) if repo_dir(project_id).exists() else []
    return found


def disconnect(project_id: str, actor: str = "user") -> None:
    with db() as con:
        con.execute("DELETE FROM repo_sources WHERE project_id=?", (project_id,))
    _rm_tree(repo_dir(project_id))
    ledger.append(project_id, actor, "repo.disconnected")
