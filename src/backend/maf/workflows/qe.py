"""QE lifecycle: requirements to signed release, with human gates G0 to G5."""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from backend.config import MAX_CASES, project_dir, repo_dir
from backend.core import doc_checks, documents
from backend.core.security import (
    safe_path,
)
from backend.core.errors import AllowanceError, AqeError, EvidenceError, ExecutionError, ModelSchemaError
from backend.maf.engine import REGISTRY, Definition, RunContext, StageSpec, part_key
from backend.maf.runtime import AgentCall
from backend.maf.workflows.ba import _strip_preamble
from backend.maf.workflows.edits import ChangeSet, Edit, apply_edits, guarded_apply
from backend.maf.workflows.shared import (
    discovery_pack,
    is_low,
    review_artifact,
    review_cases,
    review_evidence,
    token_line,
    review_with_send_back,
    token_estimate,
    _analysis,
    _brief_of_analysis,
    code_pack,
    intake,
    intake_gate,
)
from backend.qe import confidence, emit, execution, model, test_data, trace
from backend.repos import git, scan, static_analysis


async def qe_discover(rc: RunContext, state: dict) -> dict:
    a = _analysis(rc.project_id)
    root = repo_dir(rc.project_id)
    call = AgentCall(rc.run_id, rc.project_id, "repo-intelligence-analyst")
    evidence = f"SCAN:\n{_brief_of_analysis(a)}\n\nCODE:\n{discovery_pack(rc.project_id)}"
    text = _strip_preamble(await call.text(f"Write the discovery summary from these scan facts and this code.\n\n{evidence}"))
    tree = scan.tree(root, limit=100_000) if root.exists() else []
    sources = static_analysis.review_targets(root) if root.exists() else []
    issues = doc_checks.discovery_issues(text, tree, sources, evidence)
    review = await review_artifact(rc, "discovery summary", text, evidence)
    if issues or is_low(review):
        rc.log(f"Discovery sent back: {issues or review['issues']}", kind="warning")
        text = _strip_preamble(await call.text(f"Rewrite the complete discovery summary and fix these problems: {issues + review['issues']}. Use only paths that appear in the evidence."))
        issues = doc_checks.discovery_issues(text, tree, sources, evidence)
        review = await review_artifact(rc, "discovery summary", text, evidence)
    if issues:
        rc.log(f"Discovery still has gaps: {issues}", kind="warning")
    doc = documents.create(rc.project_id, "discovery", "Discovery summary", text, "agent:repo-intelligence-analyst", data=a, prompt_ref=call.prompt_ref, run_id=rc.run_id)
    rc.log("Discovery saved", {"document_id": doc["id"]}, "artifact")
    return {"discovery_id": doc["id"], "discovery_review": review, "discovery_issues": issues}


async def qe_requirements(rc: RunContext, state: dict) -> dict:
    root = repo_dir(rc.project_id)
    brownfield = state["mode"] == "brownfield"
    call = AgentCall(rc.run_id, rc.project_id, "requirements-analyst")
    approved = [d for d in documents.list_for(rc.project_id) if d["kind"] in {"brd", "prd", "stories", "gherkin"} and d["status"] == "approved"]
    stories = "\n\n".join(documents.get(d["id"])["content"][:20000] for d in approved[:3])
    if not brownfield and not stories:
        raise ValueError("Greenfield QE needs an approved requirements document. Run the BA workflow first")
    prompt = (
        (f"Reverse-engineer testable requirements from this code. Every requirement needs file, line, and an exact one-line quote copied from a numbered line below, without the line number.\n\nCODE:\n{code_pack(rc.project_id, limit=40_000)}\n" if brownfield else "Derive testable requirements from these approved documents. Use tier 'specified'.\n")
        + (f"\nAPPROVED DOCUMENTS:\n{stories}\n" if stories else "")
        + f"\nSCAN:\n{_brief_of_analysis(_analysis(rc.project_id))}\n"
        + (f"\nHUMAN FEEDBACK:\n{state['feedback']}" if state.get("feedback") else "")
    )
    for attempt in range(2):
        result = await call.typed(prompt, model.RequirementSet)
        kept, dropped = [], []
        for requirement in result.requirements:
            if brownfield and requirement.tier != "specified":
                ok, line = static_analysis.verify_quote(root, requirement.file, requirement.line, requirement.quote)
                if not ok or model.is_comment(requirement.quote):  # a comment is not behaviour: code takes precedence
                    dropped.append(requirement.id)
                    continue
                requirement.line = line
            kept.append(requirement.model_dump())
        if not kept:
            raise EvidenceError("No requirement survived evidence verification: no quote was found on disk at the stated file and line.")
        rc.log(f"{len(kept)} requirements verified; {len(dropped)} dropped for missing evidence", {"dropped": dropped})
        review = await review_artifact(rc, "requirements", json.dumps(kept), _brief_of_analysis(_analysis(rc.project_id)) if brownfield else stories)
        if attempt or not is_low(review):
            break
        prompt = f"An independent reviewer scored your requirements {review['score']}. Send the complete corrected set. Issues: {review['issues']}. Requirements dropped for missing evidence: {dropped}."
    body = "| ID | Requirement | Priority | Tier | Evidence |\n|---|---|---|---|---|\n" + "\n".join(
        f"| {r['id']} | {_cell(r['title'])}: {_cell(r['statement'])} | {r['priority']} | {r['tier']} | {('`' + r['file'] + ':' + str(r['line']) + '`') if r['file'] else '-'} |" for r in kept)
    doc = documents.create(rc.project_id, "requirements", "Requirements", body, "agent:requirements-analyst", data=kept, prompt_ref=call.prompt_ref, run_id=rc.run_id)
    return {"requirements": kept, "requirements_doc": doc["id"], "requirements_review": review}


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


