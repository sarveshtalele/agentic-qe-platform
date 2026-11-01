"""BA workflow: brief to templated document, independent review, Gherkin, human approval."""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from backend.core import doc_checks, documents, files, gherkin
from backend.db import db, rows
from backend.maf.engine import REGISTRY, Definition, RunContext, StageSpec
from backend.maf.runtime import AgentCall
from backend.maf.workflows.shared import (
    MAX_SOURCE_CHARS,
    intake,
    intake_gate,
)


class Review(BaseModel):
    score: int = Field(ge=0, le=100)
    verdict: str
    issues: list[str] = []


async def ba_context(rc: RunContext, state: dict) -> dict:
    template = files.get_template(state.get("template_id") or "builtin_brd")
    with db() as con:
        ids = state.get("source_ids") or []
        marks = ",".join("?" * len(ids))
        items = rows(con.execute(f"SELECT filename, text FROM sources WHERE project_id=? AND id IN ({marks})", (rc.project_id, *ids))) if ids else []
    source_text = "\n\n".join(f"--- Source: {s['filename']} ---\n{s['text']}" for s in items)[:MAX_SOURCE_CHARS]
    if not state.get("brief", "").strip() and not source_text:
        raise ValueError("Provide a brief or at least one uploaded source document")
    rc.log(f"Template {template['name']} with {len(template['headings'])} sections; {len(items)} source documents")
    return {"template_id": template["id"], "template_name": template["name"], "source_text": source_text, "iteration": 0}


