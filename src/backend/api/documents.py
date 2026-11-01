"""Documents API."""
from __future__ import annotations

import asyncio
import csv
import io

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import (
    PlainTextResponse,
    Response,
)
from pydantic import BaseModel, Field

from backend.api.common import _project
from backend.core import auth, doc_checks, documents, files
from backend.maf import agui, engine, evals, governance, llm, workflows  # noqa: F401 - workflows registers definitions
from backend.maf import runtime as agents

from backend.db import db, rows  # noqa: E402

from backend.core.security import safe_path  # noqa: E402

router = APIRouter()


class DocIn(BaseModel):
    kind: str = "brd"
    title: str = Field(min_length=1)
    content: str = ""
    template_id: str | None = None


class VersionIn(BaseModel):
    content: str
    note: str = ""
    author: str = "user"


class ActorIn(BaseModel):
    by: str = "user"


@router.get("/api/documents")
def all_documents():
    with db() as con:
        projects = rows(con.execute("SELECT id, name FROM projects WHERE archived=0 AND id!='prj_agent_evals'"))
    found = [{**doc, "project": p["name"]} for p in projects if auth.can_see_project(p["id"]) for doc in documents.list_for(p["id"])]
    return sorted(found, key=lambda doc: doc["updated_at"], reverse=True)[:500]


@router.get("/api/projects/{project_id}/documents")
def list_documents(project_id: str, kind: str | None = None):
    return documents.list_for(project_id, kind)


@router.post("/api/projects/{project_id}/documents", status_code=201)
def create_document(project_id: str, body: DocIn):
    _project(project_id)
    content = body.content or (files.get_template(body.template_id)["body"] if body.template_id else "")
    return documents.create(project_id, body.kind, body.title, content, "user", template_id=body.template_id)


@router.get("/api/documents/{doc_id}")
def get_document(doc_id: str, version: int | None = None):
    return documents.get(doc_id, version)


@router.put("/api/documents/{doc_id}")
def save_document(doc_id: str, body: VersionIn):
    return documents.save_version(doc_id, body.content, body.author, note=body.note or "Edited")


@router.delete("/api/documents/{doc_id}", status_code=204)
def delete_document(doc_id: str):
    documents.delete(doc_id, "user")
    return Response(status_code=204)


@router.get("/api/documents/{doc_id}/versions")
def document_versions(doc_id: str):
    return documents.versions(doc_id)


@router.get("/api/documents/{doc_id}/diff", response_class=PlainTextResponse)
def document_diff(doc_id: str, a: int, b: int):
    return documents.diff(doc_id, a, b)


@router.post("/api/documents/{doc_id}/restore/{version}")
def restore_document(doc_id: str, version: int, body: ActorIn):
    return documents.restore(doc_id, version, body.by)


@router.post("/api/documents/{doc_id}/approve")
def approve_document(doc_id: str, body: ActorIn):
    return documents.set_status(doc_id, "approved", body.by)