async def qe_plan(rc: RunContext, state: dict) -> dict:
    call = AgentCall(rc.run_id, rc.project_id, "principal-test-architect")
    a = _analysis(rc.project_id)
    prompt = f"Create the test plan.\nREQUIREMENTS:\n{json.dumps(state['requirements'])}\nDETECTED RUNNERS: {a['test_runners']}\nFRAMEWORKS: {a['frameworks']}\nEXISTING TESTS: {a.get('test_files', [])[:40]}" + (f"\nFEEDBACK:\n{state['feedback']}" if state.get("feedback") else "")
    plan = (await call.typed(prompt, model.TestPlan)).model_dump()
    score = model.plan_confidence(state["requirements"], plan)
    if score["verdict"] != "APPROVED":
        plan = (await call.typed(f"{prompt}\n\nAutomatic checks rejected your plan: {score['issues']}. Fix them.", model.TestPlan)).model_dump()
        score = model.plan_confidence(state["requirements"], plan)
    root = repo_dir(rc.project_id)
    wanted_files = list(dict.fromkeys(r["file"] for r in state["requirements"] if r.get("file")))
    evidence = lambda _: f"REQUIREMENTS:\n{json.dumps(state['requirements'])}\n\nCODE (line numbers are before each line):\n{code_pack(rc.project_id, paths=wanted_files or None, limit=20_000)}"

    async def revise_plan(_: int, record: dict, calls: list) -> str:
        nonlocal plan
        again = AgentCall(rc.run_id, rc.project_id, "principal-test-architect")
        calls.append(again)
        plan = (await again.typed(f"{prompt}\n\nAn independent reviewer found these flaws in your plan. Fix each one and send the complete plan.\n{confidence.flaw_lines(record)}", model.TestPlan, attempts=2)).model_dump()
        return json.dumps(plan)

    records, tokens = await review_with_send_back(rc, "plan", "plan", [("PLAN", json.dumps(plan))], evidence, root if root.exists() else None, revise_plan)
    score = model.plan_confidence(state["requirements"], plan)
    review = confidence.summarise(records, tokens)
    rc.log(f"Plan score {score['score']} ({score['verdict']}), independent review {review['score']} ({review['verdict']})", {"deterministic": score, "review": review}, "review")
    body = f"{plan['strategy']}\n\n| Area | Requirements | Risk | Level | Framework | Rationale |\n|---|---|---|---|---|---|\n" + "\n".join(
        f"| {_cell(x['name'])} | {', '.join(x['requirement_ids'])} | {x['risk']} | {x['level']} | {x['framework']} | {_cell(x['rationale'])} |" for x in plan["areas"])
    doc = documents.create(rc.project_id, "test_plan", "Test plan", body, "agent:principal-test-architect", data={"plan": plan, "score": score, "review": review}, prompt_ref=call.prompt_ref, run_id=rc.run_id)
    return {"plan": plan, "plan_doc": doc["id"], "plan_score": score, "plan_review": review}


DESIGN_BATCH = 4
PARTIAL_AFTER = 2  # earlier failures of a stage before it may end with a partial result


def settle(rc: RunContext, batches: list, outcomes: list, what: str) -> dict | None:
    """Finished batches are already saved. A failed one raises, so Retry repeats only it, until retries are used up: then the stage ends marked partial."""
    for outcome in outcomes:
        if isinstance(outcome, BaseException) and not isinstance(outcome, Exception):
            raise outcome  # cancellation is not a batch failure
    failed = [(batch, outcome) for batch, outcome in zip(batches, outcomes) if isinstance(outcome, Exception)]
    if not failed:
        return None
    if limit := next((o for _, o in failed if isinstance(o, AllowanceError)), None):
        raise limit  # a limit never ends a stage as a partial result: finished batches stay saved, and Retry continues after the reset
    for _, outcome in failed[1:]:
        rc.log(f"Another {what} batch failed: {getattr(outcome, 'code', type(outcome).__name__)} {str(outcome)[:200]}", kind="warning")
    if rc.earlier_failures() < PARTIAL_AFTER or len(failed) == len(batches):
        raise failed[0][1]
    missing = [item for batch, _ in failed for item in batch]
    rc.log(f"{what}: {len(failed)} of {len(batches)} batches kept failing. The result is PARTIAL and cannot be approved.", {"missing": missing}, "warning")
    return {"stage": rc.stage, "missing": missing, "codes": sorted({getattr(o, "code", "AQE-INT-001") for _, o in failed})}


def _number_cases(cases: list[dict]) -> None:
    for number, case in enumerate(cases, 1):
        case["id"] = f"TC-APP-{number:03d}"


DESIGN_REVIEW_BATCH = 8
CODE_REVIEW_BATCH = 8


def _files_of(requirements: list[dict]) -> list[str]:
    return list(dict.fromkeys(r["file"] for r in requirements if r.get("file")))


def _design_evidence(rc: RunContext, requirements: list[dict], cases: list[dict]) -> str:
    """Evidence for one review batch: only the requirements its cases cover, with their quotes and the lines near each citation."""
    wanted = [r for r in requirements if r["id"] in {c["requirement_id"] for c in cases}] or requirements
    return review_evidence(rc.project_id, wanted)


