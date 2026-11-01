"""Templates and source documents API."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import (
    Response,
)
from pydantic import BaseModel, Field

from backend.api.common import _project
from backend.config import project_dir
from backend.core import files
from backend.core.security import sha256
from backend.db import db, new_id, now, row, rows
from backend.maf import agui, engine, evals, governance, llm, workflows  # noqa: F401 - workflows registers definitions

router = APIRouter()


class TemplateIn(BaseModel):
    name: str = Field(min_length=1)
    kind: str = "brd"
    body: str = Field(min_length=1)


@router.get("/api/templates")
def templates(project_id: str | None = None):
    return files.list_templates(project_id)


@router.post("/api/templates", status_code=201)
def add_template(body: TemplateIn, project_id: str | None = None):
    return files.add_template(project_id, body.name, body.kind, body.body)


@router.post("/api/templates/upload", status_code=201)
async def upload_template(file: UploadFile = File(...), name: str = Form(""), kind: str = Form("brd"), project_id: str | None = Form(None)):
    return files.add_template(project_id or None, name or Path(file.filename or "template").stem, kind, files.extract_text(file.filename or "", await file.read()))


@router.delete("/api/templates/{template_id}", status_code=204)
def delete_template(template_id: str):
    if files.get_template(template_id)["builtin"]:
        raise HTTPException(400, "Built-in templates cannot be deleted")
    with db() as con:
        con.execute("DELETE FROM templates WHERE id=?", (template_id,))
    return Response(status_code=204)


@router.get("/api/projects/{project_id}/sources")
def sources(project_id: str):
    with db() as con:
        return rows(con.execute("SELECT id, filename, sha256, length(text) AS chars, created_at FROM sources WHERE project_id=? ORDER BY created_at DESC", (project_id,)))


@router.post("/api/projects/{project_id}/sources", status_code=201)
async def upload_source(project_id: str, file: UploadFile = File(...)):
    _project(project_id)
    blob = await file.read()
    text = files.extract_text(file.filename or "", blob)
    if not text.strip():
        raise HTTPException(400, "No text could be extracted. Scanned PDFs need OCR before upload")
    digest = sha256(blob)
    with db() as con:
        existing = row(con.execute("SELECT id FROM sources WHERE project_id=? AND sha256=?", (project_id, digest)))
        source_id = existing["id"] if existing else new_id("src")
        if not existing:
            con.execute("INSERT INTO sources VALUES (?,?,?,?,?,?)", (source_id, project_id, file.filename, digest, text, now()))
    folder = project_dir(project_id) / "sources"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{source_id}-{Path(file.filename or 'source').name}").write_bytes(blob)
    return {"id": source_id, "filename": file.filename, "sha256": digest, "chars": len(text), "duplicate": bool(existing)}


@router.delete("/api/projects/{project_id}/sources/{source_id}", status_code=204)
def delete_source(project_id: str, source_id: str):
    with db() as con:
        con.execute("DELETE FROM sources WHERE id=? AND project_id=?", (source_id, project_id))
    return Response(status_code=204)