@router.get("/api/documents/{doc_id}/export/{fmt}")
def export_document(doc_id: str, fmt: str, version: int | None = None):
    doc = documents.get(doc_id, version)
    slug = "".join(c if c.isalnum() else "-" for c in doc["title"]).strip("-").lower()[:60] or doc["id"]
    name = f"{slug}-v{doc['version']}"
    if fmt == "md":
        return Response(doc["content"], media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{name}.md"'})
    if fmt == "feature":
        return Response(doc["content"], media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{name}.feature"'})
    if fmt == "docx":
        body = doc["content"] if doc["kind"] != "gherkin" else f"```\n{doc['content']}\n```"
        blob = files.markdown_to_docx(doc["title"], body, f"Version {doc['version']} · {doc['status']} · SHA-256 {doc['sha256'][:16]}", documents.image_root(doc))
        return Response(blob, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f'attachment; filename="{name}.docx"'})
    if fmt == "patch":
        return Response(doc["content"], media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{name}.patch"'})
    if fmt in {"csv", "jira"} and doc["kind"] == "test_cases":
        return Response(_cases_csv(doc["data"], fmt), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{name}-{fmt}.csv"'})
    raise HTTPException(400, "Use md, docx, feature, patch, or for test cases csv and jira")


@router.post("/api/documents/{doc_id}/images", status_code=201)
async def add_image(doc_id: str, file: UploadFile = File(...)):
    blob = await file.read(documents.MAX_IMAGE_BYTES + 1)
    name = await asyncio.to_thread(documents.save_image, doc_id, blob)
    return {"file": name, "url": f"/api/documents/{doc_id}/images/{name}"}


@router.get("/api/documents/{doc_id}/images/{name}")
def get_image(doc_id: str, name: str):
    target = safe_path(documents.image_root(documents.get(doc_id)), name)
    if target.suffix not in {".png", ".jpg", ".gif", ".webp"} or not target.is_file():
        raise HTTPException(404, "Image not found")
    media = {".png": "image/png", ".jpg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}[target.suffix]
    return Response(target.read_bytes(), media_type=media, headers={"X-Content-Type-Options": "nosniff"})


def _cases_csv(cases: list[dict], fmt: str) -> str:
    def cell(value) -> str:  # spreadsheets execute cells starting with these characters
        text = str(value)
        return "'" + text if text[:1] in {"=", "+", "-", "@", "\t", "\r"} else text

    out = io.StringIO()
    writer = csv.writer(out)
    if fmt == "csv":
        writer.writerow(["TC ID", "User Story ID", "Scenario", "Type", "Precondition", "Test Data", "Steps", "Expected Result", "Priority", "Automation Candidate", "Remarks"])
        for c in cases:
            steps = " ".join(f"{i + 1}. {s}" for i, s in enumerate(c["steps"]))
            writer.writerow([cell(v) for v in (c["id"], c["requirement_id"], c["scenario"], c["type"], c["precondition"], c["test_data"], steps, c["expected_result"], c["priority"], f"Yes ({c['level']})", f"Oracle: {c['oracle']}")])
    else:
        writer.writerow(["Summary", "Issue Type", "Description", "Priority", "Labels", "Parent/Story ID"])
        for c in cases:
            description = f"Steps: {' '.join(c['steps'])}\nExpected: {c['expected_result']}"
            writer.writerow([cell(v) for v in (f"{c['id']}: {c['scenario']}", "Test", description, c["priority"], c["type"].replace(" ", "-"), c["requirement_id"])])
    return out.getvalue()


class RefineIn(BaseModel):
    instructions: str = Field(min_length=1)
    by: str = "user"


@router.post("/api/documents/{doc_id}/review")
async def review_document(doc_id: str):
    doc = documents.get(doc_id)
    review = await agents.AgentCall(None, doc["project_id"], "doc_reviewer").typed(f"Review this document for completeness, testability, consistency, and invented facts.\n\nDOCUMENT:\n{doc['content']}", workflows.Review)
    template_body = files.get_template(doc["template_id"])["body"] if doc["template_id"] else ""
    return {**doc_checks.apply(review.model_dump(), doc["content"], template_body), "version": doc["version"]}


@router.post("/api/documents/{doc_id}/refine")
async def refine_document(doc_id: str, body: RefineIn):
    doc = documents.get(doc_id)
    agent_key = "gherkin_author" if doc["kind"] == "gherkin" else "business_analyst"
    call = agents.AgentCall(None, doc["project_id"], agent_key)
    text = await call.text(f"Revise this document, keeping its structure. Return only the full revised document.\n\nINSTRUCTIONS:\n{body.instructions}\n\nDOCUMENT:\n{doc['content']}")
    return documents.save_version(doc_id, text, f"agent:{agent_key}", note=f"Refine: {body.instructions[:150]}", prompt_ref=call.prompt_ref)