async def qe_design(rc: RunContext, state: dict) -> dict:
    call = AgentCall(rc.run_id, rc.project_id, "test-design-architect", skills=("designing-test-cases",))
    feedback = f"\nFEEDBACK:\n{state['feedback']}" if state.get("feedback") else ""
    root = repo_dir(rc.project_id)
    source = root if root.exists() else None
    # the case budget is decided here, by code, before any model call: tokens are never spent on cases that would be cut
    budget = model.case_quota(state["requirements"], MAX_CASES)
    quota = budget["quota"]
    dropped: list[dict] = []
    rc.log(budget["message"], budget, "warning" if budget["left_out_requirements"] or budget["p0_over_limit"] else "log")

    def asked_for(requirements: list[dict]) -> str:
        return "\nCASE QUOTA, at most this many cases for each requirement (for 4: 1 Positive, 2 Negative, 1 Exception; with fewer, the Positive case first):\n" + ", ".join(f"{r['id']}: {quota.get(r['id'], 0)}" for r in requirements)

    async def design(requirements: list[dict], note: str = "") -> list[dict]:
        # each batch has its own conversation, so batches can run together
        batch_call = AgentCall(rc.run_id, rc.project_id, "test-design-architect", skills=("designing-test-cases",))
        try:
            result = await batch_call.typed(f"Design test cases for only these requirements.\nREQUIREMENTS:\n{json.dumps(requirements)}{asked_for(requirements)}\nPLAN:\n{json.dumps(state['plan'])}{feedback}{note}", model.CaseSet, attempts=2)
        except AllowanceError:
            raise  # a limit is not a bad reply, so the batch is not split; the stage stops and finished batches are kept
        except RuntimeError as exc:
            if len(requirements) < 2:
                raise
            # a smaller request is the reliable answer to a reply that keeps breaking
            rc.log(f"Splitting a design batch of {len(requirements)} requirements: {str(exc)[:160]}", kind="warning")
            half = len(requirements) // 2
            parts = await asyncio.gather(design(requirements[:half], note), design(requirements[half:], note))
            return [case for part in parts for case in part]
        return [c.model_dump() for c in result.cases]

    async def design_and_review(requirements: list[dict]) -> tuple[list[dict], list[dict], dict, list[dict]]:
        found, over = model.apply_quota(await design(requirements), quota)  # an excess case is dropped before it is reviewed

        async def revise_case(i: int, record: dict, calls: list) -> str:
            # the case goes back alone, with only its own flaws and the one requirement it covers
            old = found[i]
            again = AgentCall(rc.run_id, rc.project_id, "test-design-architect", skills=("designing-test-cases",))
            calls.append(again)
            owner = [r for r in requirements if r["id"] == old["requirement_id"]] or requirements
            result = await again.typed(f"Rewrite only this one test case, keeping its type, and fix every flaw the independent reviewer found. Send one case.\nREQUIREMENT:\n{json.dumps(owner)}\nCASE:\n{json.dumps(old)}\nFLAWS AND FIXES:\n{confidence.flaw_lines(record)}\nPLAN:\n{json.dumps(state['plan'])}", model.CaseSet, attempts=2)
            found[i] = {**result.cases[0].model_dump(), "requirement_id": old["requirement_id"]}
            return json.dumps(found[i])

        records, tokens = await review_with_send_back(rc, "design", "design cases", [(f"C{n}", json.dumps(c)) for n, c in enumerate(found, 1)],
                                                      lambda indexes: _design_evidence(rc, requirements, [found[i] for i in indexes]), source, revise_case, DESIGN_REVIEW_BATCH)
        return found, records, tokens, over

    # one large reply breaks on real repositories, so batches run in parallel, each with its own review, and code merges them
    designed = [r for r in state["requirements"] if r["id"] in quota]
    batches = [designed[i : i + DESIGN_BATCH] for i in range(0, len(designed), DESIGN_BATCH)]

    async def finished_or_new(batch: list[dict]) -> tuple[list[dict], list[dict], dict, list[dict]]:
        key = part_key("design", [r["id"] for r in batch], state.get("feedback", ""), [quota[r["id"]] for r in batch])
        if (saved := rc.kept(key)) and saved.get("records"):
            rc.log(f"Kept result reused for {len(batch)} requirements: {batch[0]['id']} to {batch[-1]['id']}")
            return saved["cases"], saved["records"], saved["tokens"], saved.get("dropped", [])
        found, records, tokens, over = await design_and_review(batch)
        rc.keep(key, {"cases": found, "records": records, "tokens": tokens, "dropped": over})
        return found, records, tokens, over

    outcomes = await asyncio.gather(*(finished_or_new(b) for b in batches), return_exceptions=True)
    partial = settle(rc, [[r["id"] for r in b] for b in batches], outcomes, "Design")
    done = [o for o in outcomes if not isinstance(o, BaseException)]
    # each case keeps the review record made for it; ids are assigned below, so the pair travels together
    pairs = [(case, record) for found, records, _, _ in done for case, record in zip(found, records)]
    dropped += [c for _, _, _, over in done for c in over]
    tokens = {k: sum(t.get(k, 0) for _, _, t, _ in done) for k in ("review", "revise", "total")}
    cases = [case for case, _ in pairs]
    # batches number their cases separately, so ids are assigned here
    _number_cases(cases)
    gaps, dupes = model.coverage_gaps(state["requirements"], cases), model.duplicate_scenarios(cases)
    if gaps or dupes:
        rc.log(f"Design checks found gaps {gaps} and duplicates {dupes}; revising", kind="warning")
        affected = {g.split(":")[0] for g in gaps} | {c["requirement_id"] for c in cases if c["id"] in dupes}
        missing = set(partial["missing"]) if partial else set()  # a partial result is not designed again here
        wanted = [r for r in designed if r["id"] in affected - missing] or ([] if partial else designed)
        if wanted:
            revised, over = model.apply_quota(await design(wanted, f"\n\nThese cases failed checks. Gaps: {gaps}. Duplicates: {dupes}. Return a full corrected set for these requirements, within the case quota."), quota)
            dropped += over
            fresh, spent = await review_cases(rc, "design", "design cases", [(f"C{n}", json.dumps(c)) for n, c in enumerate(revised, 1)], lambda keys: _design_evidence(rc, wanted, [revised[int(k[1:]) - 1] for k in keys]), source, DESIGN_REVIEW_BATCH)
            tokens["review"] += spent
            tokens["total"] += spent
            pairs = [p for p in pairs if p[0]["requirement_id"] not in {r["id"] for r in wanted}] + list(zip(revised, fresh))
            cases = [case for case, _ in pairs]
        gaps = model.coverage_gaps(state["requirements"], cases)
    _number_cases(cases)
    records = {case["id"]: {**record, "tc_id": case["id"]} for case, record in pairs}
    # final safety check: after the quota nothing should be cut here, and if something is, it is reported
    cases, cut = model.limit_cases(cases, state["requirements"], max(MAX_CASES, budget["planned"]))
    case_limit = {**cut, "limit": MAX_CASES, "quota": quota, "planned": budget["planned"], "left_out_requirements": budget["left_out_requirements"], "p0_over_limit": budget["p0_over_limit"],
                  "dropped_over_quota": [{k: c.get(k) for k in ("requirement_id", "type", "scenario")} for c in dropped]}
    case_limit["requirements_without_cases"] = [r["id"] for r in state["requirements"] if r["id"] not in {c["requirement_id"] for c in cases}]
    case_limit["left_out_count"] = cut["left_out_count"] + len(dropped)
    case_limit["message"] = budget["message"] + (f"; {len(dropped)} excess cases dropped before review" if dropped else "") + (f"; {cut['left_out_count']} more cut by the final check" if cut["left_out_count"] else "")
    case_limit["notice"] = bool(case_limit["left_out_count"] or budget["left_out_requirements"] or budget["p0_over_limit"])
    if case_limit["notice"]:
        rc.log(case_limit["message"], case_limit, "warning")
    cases_review = confidence.summarise([records[c["id"]] for c in cases], tokens)
    rc.log(f"Design review: {cases_review['counts']}, {tokens['total']} tokens", {"tokens": tokens}, "review")
    columns = "| TC ID | Requirement | Scenario | Type | Level | Precondition | Test Data | Steps | Expected Result | Oracle | Priority |\n|---|---|---|---|---|---|---|---|---|---|---|\n"
    body = columns + "\n".join(f"| {c['id']} | {c['requirement_id']} | {_cell(c['scenario'])} | {c['type']} | {c['level']} | {_cell(c['precondition'])} | {_cell(c['test_data'])} | {_cell(' '.join(f'{i + 1}. {s}' for i, s in enumerate(c['steps'])))} | {_cell(c['expected_result'])} | {c['oracle']} | {c['priority']} |" for c in cases)
    if case_limit["notice"]:
        body = f"> {case_limit['message']}. Requirements with no case now: {', '.join(case_limit['requirements_without_cases']) or 'none'}\n\n" + body
    if partial:
        body = f"> PARTIAL RESULT. No cases yet for: {', '.join(partial['missing'])}\n\n" + body
    doc = documents.create(rc.project_id, "test_cases", f"Test cases (PARTIAL, {len(partial['missing'])} requirements missing)" if partial else "Test cases", body, "agent:test-design-architect", data=cases, prompt_ref=call.prompt_ref, run_id=rc.run_id)
    rc.log(f"{len(cases)} cases designed; {len(gaps)} remaining gaps", {"gaps": gaps}, "artifact")
    return {"cases": cases, "cases_doc": doc["id"], "design_gaps": gaps, "case_limit": case_limit, "cases_review": cases_review, "partial": partial}


