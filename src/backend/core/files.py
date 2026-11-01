"""Uploaded-file text extraction, templates, and DOCX export."""
from __future__ import annotations

import io
import re

from docx import Document
from docx.shared import Pt

from backend.config import TEMPLATES_DIR
from backend.core.security import sha256
from backend.db import db, new_id, now, rows

TEXT_SUFFIXES = {".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".feature", ".rst"}


class UnsupportedFile(ValueError):
    pass


def extract_text(filename: str, blob: bytes) -> str:
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix in TEXT_SUFFIXES:
        return blob.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        from pypdf import PdfReader

        return "\n\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(blob)).pages)
    if suffix == ".docx":
        return _docx_to_markdown(blob)
    if suffix == ".xlsx":
        from openpyxl import load_workbook

        book = load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
        return "\n\n".join(f"## {sheet.title}\n" + "\n".join(" | ".join("" if c is None else str(c) for c in row) for row in sheet.iter_rows(values_only=True)) for sheet in book)
    if suffix == ".pptx":
        from pptx import Presentation

        slides = Presentation(io.BytesIO(blob)).slides
        return "\n\n".join(f"## Slide {i}\n" + "\n".join(s.text_frame.text for s in slide.shapes if s.has_text_frame) for i, slide in enumerate(slides, 1))
    raise UnsupportedFile(f"Unsupported file type {suffix or filename}. Use .md, .txt, .pdf, .docx, .xlsx, .pptx, .csv, .json, .yaml")


def _docx_to_markdown(blob: bytes) -> str:
    doc = Document(io.BytesIO(blob))
    out: list[str] = []
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        match = re.match(r"Heading (\d)", paragraph.style.name or "")
        out.append(f"{'#' * int(match.group(1))} {text}" if match else text)
    for table in doc.tables:
        for i, table_row in enumerate(table.rows):
            out.append("| " + " | ".join(c.text.strip() for c in table_row.cells) + " |")
            if i == 0:
                out.append("|" + " --- |" * len(table_row.cells))
    return "\n\n".join(out)


def seed_templates() -> None:
    with db() as con:
        for path in sorted(TEMPLATES_DIR.glob("*.md")):
            body = path.read_text(encoding="utf-8")
            title = next((l[2:].strip() for l in body.splitlines() if l.startswith("# ")), path.stem)
            if not con.execute("SELECT 1 FROM templates WHERE id=?", (f"builtin_{path.stem}",)).fetchone():
                con.execute("INSERT INTO templates VALUES (?,?,?,?,?,1,?,?)", (f"builtin_{path.stem}", None, title, path.stem, body, sha256(body), now()))
            else:
                con.execute("UPDATE templates SET name=?, body=?, sha256=? WHERE id=?", (title, body, sha256(body), f"builtin_{path.stem}"))


def add_template(project_id: str | None, name: str, kind: str, body: str) -> dict:
    if not template_headings(body):
        raise UnsupportedFile("Template needs at least one markdown or Word heading")
    template_id = new_id("tpl")
    with db() as con:
        con.execute("INSERT INTO templates VALUES (?,?,?,?,?,0,?,?)", (template_id, project_id, name, kind, body, sha256(body), now()))
    return get_template(template_id)


def get_template(template_id: str) -> dict:
    with db() as con:
        found = con.execute("SELECT * FROM templates WHERE id=?", (template_id,)).fetchone()
    if not found:
        raise KeyError(template_id)
    return {**dict(found), "headings": template_headings(found["body"])}


def list_templates(project_id: str | None = None) -> list[dict]:
    with db() as con:
        items = rows(con.execute("SELECT * FROM templates WHERE project_id IS NULL OR project_id=? ORDER BY builtin DESC, name", (project_id,)))
    return [{**t, "headings": template_headings(t["body"])} for t in items]


def template_headings(body: str) -> list[str]:
    in_code, found = False, []
    for line in body.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        match = re.match(r"^#{2,3}\s+(.+?)\s*$", line)
        if match and not in_code:
            found.append(match.group(1))
    return found or [m.group(1) for m in re.finditer(r"^#\s+(.+?)\s*$", body, re.M)]


def missing_headings(template_body: str, document: str) -> list[str]:
    have = {h.lower() for h in template_headings(document)} | {m.group(1).lower() for m in re.finditer(r"^#{1,4}\s+(.+?)\s*$", document, re.M)}
    return [h for h in template_headings(template_body) if h.lower() not in have]


INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def _runs(paragraph, text: str) -> None:
    for part in INLINE.split(text):
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            paragraph.add_run(part[2:-2]).bold = True
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            run = paragraph.add_run(part[1:-1])
            run.font.name = "Consolas"
        elif part:
            paragraph.add_run(part)


def markdown_to_docx(title: str, markdown: str, meta: str = "") -> bytes:
    doc = Document()
    doc.add_heading(title, 0)
    if meta:
        doc.add_paragraph(meta).runs[0].italic = True
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            run = doc.add_paragraph().add_run("\n".join(block))
            run.font.name, run.font.size = "Consolas", Pt(9)
        elif line.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            cells = lambda l: [c.strip() for c in l.strip().strip("|").split("|")]  # noqa: E731
            header = cells(line)
            i += 2
            body = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                body.append(cells(lines[i]))
                i += 1
            i -= 1
            table = doc.add_table(rows=1, cols=len(header))
            table.style = "Table Grid"
            for j, value in enumerate(header):
                table.rows[0].cells[j].text = ""
                table.rows[0].cells[j].paragraphs[0].add_run(value).bold = True
            for values in body:
                cols = table.add_row().cells
                for j, value in enumerate(values[: len(header)]):
                    _runs(cols[j].paragraphs[0], value)
        elif match := re.match(r"^(#{1,6})\s+(.+)$", line):
            doc.add_heading(match.group(2), min(len(match.group(1)), 4))
        elif match := re.match(r"^\s*[-*]\s+(.+)$", line):
            _runs(doc.add_paragraph(style="List Bullet"), match.group(1))
        elif match := re.match(r"^\s*\d+[.)]\s+(.+)$", line):
            _runs(doc.add_paragraph(style="List Number"), match.group(1))
        elif line.strip():
            _runs(doc.add_paragraph(), line)
        i += 1
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
