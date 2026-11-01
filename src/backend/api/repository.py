"""Repository API."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import (
    PlainTextResponse,
    Response,
)
from pydantic import BaseModel, Field

from backend.api.common import _project, _save_upload
from backend.config import project_dir, repo_dir
from backend.core.security import safe_path
from backend.maf import agui, engine, evals, governance, llm, workflows  # noqa: F401 - workflows registers definitions
from backend.repos import ingest, scan, sandbox

router = APIRouter()


class GitIn(BaseModel):
    url: str
    ref: str = ""
    credential_id: str | None = None


@router.get("/api/projects/{project_id}/repo")
def get_repo(project_id: str):
    _project(project_id)
    repo = ingest.get(project_id)
    return {**repo, "sandbox": sandbox.info(project_id)} if repo else None


@router.post("/api/projects/{project_id}/repo/git")
async def connect_git(project_id: str, body: GitIn):
    _project(project_id)
    return await asyncio.to_thread(ingest.from_git, project_id, body.url, body.ref, body.credential_id)


@router.post("/api/projects/{project_id}/repo/zip")
async def upload_zip(project_id: str, file: UploadFile = File(...)):
    _project(project_id)
    project_dir(project_id).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=project_dir(project_id)) as tmp:
        archive = Path(tmp) / "upload.zip"
        await _save_upload(file, archive)
        return await asyncio.to_thread(ingest.from_zip, project_id, archive, file.filename or "upload.zip")


class LocalIn(BaseModel):
    path: str = Field(min_length=1)


@router.post("/api/projects/{project_id}/repo/local")
async def import_local(project_id: str, body: LocalIn):
    _project(project_id)
    return await asyncio.to_thread(ingest.from_local, project_id, body.path)


@router.post("/api/projects/{project_id}/repo/resync")
async def resync(project_id: str):
    return await asyncio.to_thread(ingest.resync, project_id)


@router.delete("/api/projects/{project_id}/repo", status_code=204)
def disconnect(project_id: str):
    ingest.disconnect(project_id)
    return Response(status_code=204)


@router.get("/api/projects/{project_id}/repo/tree")
def repo_tree(project_id: str):
    root = repo_dir(project_id)
    return {"files": scan.tree(root) if root.exists() else []}


@router.get("/api/projects/{project_id}/repo/file", response_class=PlainTextResponse)
def repo_file(project_id: str, path: str):
    target = safe_path(repo_dir(project_id), path)
    if not target.is_file():
        raise KeyError(path)
    return scan._read(target) or "(binary, empty, or too large to display)"