async def qe_data(rc: RunContext, state: dict) -> dict:
    """Plugin command qe-data (skill generating-test-data). Code builds the datasets, so this stage uses no model tokens. It is part of Gate 3."""
    fixtures = test_data.build_fixtures(state["cases"])
    used = sorted(fixtures["datasets"])
    doc = documents.create(rc.project_id, "test_data", "Test data", "```json\n" + json.dumps(fixtures, indent=2, ensure_ascii=False) + "\n```", "system", data=fixtures, run_id=rc.run_id)
    rc.log(f"Test data built for {len(fixtures['cases'])} cases from {len(used)} shared datasets ({', '.join(used) or 'none needed'}); no model call", {"document_id": doc["id"]}, "artifact")
    return {"fixtures": fixtures, "fixtures_doc": doc["id"]}


class GeneratedFile(BaseModel):
    path: str
    case_ids: list[str] = Field(min_length=1)
    content: str


class GeneratedSuite(BaseModel):
    framework: str
    files: list[GeneratedFile] = Field(min_length=1)


def _generated_file_problems(item: GeneratedFile, known: set[str], worktree: Path, async_ok: bool = False) -> list[str]:
    errors = list(execution.invalid_test_code(worktree, item.path, item.content, async_ok))
    if not set(item.case_ids) <= known:
        errors.append(f"{item.path}: unknown case ids")
    if issue := execution.syntax_error(item.path, item.content):
        errors.append(issue)
    if re.search(r"assert\s+True\b|expect\(\s*true\s*\)\.toBe\(\s*true\s*\)", item.content):
        errors.append(f"{item.path}: tautological assertion")
    if placeholder := re.search(r"^\s*(pass|\.\.\.)\s*$|\bTODO\b", item.content, re.M):
        errors.append(f"{item.path}: line {item.content.count(chr(10), 0, placeholder.start()) + 1} has placeholder code ({placeholder.group(0).strip()}). Remove it and write real code. Do not use pass, an ellipsis, or the word TODO anywhere in the file")
    if "CASE_ID" not in item.content.splitlines()[0]:
        errors.append(f"{item.path}: first line must be a CASE_ID comment")
    if len(item.case_ids) != 1:
        errors.append(f"{item.path}: one case per file")
    if not item.path.replace("\\", "/").startswith("tests/agentic_qe/"):
        errors.append(f"{item.path}: must live under tests/agentic_qe/")
    return errors


GENERATE_BATCH = 10