def _strip_preamble(text: str) -> str:
    """Drop chatter before the first heading and a wrapping code fence, so saved documents render as documents."""
    text = re.sub(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", r"\1", text.strip(), flags=re.S)
    heading = re.search(r"^#{1,3}\s", text, re.M)
    return text[heading.start():].strip() if heading else text


async def ba_draft(rc: RunContext, state: dict) -> dict:
    template = files.get_template(state["template_id"])
    call = AgentCall(rc.run_id, rc.project_id, "business-analyst", refs=())
    message = (
        f"Artifact: requirements document. Write the document for this request.\n\nBRIEF:\n{state.get('brief', '')}\n\nSOURCE DOCUMENTS:\n{state.get('source_text') or '(none)'}\n\n"
        f"TEMPLATE (keep every heading exactly, in this order):\n{template['body']}\n"
    )
    current = documents.get(state["doc_id"])["content"] if state.get("doc_id") else ""
    if state.get("feedback"):
        message += f"\nCURRENT DRAFT:\n{current}\n\nREVISE IT TO ADDRESS THIS FEEDBACK:\n{state['feedback']}\n"
    text = await call.text(message)
    text = _strip_preamble(text)
    missing = files.missing_headings(template["body"], text)
    if missing:
        rc.log(f"Draft missed sections {missing}; asking the agent to complete them")
        text = await call.text(f"{message}\nYour previous draft omitted these required headings: {missing}. Return the full document with them.\n\nPREVIOUS DRAFT:\n{text}")
        text = _strip_preamble(text)
        missing = files.missing_headings(template["body"], text)
    title = state.get("title") or f"{template['name']}"
    if state.get("doc_id"):
        doc = documents.save_version(state["doc_id"], text, "agent:business-analyst", note="Revision: " + state.get("feedback", "")[:200], prompt_ref=call.prompt_ref, run_id=rc.run_id)
    else:
        doc = documents.create(rc.project_id, template["kind"], title, text, "agent:business-analyst", note="First draft", prompt_ref=call.prompt_ref, run_id=rc.run_id, template_id=template["id"])
    rc.log(f"Saved {doc['title']} v{doc['version']}", {"document_id": doc["id"], "missing_sections": missing}, "artifact")
    return {"doc_id": doc["id"], "iteration": state.get("iteration", 0) + 1, "missing_sections": missing}


async def ba_review(rc: RunContext, state: dict) -> dict:
    doc = documents.get(state["doc_id"])
    review = await AgentCall(rc.run_id, rc.project_id, "confidence-reviewer", skills=()).typed(
        f"Review type: requirements document. Review this document against the brief.\n\nBRIEF:\n{state.get('brief', '')}\n\nSOURCES:\n{state.get('source_text') or '(none)'}\n\nDOCUMENT:\n{doc['content']}", Review)
    # the lower of the model score and the deterministic checks wins
    combined = doc_checks.apply(review.model_dump(), doc["content"], files.get_template(state["template_id"])["body"], f"{state.get('brief', '')}\n{state.get('source_text', '')}")
    rc.log(f"Review score {combined['score']} (model {combined['model_score']}): {combined['verdict']}", combined, "review")
    update = {"review": combined}
    if combined["score"] < 75 and state["iteration"] < 2:
        update |= {"feedback": "Reviewer issues:\n" + "\n".join(combined["issues"]), "_next": "draft"}
    else:
        update["feedback"] = ""
    return update


async def ba_gherkin(rc: RunContext, state: dict) -> dict:
    doc = documents.get(state["doc_id"])
    call = AgentCall(rc.run_id, rc.project_id, "business-analyst", refs=())
    message = f"Artifact: Gherkin feature file. Convert this document's requirements into one Gherkin feature file.\n\nDOCUMENT:\n{doc['content']}"
    errors = ""
    for _ in range(3):
        text = await call.text(message + (f"\n\nThe previous output failed the Gherkin parser: {errors}\n\nPREVIOUS OUTPUT:\n{text}" if errors else ""))  # noqa: F821
        text = re.sub(r"^```\w*\n|```\s*$", "", text.strip(), flags=re.M).strip()
        check = gherkin.validate(text)
        if check["valid"]:
            break
        errors = "; ".join(check["errors"])
    else:
        raise RuntimeError(f"Gherkin author failed validation: {errors}")
    if state.get("gherkin_id"):
        saved = documents.save_version(state["gherkin_id"], text, "agent:business-analyst", note="Regenerated", prompt_ref=call.prompt_ref, run_id=rc.run_id)
    else:
        saved = documents.create(rc.project_id, "gherkin", f"{doc['title']} scenarios", text, "agent:business-analyst", prompt_ref=call.prompt_ref, run_id=rc.run_id, parent_id=doc["id"])
    rc.log(f"Gherkin valid: {check['scenarios']} scenarios, {check['steps']} steps", {"document_id": saved["id"]}, "artifact")
    return {"gherkin_id": saved["id"]}


def ba_gate(rc: RunContext, state: dict):
    return {"gate": 1, "title": "Gate 1: approve requirements document",
            "summary": f"Review score {state['review']['score']}. Open the document and its Gherkin scenarios, edit if needed, then approve or send back with feedback.",
            "payload": {"documents": [state["doc_id"], state["gherkin_id"]], "titles": [documents.get(state["doc_id"])["title"], documents.get(state["gherkin_id"])["title"]], "review": state["review"], "missing_sections": state.get("missing_sections", [])}}


async def ba_approved(rc: RunContext, state: dict, answer: dict) -> dict:
    for doc_id in (state["doc_id"], state["gherkin_id"]):
        documents.set_status(doc_id, "approved", answer["by"])
    return {}


def ba_definition() -> Definition:
    return Definition("ba", [
        StageSpec("intake", intake, "Intake", approval=intake_gate, next="context"),
        StageSpec("context", ba_context, "Load template and sources", next="draft"),
        StageSpec("draft", ba_draft, "Draft document", next="review"),
        StageSpec("review", ba_review, "Independent review", next="gherkin"),
        StageSpec("gherkin", ba_gherkin, "Author Gherkin", approval=ba_gate, on_approved=ba_approved, on_rejected="draft", next="END"),
    ], routes={"review": ["draft"]})


REGISTRY["ba"] = ba_definition
