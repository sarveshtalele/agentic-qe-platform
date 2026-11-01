"""Versioned documents. Every save is an immutable version with SHA-256, author, and prompt reference.

Versions are written through to data/projects/<id>/documents/<kind>/<doc>/vNNNN.<ext> so a project
stays readable without the app. The database remains the source of truth.
"""
from __future__ import annotations

import difflib
import json
import re

from backend.config import project_dir
from backend.core import gherkin, ledger
from backend.core.security import redact, sha256
from backend.db import db, new_id, now, row, rows

EXT = {"gherkin": "feature", "patch": "patch"}


class DocumentError(ValueError):
    pass


def create(project_id: str, kind: str, title: str, content: str, author: str, *, data=None, note="", prompt_ref="",
           run_id=None, parent_id=None, template_id=None) -> dict:
    doc_id, stamp = new_id("doc"), now()
    with db() as con:
        con.execute(
            "INSERT INTO documents (id, project_id, kind, title, parent_id, template_id, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (doc_id, project_id, kind, title, parent_id, template_id, stamp, stamp),
        )
    return save_version(doc_id, content, author, data=data, note=note or "Created", prompt_ref=prompt_ref, run_id=run_id)


def save_version(doc_id: str, content: str, author: str, *, data=None, note="", prompt_ref="", run_id=None) -> dict:
    doc = _doc(doc_id)
    if doc["kind"] == "gherkin":
        check = gherkin.validate(content)
        if not check["valid"]:
            raise DocumentError("Invalid Gherkin: " + "; ".join(check["errors"]))
    content = redact(content)
    digest, stamp = sha256(content), now()
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        latest = row(con.execute("SELECT version, sha256 FROM document_versions WHERE document_id=? ORDER BY version DESC LIMIT 1", (doc_id,)))
        if latest and latest["sha256"] == digest and data is None:
            return get(doc_id)
        version = (latest["version"] if latest else 0) + 1
        con.execute(
            "INSERT INTO document_versions VALUES (?,?,?,?,?,?,?,?,?,?)",
            (doc_id, version, content, json.dumps(data), digest, author, note, prompt_ref, run_id, stamp),
        )
        # an edit invalidates a previous approval of this document
        con.execute("UPDATE documents SET current_version=?, updated_at=?, status='draft' WHERE id=?", (version, stamp, doc_id))
    folder = project_dir(doc["project_id"]) / "documents" / doc["kind"] / doc_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"v{version:04d}.{EXT.get(doc['kind'], 'md')}").write_text(content, encoding="utf-8")
    ledger.append(doc["project_id"], author, "document.version", doc_id, {"version": version, "sha256": digest, "prompt": prompt_ref})
    return get(doc_id)


def _doc(doc_id: str) -> dict:
    with db() as con:
        found = row(con.execute("SELECT * FROM documents WHERE id=?", (doc_id,)))
    if not found:
        raise KeyError(doc_id)
    return found


def get(doc_id: str, version: int | None = None) -> dict:
    doc = _doc(doc_id)
    with db() as con:
        current = row(con.execute("SELECT * FROM document_versions WHERE document_id=? AND version=?", (doc_id, version or doc["current_version"])))
    if not current:
        raise KeyError(f"{doc_id} v{version}")
    extra = gherkin.validate(current["content"]) if doc["kind"] == "gherkin" else None
    return {**doc, "version": current["version"], "content": current["content"], "data": json.loads(current["data"]),
            "sha256": current["sha256"], "author": current["author"], "note": current["note"],
            "prompt_ref": current["prompt_ref"], "run_id": current["run_id"], "version_created_at": current["created_at"], "gherkin": extra}


def list_for(project_id: str, kind: str | None = None) -> list[dict]:
    query = "SELECT * FROM documents WHERE project_id=?" + (" AND kind=?" if kind else "") + " ORDER BY updated_at DESC"
    with db() as con:
        return rows(con.execute(query, (project_id, kind) if kind else (project_id,)))


def latest_of_kind(project_id: str, kind: str) -> dict | None:
    docs = list_for(project_id, kind)
    return get(docs[0]["id"]) if docs else None


def versions(doc_id: str) -> list[dict]:
    with db() as con:
        return rows(con.execute(
            "SELECT version, sha256, author, note, prompt_ref, run_id, created_at, length(content) AS size FROM document_versions WHERE document_id=? ORDER BY version DESC",
            (doc_id,),
        ))


def diff(doc_id: str, a: int, b: int) -> str:
    left, right = get(doc_id, a), get(doc_id, b)
    return "\n".join(difflib.unified_diff(left["content"].splitlines(), right["content"].splitlines(), f"v{a}", f"v{b}", lineterm=""))


def restore(doc_id: str, version: int, author: str) -> dict:
    old = get(doc_id, version)
    return save_version(doc_id, old["content"], author, data=old["data"], note=f"Restored from v{version}")


def set_status(doc_id: str, status: str, by: str) -> dict:
    doc = _doc(doc_id)
    with db() as con:
        con.execute("UPDATE documents SET status=?, updated_at=? WHERE id=?", (status, now(), doc_id))
    ledger.append(doc["project_id"], by, f"document.{status}", doc_id, {"version": doc["current_version"]})
    return get(doc_id)


def delete(doc_id: str, by: str) -> None:
    doc = _doc(doc_id)
    with db() as con:
        con.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    ledger.append(doc["project_id"], by, "document.deleted", doc_id, {"title": doc["title"], "versions": doc["current_version"]})


def search(project_id: str, query: str, limit: int = 8) -> list[dict]:
    """Keyword search over the current version of every document, returning line-context snippets."""
    terms = [t.lower() for t in re.findall(r"\w{3,}", query)] or [query.lower()]
    results = []
    for doc in list_for(project_id):
        body = get(doc["id"])["content"]
        lower = body.lower()
        score = sum(lower.count(t) for t in terms)
        if not score:
            continue
        lines = body.splitlines()
        hits = [i for i, line in enumerate(lines) if any(t in line.lower() for t in terms)][:3]
        snippet = "\n".join(lines[i] for i in hits)
        results.append({"id": doc["id"], "kind": doc["kind"], "title": doc["title"], "version": doc["current_version"], "score": score, "snippet": snippet})
    return sorted(results, key=lambda r: -r["score"])[:limit]