async def qe_generate(rc: RunContext, state: dict) -> dict:
    root = repo_dir(rc.project_id)
    if not state.get("worktree"):
        if not root.exists():  # greenfield: tests are written first in a fresh repository
            root.mkdir(parents=True)
            await asyncio.to_thread(git.init_snapshot, root, "Agentic QE Platform greenfield baseline")
            (root / ".gitkeep").write_text("", encoding="utf-8")
            await asyncio.to_thread(git.commit_all, root, "Agentic QE Platform greenfield baseline")
        worktree = project_dir(rc.project_id) / "worktrees" / rc.run_id
        worktree.parent.mkdir(parents=True, exist_ok=True)
        branch = f"atlas/qe-{rc.run_id[-6:]}"
        if not worktree.exists():  # a retry finds the worktree its failed attempt made
            await asyncio.to_thread(git.add_worktree, root, worktree, branch)
        state = {**state, "worktree": str(worktree), "branch": branch}
    worktree = Path(state["worktree"])
    call = AgentCall(rc.run_id, rc.project_id, "test-automation-engineer")
    a = _analysis(rc.project_id)
    known = {c["id"] for c in state["cases"]}
    files_of = {r["id"]: r.get("file") for r in state["requirements"]}
    feedback = f"\nFEEDBACK:\n{state['feedback']}" if state.get("feedback") else ""
    install = bool(state.get("install_deps"))
    declared = emit.declared_dependencies(worktree)
    facts = await asyncio.to_thread(execution.environment_facts, worktree, declared)
    inventory = await asyncio.to_thread(emit.inventory, facts["python"])
    allowed = declared if install else frozenset()  # packages the run will install count as available
    async_ok = bool(facts["pytest_asyncio"] or install)
    notes = execution.environment_notes(facts, install)
    rc.log(f"Environment: httpx {facts['httpx'] or 'not installed'}, pytest-asyncio {'yes' if facts['pytest_asyncio'] else 'no'}, {len(facts['rate_limiters'])} rate limiters" + ("" if inventory else ". The installed packages could not be read, so the third-party import check is skipped"), facts)

    async def generate_batch(cases: list[dict]) -> tuple[dict[str, GeneratedFile], str, list[str]]:
        # each batch sees only the code its cases test, which keeps every request small
        batch_call = AgentCall(rc.run_id, rc.project_id, "test-automation-engineer")
        code = code_pack(rc.project_id, worktree, list(dict.fromkeys(files_of[c["requirement_id"]] for c in cases if files_of.get(c["requirement_id"]))) or None, limit=30_000)
        wanted = {c["id"] for c in cases}
        under_test = list(dict.fromkeys(files_of[c["requirement_id"]] for c in cases if files_of.get(c["requirement_id"])))
        request = (f"Generate executable tests under tests/agentic_qe/ for these cases, one file per case. Send a file for every case.\nCASES:\n{json.dumps(cases)}\nDETECTED RUNNERS: {a['test_runners']}\n"
                   f"Import only names you can see in this code. Name each test function with its case id, for example test_TC_APP_001_empty_input.\n"
                   f"tests/agentic_qe/fixtures.json holds the shared datasets under \"datasets\" and each case's own data under \"cases\"; load it with json and pathlib relative to __file__.\n"
                   f"{notes}\n{emit.signatures(worktree, under_test)}{feedback}\n\nCODE:\n{code}")
        key = part_key("generate", sorted(wanted), state.get("feedback", ""))
        if saved := rc.kept(key):
            rc.log(f"Kept result reused for {len(wanted)} cases")
            return {p: GeneratedFile(**f) for p, f in saved["accepted"].items()}, saved["framework"], saved["errors"]
        accepted: dict[str, GeneratedFile] = {}
        errors: list[str] = []
        framework = ""
        for _ in range(3):
            try:
                suite = await batch_call.typed(request, GeneratedSuite)
            except AllowanceError:
                raise
            except AqeError as exc:
                if not accepted:
                    raise  # nothing from this batch is usable, so it is the one a retry repeats
                errors = [str(exc)[:300]]
                break
            framework = suite.framework
            errors = []
            for item in suite.files:
                problems = _generated_file_problems(item, known, worktree, async_ok)
                if problems:
                    errors.extend(problems)
                    accepted.pop(item.path, None)
                else:
                    accepted[item.path] = item
            covered = {cid for f in accepted.values() for cid in f.case_ids}
            missing = sorted(wanted - covered)
            if not errors and not missing:
                break
            # only what is refused or missing goes round again, because resending a whole batch costs many thousands of tokens
            request = "These generated test files were refused. Send corrected versions of only these files, with the same paths and case ids.\nPROBLEMS:\n" + "\n".join(errors[:40]) + (f"\nThese cases have no test yet, so send one file for each: {missing}" if missing else "") + f"\n\nCODE:\n{code}"
        rc.keep(key, {"accepted": {p: f.model_dump() for p, f in accepted.items()}, "framework": framework, "errors": errors})
        return accepted, framework, errors

    batches = [state["cases"][i : i + GENERATE_BATCH] for i in range(0, len(state["cases"]), GENERATE_BATCH)]
    outcomes = await asyncio.gather(*(generate_batch(batch) for batch in batches), return_exceptions=True)
    partial = settle(rc, [[c["id"] for c in b] for b in batches], outcomes, "Generate")
    outcomes = [o for o in outcomes if not isinstance(o, BaseException)]
    accepted = {path: item for found, _, _ in outcomes for path, item in found.items()}
    errors = [problem for _, _, found in outcomes for problem in found]
    if not accepted:
        raise ModelSchemaError(f"Generated tests failed checks: {errors}", action="Retry the stage. Each problem above names the file and the rule it broke.")
    suite = GeneratedSuite(framework=next((framework for _, framework, _ in outcomes if framework), ""), files=list(accepted.values()))
    missing = sorted(known - {cid for f in suite.files for cid in f.case_ids})
    if missing:
        rc.log(f"{len(missing)} of {len(known)} cases have no test: {missing[:30]}", {"problems": errors[:20]}, "warning")
    case_of = {c["id"]: c for c in state["cases"]}
    static_findings = lambda item: emit.check(worktree, item.path, item.content, inventory, allowed)
    unresolved: list[dict] = []
    flagged = {i: found for i, item in enumerate(suite.files) if (found := static_findings(item))}
    if flagged:
        rc.log(f"{len(flagged)} generated tests failed the static checks. Each goes back alone, once", {"findings": {suite.files[i].path: found[:5] for i, found in flagged.items()}}, "warning")

    async def send_back(i: int, found: list[str]) -> GeneratedFile:
        old = suite.files[i]
        case = case_of.get(old.case_ids[0], {})
        under_test = files_of.get(case.get("requirement_id"))
        again = AgentCall(rc.run_id, rc.project_id, "test-automation-engineer")
        result = await again.typed(f"Rewrite only this generated test file and fix every problem the static checks found. Send a suite with exactly this one file, with the same path and case id.\nCASE:\n{json.dumps(case)}\n"
                                   f"CURRENT FILE {old.path}:\n{old.content}\nPROBLEMS, each with the real signature:\n" + "\n".join(found[:20]) + f"\n{notes}\n{emit.signatures(worktree, [under_test] if under_test else [])}", GeneratedSuite, attempts=2)
        new = next((f for f in result.files if f.path == old.path and f.case_ids == old.case_ids), None)
        if new is None:
            raise ValueError("The agent did not send back the same file for the same case")
        if problems := _generated_file_problems(new, known, worktree, async_ok):
            raise ValueError("; ".join(problems[:3]))
        return new

    outcomes = await asyncio.gather(*(send_back(i, found) for i, found in flagged.items()), return_exceptions=True)
    for (i, found), outcome in zip(flagged.items(), outcomes):
        if isinstance(outcome, BaseException) and not isinstance(outcome, Exception):
            raise outcome
        if isinstance(outcome, AllowanceError):
            raise outcome
        remaining = found
        if isinstance(outcome, Exception):
            rc.log(f"{suite.files[i].path} could not be sent back: {str(outcome)[:200]}", kind="warning")
        elif len(after := static_findings(outcome)) <= len(found):  # the new file replaces the old one unless it is worse
            suite.files[i], remaining = outcome, after
        if remaining:
            unresolved.append({"path": suite.files[i].path, "case_id": suite.files[i].case_ids[0], "findings": remaining[:10]})
    if unresolved:
        rc.log(f"{len(unresolved)} tests still fail the static checks after one round. They stay, marked", {"unresolved": unresolved}, "warning")
    edits = [Edit(path=f.path, action="create", content=f.content) for f in suite.files]
    if state.get("fixtures"):
        edits.append(Edit(path="tests/agentic_qe/fixtures.json", action="create", content=json.dumps(state["fixtures"], indent=2, ensure_ascii=False)))
    errors = apply_edits(worktree, edits)
    if errors:
        raise RuntimeError(f"Generated tests refused: {errors}")
    marked = {u["path"] for u in unresolved}
    tests = [{"case_id": cid, "path": f.path, **({"unresolved": True} if f.path in marked else {})} for f in suite.files for cid in f.case_ids]

    def test_text(item: GeneratedFile) -> str:
        numbered = "\n".join(f"{n}: {line}" for n, line in enumerate(item.content.splitlines(), 1))
        return f"TEST FILE {item.path}\n{numbered[:8_000]}\nCASE:\n{json.dumps(case_of.get(item.case_ids[0], {}))}"

    def test_evidence(indexes: list[int]) -> str:
        chosen = {case_of[suite.files[i].case_ids[0]]["requirement_id"] for i in indexes if suite.files[i].case_ids[0] in case_of}
        return review_evidence(rc.project_id, [r for r in state["requirements"] if r["id"] in chosen], worktree)

    async def revise_test(i: int, record: dict, calls: list) -> str:
        # the test goes back alone with its own flaws; the same checks as a first draft apply to what comes back
        old = suite.files[i]
        again = AgentCall(rc.run_id, rc.project_id, "test-automation-engineer")
        calls.append(again)
        result = await again.typed(f"Rewrite only this generated test file and fix every flaw the independent reviewer found. Send a suite with exactly this one file, with the same path and case id.\nCASE:\n{json.dumps(case_of.get(old.case_ids[0], {}))}\n"
                                   f"CURRENT FILE {old.path}:\n{old.content}\nFLAWS AND FIXES:\n{confidence.flaw_lines(record)}\n\n{test_evidence([i])}", GeneratedSuite, attempts=2)
        new = next((f for f in result.files if f.path == old.path), None)
        if new is None or new.case_ids != old.case_ids:
            raise ValueError("The agent did not send back the same file for the same case")
        if problems := [*_generated_file_problems(new, known, worktree, async_ok), *(found if len(found := static_findings(new)) > len(static_findings(old)) else [])]:
            raise ValueError("; ".join(problems[:3]))
        if refused := apply_edits(worktree, [Edit(path=new.path, action="create", content=new.content)]):
            raise ValueError("; ".join(refused[:3]))
        suite.files[i] = new
        return test_text(new)

    records, tokens = await review_with_send_back(rc, "code", "generated tests", [(f.case_ids[0], test_text(f)) for f in suite.files], test_evidence, worktree, revise_test, CODE_REVIEW_BATCH)
    for record, item in zip(records, suite.files):
        record["file"] = record.get("file") or item.path
    tests_review = confidence.summarise(records, tokens)
    flagged_text = {u["path"]: "> STATIC CHECK FINDINGS, still open after one round trip to the agent:\n" + "\n".join(f"> - {x}" for x in u["findings"]) + "\n\n" for u in unresolved}
    body = "\n\n".join(f"## {f.path}\n\nCases: {', '.join(f.case_ids)}\n\n{flagged_text.get(f.path, '')}```\n{f.content}\n```" for f in suite.files)
    if partial:
        body = f"> PARTIAL RESULT. No tests yet for: {', '.join(partial['missing'])}\n\n" + body
    doc = documents.create(rc.project_id, "test_code", "Generated tests (PARTIAL)" if partial else "Generated tests", body, "agent:test-automation-engineer", data=tests, prompt_ref=call.prompt_ref, run_id=rc.run_id)
    rc.log(f"{len(suite.files)} test files written to {state['branch']}", kind="artifact")
    return {"worktree": state["worktree"], "branch": state["branch"], "tests": tests, "framework": suite.framework, "test_doc": doc["id"], "heal_attempts": state.get("heal_attempts", 0), "tests_review": tests_review, "tests_missing": missing, "emit_unresolved": unresolved, "env_facts": facts, "partial": partial}


