"""Helpers shared by routers."""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile

from backend import config
from backend.db import db, row


def _project(project_id: str) -> dict:
    with db() as con:
        found = row(con.execute("SELECT * FROM projects WHERE id=?", (project_id,)))
    if not found:
        raise KeyError(project_id)
    return found


async def _save_upload(upload: UploadFile, target: Path) -> int:
    size = 0
    with target.open("wb") as sink:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > config.MAX_UPLOAD_BYTES:
                raise HTTPException(413, f"Upload exceeds {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
            sink.write(chunk)
    return size