async def qe_prepare(rc: RunContext, state: dict) -> dict:
    """Setup before the tests run: dependencies (only when the run opted in), pytest-asyncio for async tests, and the facts the classification and the report use."""
    worktree = Path(state["worktree"])
    try:
        if state.get("install_deps"):
            await asyncio.to_thread(execution.install_dependencies, worktree, _analysis(rc.project_id), rc.log)
        declared = emit.declared_dependencies(worktree)
        facts = await asyncio.to_thread(execution.environment_facts, worktree, declared)
        asyncs = await asyncio.to_thread(execution.async_test_files, worktree)
        if asyncs and not facts["pytest_asyncio"] and state.get("install_deps"):
            await asyncio.to_thread(execution.install_pytest_asyncio, worktree, rc.log)
            facts = await asyncio.to_thread(execution.environment_facts, worktree, declared)
    except (subprocess.SubprocessError, OSError) as exc:
        raise ExecutionError(f"Dependencies could not be installed: {type(exc).__name__}: {str(exc)[:200]}") from exc
    # a command-line option for the generated tests only: the repository's own configuration is not edited
    args = ["-o", "asyncio_mode=auto"] if asyncs and facts["pytest_asyncio"] else []
    if asyncs and not facts["pytest_asyncio"]:
        rc.log(f"{len(asyncs)} async tests need pytest-asyncio, which is not installed. They will fail and be classed as environment", {"files": asyncs[:20]}, "warning")
    rc.log(f"Prepared: httpx {facts['httpx'] or 'none'}, pytest-asyncio {'yes' if facts['pytest_asyncio'] else 'no'}, {len(asyncs)} async tests, {len(facts['rate_limiters'])} rate limiters", {"pytest_args": args, "rate_limiters": facts["rate_limiters"]})
    return {"env_facts": facts, "async_tests": asyncs, "pytest_args": args}


async def _explain(rc: RunContext, result: dict) -> dict:
    """The qa-execution-engineer's summary, accepted only if every number and the verdict match the JUnit counts. Otherwise code's own summary is used."""
    own = {"text": execution.code_summary(result), "source": "code", "reason": ""}
    if result["passed"] + result["failed"] + result["skipped"] == 0:
        return {**own, "reason": "No test ran, so there is nothing to explain"}
    try:
        reply = await AgentCall(rc.run_id, rc.project_id, "qa-execution-engineer").typed(f"Explain this test result.\nEVIDENCE:\n{json.dumps(execution.summary_evidence(result))}", model.ExecutionSummary)
    except AllowanceError:
        raise
    except Exception as exc:
        rc.log(f"The execution summary did not run, so code's summary is used: {str(exc)[:200]}", kind="warning")
        return {**own, "reason": f"Agent summary did not run: {str(exc)[:200]}"}
    if problems := execution.summary_problems(reply.model_dump(), result):
        rc.log(f"The agent's execution summary was refused, so code's summary is used: {'; '.join(problems[:4])}", {"refused": reply.summary[:500]}, "warning")
        return {**own, "reason": "Agent summary refused: " + "; ".join(problems[:4])}
    return {"text": reply.summary, "source": "agent", "reason": ""}


async def qe_execute(rc: RunContext, state: dict) -> dict:
    worktree = Path(state["worktree"])
    framework = state["framework"].lower()
    runner = next((r for r in execution.REGISTERED if r in framework), framework)
    result = await asyncio.to_thread(execution.run_suite, runner, worktree, "tests/agentic_qe", worktree.parent / f"{rc.run_id}-results", int(state.get("timeout", 300)), tuple(state.get("pytest_args", [])))
    rc.log(f"{runner}: {result['verdict']}. {result['passed']} passed, {result['failed']} failed, {result['skipped']} skipped", {"exit_code": result["exit_code"], "reason": result["reason"], "output": result["output"][-1500:]}, "test")
    explained = await _explain(rc, result)
    update = {"results": [result], "execution_summary": explained, "attempt_history": [*state.get("attempt_history", []), {k: result[k] for k in ("verdict", "passed", "failed")}]}
    if state["mode"] == "greenfield":  # tests written first: failures are the RED baseline, not defects to heal
        rc.log("Greenfield RED baseline recorded. Failures are expected until the app exists.", kind="review")
        update["_next"] = "trace"
    elif result["failed"] and state.get("heal_attempts", 0) < 2:
        update["_next"] = "heal"
    else:
        update["_next"] = "trace"
    return update


class DefectNote(BaseModel):
    test: str
    cause: str = ""
    fix: str = ""


class HealResult(ChangeSet):
    notes: list[DefectNote] = Field(default_factory=list)


def _records(results: list[dict], notes: dict, healed: set[str]) -> list[dict]:
    failed = [c for suite in results for c in suite["cases"] if c["status"] == "failed"]
    return [execution.failure_record(c, execution.classify_failure(c["message"]), c["name"] in healed, notes.get(c["name"]) or notes.get(f"{c['classname']}::{c['name']}")) for c in failed]


async def qe_heal(rc: RunContext, state: dict) -> dict:
    worktree = Path(state["worktree"])
    failures = [c for suite in state["results"] for c in suite["cases"] if c["status"] == "failed"]
    classified = [{**c, "class": execution.classify_failure(c["message"])} for c in failures]
    defects = [c for c in classified if c["class"] == "DEFECT"]
    drift = [c for c in classified if c["class"] in {"SELECTOR_DRIFT", "FIXTURE_DRIFT"}]
    rc.log(f"{len(defects)} application defects left failing, {len(drift)} drift, {len(classified) - len(defects) - len(drift)} environment", {"classes": [{"test": c["name"], "class": c["class"]} for c in classified]}, "review")
    log = [*state.get("healer_log", [])]
    notes = dict(state.get("defect_notes", {}))
    known = {n for c in classified for n in (c["name"], f"{c['classname']}::{c['name']}")}

    def healing_guard(edit: Edit) -> str | None:
        """Plugin rule: healing repairs selectors and fixtures only. It keeps every assertion and never touches application code or a test that found a defect."""
        target = safe_path(worktree, edit.path)
        old = target.read_text(encoding="utf-8") if target.is_file() else ""
        new = edit.content if edit.action == "create" else old.replace(edit.search, edit.replace, 1)
        ok, reason = execution.assertions_preserved(old, new)
        if not edit.path.replace("\\", "/").startswith("tests/"):
            reason, ok = "Healing may only touch tests", False
        elif ok and not execution.heal_allowed(classified, edit.path):
            reason, ok = "Healing may only repair a test that failed from selector or fixture drift. An application defect stays a failing test", False
        return None if ok else reason

    applied: list[str] = []
    if classified:
        shown = json.dumps([{"test": f"{c['classname']}::{c['name']}", "class": c["class"], "message": c["message"][:700]} for c in classified[:30]])[:12000]
        ask = ("Repair only test drift in these failing tests. Never change an assertion's meaning. The line numbers are not part of the files. Also send one note per failing test: its test name, the cause shown by the message, and the fix. "
               "The class of each failure is decided by code and is not yours to change; an application defect gets no edit.\n" if drift else
               "No test here is drift, so send no edits. Send one note per failing test: its test name, the cause shown by the message, and the fix. The class is decided by code.\n")
        try:
            result = await AgentCall(rc.run_id, rc.project_id, "defect-diagnostician").typed(f"{ask}FAILURES:\n{shown}\n\nCODE:\n{code_pack(rc.project_id, worktree, limit=30_000)}", HealResult)
        except AllowanceError:
            raise
        except Exception as exc:
            if drift:
                raise  # a repair that cannot be asked for is a failed stage
            rc.log(f"The defect notes did not run, so the pattern text is used: {str(exc)[:200]}", kind="warning")
            result = HealResult(summary="")
        for note in result.notes:
            if note.test in known:
                notes[note.test] = {"cause": note.cause, "fix": note.fix}
        if drift:
            applied, refused = await asyncio.to_thread(guarded_apply, worktree, result.edits, healing_guard)
            log.append({"applied": applied, "refused": refused, "summary": result.summary[:500]})
            rc.log(f"Healed {applied}; refused {refused}", kind="artifact")
    healed = {c["name"] for c in drift if any(Path(a).stem and re.search(rf"(?<![a-z0-9]){re.escape(Path(a).stem.lower())}(?![a-z0-9])", re.sub(r"[^a-z0-9]+", "_", f"{c['classname']} {c['name']}".lower())) for a in applied)}
    records = _records(state["results"], notes, healed)
    update = {"heal_attempts": state.get("heal_attempts", 0) + 1, "defects": [{"name": c["name"], "message": c["message"][:1500]} for c in defects], "defect_notes": notes, "defect_records": records, "healer_log": log}
    return {**update, "_next": "execute" if applied else "trace"}


def _defect_body(records: list[dict]) -> str:
    if not records:
        return "No failed tests."
    rows = "\n".join(f"| {_cell(r['test'])} | {r['classification']} | {_cell(r['evidence'][:200])} | {_cell(r['cause'])} | {_cell(r['fix'])} | {'yes' if r['healed'] else 'no'} |" for r in records)
    return "| Test | Classification | Evidence | Cause | Fix | Healed |\n|---|---|---|---|---|---|\n" + rows


async def qe_trace(rc: RunContext, state: dict) -> dict:
    results = state.get("results", [])
    defects = state.get("defects", [])
    matrix = trace.build_matrix(state["requirements"], state["cases"], state.get("tests", []), results)
    summary = trace.release_summary(matrix, results, defects)
    failed = [c for suite in results for c in suite["cases"] if c["status"] == "failed"]
    if failed and summary["passed"] == 0 and all(execution.classify_failure(c["message"]) == "ENVIRONMENT" for c in failed):
        summary |= {"verdict": "INCONCLUSIVE", "reason": "Tests could not run in this environment"}
    summary["failure_classes"] = execution.failure_counts(results)  # reported, never used to turn a failure into a pass
    records = _records(results, state.get("defect_notes", {}), {r["test"].split("::")[-1] for r in state.get("defect_records", []) if r["healed"]})
    defect_doc = documents.create(rc.project_id, "defect_report", "Defect records", _defect_body(records), "system", data=records, run_id=rc.run_id)
    lines = ["| Requirement | Priority | Cases | Results | Covered |", "|---|---|---|---|---|"]
    for r in matrix["rows"]:
        lines.append(f"| {r['requirement_id']}: {_cell(r['title'])} | {r['priority']} | {', '.join(c['case_id'] for c in r['cases'])} | {', '.join(c['result'] for c in r['cases'])} | {'yes' if r['covered'] else 'NO'} |")
    doc = documents.create(rc.project_id, "traceability", "Traceability matrix", "\n".join(lines) + f"\n\nGaps: {matrix['gaps'] or 'none'}\n\nOrphan tests: {matrix['orphan_tests'] or 'none'}",
                           "system", data={"matrix": matrix, "summary": summary}, run_id=rc.run_id)
    rc.log(f"Verdict {summary['verdict']}: {summary['passed']}/{summary['executed']} passed, {summary['coverage']}% requirement coverage", summary, "artifact")
    # a score given before the tests ran cannot stand once they have: a failed test is capped, and the post-execution summary shows both numbers
    executed = {c["case_id"]: c["result"] for row in matrix["rows"] for c in row["cases"]}
    after = confidence.cap_failed((state.get("tests_review") or {}).get("records", []), executed)
    rc.log(f"Test review after execution: score {after['score_before']} before, {after['score']} after; {after['capped']} of {after['executed']} executed tests failed and were capped at {confidence.TEST_FAIL_CAP}", {k: after[k] for k in ("score_before", "score", "capped", "failed", "executed")}, "review")
    return {"matrix_doc": doc["id"], "summary": summary, "tests_review_after": after, "defect_records": records, "defect_doc": defect_doc["id"], "_next": "sign"}


async def qe_sign(rc: RunContext, state: dict) -> dict:
    s = state["summary"]
    call = AgentCall(rc.run_id, rc.project_id, "confidence-reviewer")
    review = await call.typed(f"Independently review release readiness from this evidence only.\nSUMMARY:\n{json.dumps(s)}\nDEFECTS:\n{json.dumps(state.get('defects', []))[:6000]}\nHEALER LOG:\n{json.dumps(state.get('healer_log', []))}\nPLAN REVIEW:\n{json.dumps(state.get('plan_review'))}", model.ConfidenceReview)
    body = (f"## Verdict: {s['verdict']}\n\n| Metric | Value |\n|---|---|\n| Tests executed | {s['executed']} |\n| Passed | {s['passed']} |\n| Failed | {s['failed']} |\n| Pass rate | {s['pass_rate']}% |\n"
            f"| Requirements covered | {s['requirements_covered']}/{s['requirements']} ({s['coverage']}%) |\n| Application defects | {s['defects']} |\n| Independent review | {review.score} ({review.verdict}) |\n\n"
            f"## Coverage gaps\n\n{', '.join(s['gaps']) or 'None'}\n\n## Review issues\n\n" + ("\n".join(f"- {i}" for i in review.issues) or "None") + "\n\n## Defect records\n\n" + _defect_body(state.get("defect_records", [])) + "\n\n## Execution summary\n\n" + (state.get("execution_summary") or {}).get("text", "No summary.") + "\n\n## Defects\n\n" + ("\n".join(f"- **{d['name']}**: {d['message'][:300]}" for d in state.get("defects", [])) or "None") + f"\n\nBranch with generated tests: `{state.get('branch', '')}`\n")
    doc = documents.create(rc.project_id, "release", "Release sign-off", body, "agent:confidence-reviewer", data={"summary": s, "review": review.model_dump()}, prompt_ref=call.prompt_ref, run_id=rc.run_id)
    return {"release_doc": doc["id"], "release_review": review.model_dump()}


def _doc_gate(gate: int, label: str, doc_key: str, summary, review_key: str = "", extras=None):
    def build(rc: RunContext, state: dict):
        review = state.get(review_key) if review_key else None
        payload = {"documents": [state[doc_key]], "titles": [documents.get(state[doc_key])["title"]]}
        if gate == 1 and state.get("discovery_id"):
            payload = {"documents": [state["discovery_id"], *payload["documents"]], "titles": ["Discovery summary", *payload["titles"]]}
        if review:
            payload["confidence"] = review
        if extras:
            payload |= extras(rc, state)
        payload["tokens"] = tokens = token_line(rc.run_id)
        if state.get("partial"):
            payload["partial"] = state["partial"]
            return {"gate": gate, "title": f"Gate {gate} (PARTIAL): {label}", "summary": f"PARTIAL RESULT, not complete. Missing: {', '.join(state['partial']['missing'])}. {summary(state)} {tokens['text']}", "payload": payload}
        return {"gate": gate, "title": f"Gate {gate}: approve {label}", "summary": f"{summary(state)} {tokens['text']}", "payload": payload}

    return build


async def qe_commit(rc: RunContext, state: dict, answer: dict) -> dict:
    commit = await asyncio.to_thread(git.commit_all, Path(state["worktree"]), f"Add Agentic QE Platform generated tests\n\nApproved by {answer['by']} in run {rc.run_id}")
    return {"test_commit": commit}


def _gate3_extras(rc: RunContext, state: dict) -> dict:
    # what generation will probably cost, from the design calls this run has really made; the tests are assumed to cost about what a design call did
    batches = -(-len(state["cases"]) // GENERATE_BATCH)
    extra = {"case_limit": state.get("case_limit"), "estimate": token_estimate(rc.run_id, "test-design-architect", batches, f"generation of {len(state['cases'])} cases in {batches} batches",
                                                                                f"average of the design agent's recorded calls, assuming a generation batch costs about one design call; reviews of the tests are not included")}
    if state.get("fixtures_doc"):
        extra |= {"documents": [state["cases_doc"], state["fixtures_doc"]], "titles": ["Test cases", "Test data"]}
    return extra


def _gate4_extras(rc: RunContext, state: dict) -> dict:
    return {"emit_unresolved": state.get("emit_unresolved", []), "estimate": token_estimate(rc.run_id, None, 4, "execution summary, up to two repair attempts, and the release review",
                                                                                          "upper bound: the average of every model call this run has recorded, times four calls")}


def _gate5_extras(rc: RunContext, state: dict) -> dict:
    return {"defect_records": state.get("defect_records", []), "execution_summary": state.get("execution_summary"), "failure_classes": state["summary"].get("failure_classes")}


def qe_definition() -> Definition:
    return Definition("qe", [
        StageSpec("intake", intake, "Intake", approval=intake_gate, next="discover"),
        StageSpec("discover", qe_discover, "Discovery", next="requirements"),
        StageSpec("requirements", qe_requirements, "Requirements", approval=_doc_gate(1, "requirements", "requirements_doc", lambda s: f"{len(s['requirements'])} requirements with verified evidence.", "requirements_review"), on_rejected="requirements", next="plan"),
        StageSpec("plan", qe_plan, "Test plan", approval=_doc_gate(2, "test plan", "plan_doc", lambda s: f"Deterministic score {s['plan_score']['score']}, independent review {s['plan_review']['score'] if s['plan_review']['score'] is not None else 'not run'} ({s['plan_review']['verdict']}).", "plan_review"), on_rejected="plan", next="design"),
        StageSpec("design", qe_design, "Test design", next="data"),
        StageSpec("data", qe_data, "Test data", approval=_doc_gate(3, "test design and data", "cases_doc", lambda s: f"{len(s['cases'])} cases. {s['case_limit']['message']}. Remaining gaps: {s['design_gaps'] or 'none'}.", "cases_review", _gate3_extras), on_rejected="design", next="generate"),
        StageSpec("generate", qe_generate, "Generate tests", approval=_doc_gate(4, "generated tests", "test_doc", lambda s: f"{len(s['tests'])} of {len(s['cases'])} cases have tests, on branch {s['branch']}. Approving also allows them to run on this machine.", "tests_review", _gate4_extras), on_approved=qe_commit, on_rejected="generate", next="prepare"),
        StageSpec("prepare", qe_prepare, "Prepare environment", next="execute"),
        StageSpec("execute", qe_execute, "Execute"),
        StageSpec("heal", qe_heal, "Heal test drift"),
        StageSpec("trace", qe_trace, "Traceability"),
        StageSpec("sign", qe_sign, "Release sign-off", approval=_doc_gate(5, "release", "release_doc", lambda s: f"Verdict {s['summary']['verdict']}: {s['summary']['passed']}/{s['summary']['executed']} tests passed. {s['tests_review_after']['capped']} reviewed tests failed and are capped at {confidence.TEST_FAIL_CAP}.", "tests_review_after", _gate5_extras), next="END"),
    ], routes={"execute": ["heal", "trace"], "heal": ["execute", "trace"], "trace": ["sign"]})


REGISTRY["qe"] = qe_definition
