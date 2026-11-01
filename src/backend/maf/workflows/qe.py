"""QE lifecycle: requirements to signed release, with human gates G0 to G5."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from backend.config import project_dir, repo_dir
from backend.core import documents
from backend.core.security import (
    safe_path,
)
from backend.maf.engine import REGISTRY, Definition, RunContext, StageSpec
from backend.maf.runtime import AgentCall
from backend.maf.workflows.ba import _strip_preamble
from backend.maf.workflows.edits import ChangeSet, Edit, apply_edits, guarded_apply
from backend.maf.workflows.shared import (
    _analysis,
    _brief_of_analysis,
    code_pack,
    intake,
    intake_gate,
)
from backend.qe import execution, model, trace
from backend.repos import git, static_analysis


async def qe_discover(rc: RunContext, state: dict) -> dict:
    a = _analysis(rc.project_id)
    text = await (call := AgentCall(rc.run_id, rc.project_id, "repo_analyst")).text(f"Write the discovery summary from these scan facts and this code.\n\nSCAN:\n{_brief_of_analysis(a)}\n\nCODE:\n{code_pack(rc.project_id, limit=25_000)}")
    text = _strip_preamble(text)
    doc = documents.create(rc.project_id, "discovery", "Discovery summary", text, "agent:repo_analyst", data=a, prompt_ref=call.prompt_ref, run_id=rc.run_id)
    rc.log("Discovery saved", {"document_id": doc["id"]}, "artifact")
    return {"discovery_id": doc["id"]}


async def qe_requirements(rc: RunContext, state: dict) -> dict:
    root = repo_dir(rc.project_id)
    brownfield = state["mode"] == "brownfield"
    call = AgentCall(rc.run_id, rc.project_id, "requirements_analyst")
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
    result = await call.typed(prompt, model.RequirementSet)
    kept, dropped = [], []
    for requirement in result.requirements:
        if brownfield and requirement.tier != "specified":
            ok, line = static_analysis.verify_quote(root, requirement.file, requirement.line, requirement.quote)
            if not ok:
                dropped.append(requirement.id)
                continue
            requirement.line = line
        kept.append(requirement.model_dump())
    if not kept:
        raise RuntimeError("No requirement survived evidence verification")
    rc.log(f"{len(kept)} requirements verified; {len(dropped)} dropped for missing evidence", {"dropped": dropped})
    body = "| ID | Requirement | Priority | Tier | Evidence |\n|---|---|---|---|---|\n" + "\n".join(
        f"| {r['id']} | {_cell(r['title'])}: {_cell(r['statement'])} | {r['priority']} | {r['tier']} | {('`' + r['file'] + ':' + str(r['line']) + '`') if r['file'] else '-'} |" for r in kept)
    doc = documents.create(rc.project_id, "requirements", "Requirements", body, "agent:requirements_analyst", data=kept, prompt_ref=call.prompt_ref, run_id=rc.run_id)
    return {"requirements": kept, "requirements_doc": doc["id"]}


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


async def qe_plan(rc: RunContext, state: dict) -> dict:
    call = AgentCall(rc.run_id, rc.project_id, "test_architect")
    a = _analysis(rc.project_id)
    prompt = f"Create the test plan.\nREQUIREMENTS:\n{json.dumps(state['requirements'])}\nDETECTED RUNNERS: {a['test_runners']}\nFRAMEWORKS: {a['frameworks']}\nEXISTING TESTS: {a.get('test_files', [])[:40]}" + (f"\nFEEDBACK:\n{state['feedback']}" if state.get("feedback") else "")
    plan = (await call.typed(prompt, model.TestPlan)).model_dump()
    score = model.plan_confidence(state["requirements"], plan)
    if score["verdict"] != "APPROVED":
        plan = (await call.typed(f"{prompt}\n\nAutomatic checks rejected your plan: {score['issues']}. Fix them.", model.TestPlan)).model_dump()
        score = model.plan_confidence(state["requirements"], plan)
    review = await AgentCall(rc.run_id, rc.project_id, "confidence_reviewer").typed(f"Score this test plan against its requirements.\nREQUIREMENTS:\n{json.dumps(state['requirements'])}\nPLAN:\n{json.dumps(plan)}", model.ConfidenceReview)
    rc.log(f"Plan score {score['score']} ({score['verdict']}), independent review {review.score} ({review.verdict})", {"deterministic": score, "review": review.model_dump()}, "review")
    body = f"{plan['strategy']}\n\n| Area | Requirements | Risk | Level | Framework | Rationale |\n|---|---|---|---|---|---|\n" + "\n".join(
        f"| {_cell(x['name'])} | {', '.join(x['requirement_ids'])} | {x['risk']} | {x['level']} | {x['framework']} | {_cell(x['rationale'])} |" for x in plan["areas"])
    doc = documents.create(rc.project_id, "test_plan", "Test plan", body, "agent:test_architect", data={"plan": plan, "score": score, "review": review.model_dump()}, prompt_ref=call.prompt_ref, run_id=rc.run_id)
    return {"plan": plan, "plan_doc": doc["id"], "plan_score": score, "plan_review": review.model_dump()}


DESIGN_BATCH = 6


def _number_cases(cases: list[dict]) -> None:
    for number, case in enumerate(cases, 1):
        case["id"] = f"TC-APP-{number:03d}"


async def qe_design(rc: RunContext, state: dict) -> dict:
    call = AgentCall(rc.run_id, rc.project_id, "test_designer")
    feedback = f"\nFEEDBACK:\n{state['feedback']}" if state.get("feedback") else ""

    async def design(requirements: list[dict], note: str = "") -> list[dict]:
        # each batch has its own conversation, so batches can run together
        batch_call = AgentCall(rc.run_id, rc.project_id, "test_designer")
        result = await batch_call.typed(f"Design test cases for only these requirements.\nREQUIREMENTS:\n{json.dumps(requirements)}\nPLAN:\n{json.dumps(state['plan'])}{feedback}{note}", model.CaseSet)
        return [c.model_dump() for c in result.cases]

    # one large reply breaks on real repositories, so requirements go in small batches and code merges the results
    batches = [state["requirements"][i : i + DESIGN_BATCH] for i in range(0, len(state["requirements"]), DESIGN_BATCH)]
    cases = [c for found in await asyncio.gather(*(design(b) for b in batches)) for c in found]
    # batches number their cases separately, so ids are assigned here
    _number_cases(cases)
    gaps, dupes = model.coverage_gaps(state["requirements"], cases), model.duplicate_scenarios(cases)
    if gaps or dupes:
        rc.log(f"Design checks found gaps {gaps} and duplicates {dupes}; revising", kind="warning")
        affected = {g.split(":")[0] for g in gaps} | {c["requirement_id"] for c in cases if c["id"] in dupes}
        wanted = [r for r in state["requirements"] if r["id"] in affected] or state["requirements"]
        revised = await design(wanted, f"\n\nThese cases failed checks. Gaps: {gaps}. Duplicates: {dupes}. Return a full corrected set for these requirements.")
        cases = [c for c in cases if c["requirement_id"] not in {r["id"] for r in wanted}] + revised
        gaps = model.coverage_gaps(state["requirements"], cases)
    _number_cases(cases)
    columns = "| TC ID | Requirement | Scenario | Type | Level | Precondition | Test Data | Steps | Expected Result | Oracle | Priority |\n|---|---|---|---|---|---|---|---|---|---|---|\n"
    body = columns + "\n".join(f"| {c['id']} | {c['requirement_id']} | {_cell(c['scenario'])} | {c['type']} | {c['level']} | {_cell(c['precondition'])} | {_cell(c['test_data'])} | {_cell(' '.join(f'{i + 1}. {s}' for i, s in enumerate(c['steps'])))} | {_cell(c['expected_result'])} | {c['oracle']} | {c['priority']} |" for c in cases)
    doc = documents.create(rc.project_id, "test_cases", "Test cases", body, "agent:test_designer", data=cases, prompt_ref=call.prompt_ref, run_id=rc.run_id)
    fixtures = {c["id"]: c["test_data"] for c in cases if c["test_data"]}
    if fixtures:
        documents.create(rc.project_id, "test_data", "Test data", "```json\n" + json.dumps(fixtures, indent=2) + "\n```", "agent:test_designer", data=fixtures, run_id=rc.run_id)
    rc.log(f"{len(cases)} cases designed; {len(gaps)} remaining gaps", {"gaps": gaps}, "artifact")
    return {"cases": cases, "cases_doc": doc["id"], "design_gaps": gaps, "fixtures": fixtures}


class GeneratedFile(BaseModel):
    path: str
    case_ids: list[str] = Field(min_length=1)
    content: str


class GeneratedSuite(BaseModel):
    framework: str
    files: list[GeneratedFile] = Field(min_length=1)


def _generated_file_problems(item: GeneratedFile, known: set[str], worktree: Path) -> list[str]:
    errors = list(execution.invalid_test_code(worktree, item.path, item.content))
    if not set(item.case_ids) <= known:
        errors.append(f"{item.path}: unknown case ids")
    if issue := execution.syntax_error(item.path, item.content):
        errors.append(issue)
    if re.search(r"assert\s+True\b|expect\(\s*true\s*\)\.toBe\(\s*true\s*\)", item.content):
        errors.append(f"{item.path}: tautological assertion")
    if re.search(r"^\s*(pass|\.\.\.)\s*$|\bTODO\b", item.content, re.M):
        errors.append(f"{item.path}: placeholder code")
    if "CASE_ID" not in item.content.splitlines()[0]:
        errors.append(f"{item.path}: first line must be a CASE_ID comment")
    if len(item.case_ids) != 1:
        errors.append(f"{item.path}: one case per file")
    if not item.path.replace("\\", "/").startswith("tests/agentic_qe/"):
        errors.append(f"{item.path}: must live under tests/agentic_qe/")
    return errors


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
        await asyncio.to_thread(git.add_worktree, root, worktree, branch)
        state = {**state, "worktree": str(worktree), "branch": branch}
    worktree = Path(state["worktree"])
    call = AgentCall(rc.run_id, rc.project_id, "test_automation")
    a = _analysis(rc.project_id)
    # the files under test go first, so the code pack limit never drops what the cases are about
    under_test = list(dict.fromkeys(r["file"] for r in state["requirements"] if r.get("file")))
    prompt = (f"Generate executable tests under tests/agentic_qe/ for these cases, one file per case.\nCASES:\n{json.dumps(state['cases'])}\nDETECTED RUNNERS: {a['test_runners']}\n"
              f"Import only names you can see in this code. Name each test function with its case id, for example test_TC_APP_001_empty_input.\n\nCODE:\n{code_pack(rc.project_id, worktree, under_test or None, limit=60_000)}" + (f"\nFEEDBACK:\n{state['feedback']}" if state.get("feedback") else ""))
    known = {c["id"] for c in state["cases"]}
    accepted: dict[str, GeneratedFile] = {}
    errors: list[str] = []
    framework = ""
    request = prompt
    for _ in range(3):
        suite = await call.typed(request, GeneratedSuite)
        framework = suite.framework
        errors = []
        for item in suite.files:
            problems = _generated_file_problems(item, known, worktree)
            if problems:
                errors.extend(problems)
                accepted.pop(item.path, None)
            else:
                accepted[item.path] = item
        if not errors:
            break
        # only the refused files go round again, because resending a whole suite costs many thousands of tokens
        request = "These generated test files were refused. Send corrected versions of only these files, with the same paths and case ids.\nPROBLEMS:\n" + "\n".join(errors[:40]) + f"\n\nCODE:\n{code_pack(rc.project_id, worktree, under_test or None, limit=60_000)}"
    else:
        raise RuntimeError(f"Generated tests failed checks: {errors}")
    suite = GeneratedSuite(framework=framework, files=list(accepted.values()))
    edits = [Edit(path=f.path, action="create", content=f.content) for f in suite.files]
    if state.get("fixtures"):
        edits.append(Edit(path="tests/agentic_qe/fixtures.json", action="create", content=json.dumps(state["fixtures"], indent=2)))
    errors = apply_edits(worktree, edits)
    if errors:
        raise RuntimeError(f"Generated tests refused: {errors}")
    tests = [{"case_id": cid, "path": f.path} for f in suite.files for cid in f.case_ids]
    body = "\n\n".join(f"## {f.path}\n\nCases: {', '.join(f.case_ids)}\n\n```\n{f.content}\n```" for f in suite.files)
    doc = documents.create(rc.project_id, "test_code", "Generated tests", body, "agent:test_automation", data=tests, prompt_ref=call.prompt_ref, run_id=rc.run_id)
    rc.log(f"{len(suite.files)} test files written to {state['branch']}", kind="artifact")
    return {"worktree": state["worktree"], "branch": state["branch"], "tests": tests, "framework": suite.framework, "test_doc": doc["id"], "heal_attempts": state.get("heal_attempts", 0)}


async def qe_execute(rc: RunContext, state: dict) -> dict:
    worktree = Path(state["worktree"])
    if state.get("install_deps"):
        await asyncio.to_thread(execution.install_dependencies, worktree, _analysis(rc.project_id), rc.log)
    framework = state["framework"].lower()
    runner = next((r for r in execution.REGISTERED if r in framework), framework)
    result = await asyncio.to_thread(execution.run_suite, runner, worktree, "tests/agentic_qe", worktree.parent / f"{rc.run_id}-results", int(state.get("timeout", 300)))
    rc.log(f"{runner}: {result['verdict']}. {result['passed']} passed, {result['failed']} failed, {result['skipped']} skipped", {"exit_code": result["exit_code"], "reason": result["reason"], "output": result["output"][-1500:]}, "test")
    update = {"results": [result], "attempt_history": [*state.get("attempt_history", []), {k: result[k] for k in ("verdict", "passed", "failed")}]}
    if state["mode"] == "greenfield":  # tests written first: failures are the RED baseline, not defects to heal
        rc.log("Greenfield RED baseline recorded. Failures are expected until the app exists.", kind="review")
        update["_next"] = "trace"
    elif result["failed"] and state.get("heal_attempts", 0) < 2:
        update["_next"] = "heal"
    else:
        update["_next"] = "trace"
    return update


async def qe_heal(rc: RunContext, state: dict) -> dict:
    worktree = Path(state["worktree"])
    failures = [c for suite in state["results"] for c in suite["cases"] if c["status"] == "failed"]
    classified = [{**c, "class": execution.classify_failure(c["message"])} for c in failures]
    defects = [c for c in classified if c["class"] == "DEFECT"]
    drift = [c for c in classified if c["class"] in {"SELECTOR_DRIFT", "FIXTURE_DRIFT"}]
    rc.log(f"{len(defects)} application defects left failing, {len(drift)} drift, {len(classified) - len(defects) - len(drift)} environment", {"classes": [{"test": c["name"], "class": c["class"]} for c in classified]}, "review")
    log = [*state.get("healer_log", [])]
    update = {"heal_attempts": state.get("heal_attempts", 0) + 1, "defects": [{"name": c["name"], "message": c["message"][:1500]} for c in defects]}
    if not drift:
        return {**update, "healer_log": log, "_next": "trace"}

    def healing_guard(edit: Edit) -> str | None:
        """Plugin rule: healing may only touch tests and must keep every assertion."""
        target = safe_path(worktree, edit.path)
        old = target.read_text(encoding="utf-8") if target.is_file() else ""
        new = edit.content if edit.action == "create" else old.replace(edit.search, edit.replace, 1)
        ok, reason = execution.assertions_preserved(old, new)
        if not edit.path.replace("\\", "/").startswith("tests/"):
            reason, ok = "Healing may only touch tests", False
        return None if ok else reason

    result = await AgentCall(rc.run_id, rc.project_id, "defect_diagnostician").typed(
        f"Repair only test drift in these failing tests. Never change an assertion's meaning. The line numbers are not part of the files.\nFAILURES:\n{json.dumps(drift)[:12000]}\n\nCODE:\n{code_pack(rc.project_id, worktree, limit=30_000)}", ChangeSet)
    applied, refused = await asyncio.to_thread(guarded_apply, worktree, result.edits, healing_guard)
    log.append({"applied": applied, "refused": refused, "summary": result.summary[:500]})
    rc.log(f"Healed {applied}; refused {refused}", kind="artifact")
    return {**update, "healer_log": log, "_next": "execute" if applied else "trace"}


async def qe_trace(rc: RunContext, state: dict) -> dict:
    results = state.get("results", [])
    defects = state.get("defects", [])
    matrix = trace.build_matrix(state["requirements"], state["cases"], state.get("tests", []), results)
    summary = trace.release_summary(matrix, results, defects)
    failed = [c for suite in results for c in suite["cases"] if c["status"] == "failed"]
    if failed and summary["passed"] == 0 and all(execution.classify_failure(c["message"]) == "ENVIRONMENT" for c in failed):
        summary |= {"verdict": "INCONCLUSIVE", "reason": "Tests could not run in this environment"}
    lines = ["| Requirement | Priority | Cases | Results | Covered |", "|---|---|---|---|---|"]
    for r in matrix["rows"]:
        lines.append(f"| {r['requirement_id']}: {_cell(r['title'])} | {r['priority']} | {', '.join(c['case_id'] for c in r['cases'])} | {', '.join(c['result'] for c in r['cases'])} | {'yes' if r['covered'] else 'NO'} |")
    doc = documents.create(rc.project_id, "traceability", "Traceability matrix", "\n".join(lines) + f"\n\nGaps: {matrix['gaps'] or 'none'}\n\nOrphan tests: {matrix['orphan_tests'] or 'none'}",
                           "system", data={"matrix": matrix, "summary": summary}, run_id=rc.run_id)
    rc.log(f"Verdict {summary['verdict']}: {summary['passed']}/{summary['executed']} passed, {summary['coverage']}% requirement coverage", summary, "artifact")
    return {"matrix_doc": doc["id"], "summary": summary, "_next": "sign"}


async def qe_sign(rc: RunContext, state: dict) -> dict:
    s = state["summary"]
    call = AgentCall(rc.run_id, rc.project_id, "confidence_reviewer")
    review = await call.typed(f"Independently review release readiness from this evidence only.\nSUMMARY:\n{json.dumps(s)}\nDEFECTS:\n{json.dumps(state.get('defects', []))[:6000]}\nHEALER LOG:\n{json.dumps(state.get('healer_log', []))}\nPLAN REVIEW:\n{json.dumps(state.get('plan_review'))}", model.ConfidenceReview)
    body = (f"## Verdict: {s['verdict']}\n\n| Metric | Value |\n|---|---|\n| Tests executed | {s['executed']} |\n| Passed | {s['passed']} |\n| Failed | {s['failed']} |\n| Pass rate | {s['pass_rate']}% |\n"
            f"| Requirements covered | {s['requirements_covered']}/{s['requirements']} ({s['coverage']}%) |\n| Application defects | {s['defects']} |\n| Independent review | {review.score} ({review.verdict}) |\n\n"
            f"## Coverage gaps\n\n{', '.join(s['gaps']) or 'None'}\n\n## Review issues\n\n" + ("\n".join(f"- {i}" for i in review.issues) or "None") + "\n\n## Defects\n\n" + ("\n".join(f"- **{d['name']}**: {d['message'][:300]}" for d in state.get("defects", [])) or "None") + f"\n\nBranch with generated tests: `{state.get('branch', '')}`\n")
    doc = documents.create(rc.project_id, "release", "Release sign-off", body, "agent:confidence_reviewer", data={"summary": s, "review": review.model_dump()}, prompt_ref=call.prompt_ref, run_id=rc.run_id)
    return {"release_doc": doc["id"], "release_review": review.model_dump()}


def _doc_gate(gate: int, label: str, doc_key: str, summary):
    def build(rc: RunContext, state: dict):
        return {"gate": gate, "title": f"Gate {gate}: approve {label}", "summary": summary(state), "payload": {"documents": [state[doc_key]], "titles": [documents.get(state[doc_key])["title"]]}}

    return build


async def qe_commit(rc: RunContext, state: dict, answer: dict) -> dict:
    commit = await asyncio.to_thread(git.commit_all, Path(state["worktree"]), f"Add Agentic QE Platform generated tests\n\nApproved by {answer['by']} in run {rc.run_id}")
    return {"test_commit": commit}


def qe_definition() -> Definition:
    return Definition("qe", [
        StageSpec("intake", intake, "Intake", approval=intake_gate, next="discover"),
        StageSpec("discover", qe_discover, "Discovery", next="requirements"),
        StageSpec("requirements", qe_requirements, "Requirements", approval=_doc_gate(1, "requirements", "requirements_doc", lambda s: f"{len(s['requirements'])} requirements with verified evidence."), on_rejected="requirements", next="plan"),
        StageSpec("plan", qe_plan, "Test plan", approval=_doc_gate(2, "test plan", "plan_doc", lambda s: f"Deterministic score {s['plan_score']['score']}, independent review {s['plan_review']['score']}."), on_rejected="plan", next="design"),
        StageSpec("design", qe_design, "Test design", approval=_doc_gate(3, "test design", "cases_doc", lambda s: f"{len(s['cases'])} cases. Remaining gaps: {s['design_gaps'] or 'none'}."), on_rejected="design", next="generate"),
        StageSpec("generate", qe_generate, "Generate tests", approval=_doc_gate(4, "generated tests", "test_doc", lambda s: f"{len(s['tests'])} test mappings on branch {s['branch']}. Approving also allows them to run on this machine."), on_approved=qe_commit, on_rejected="generate", next="execute"),
        StageSpec("execute", qe_execute, "Execute"),
        StageSpec("heal", qe_heal, "Heal test drift"),
        StageSpec("trace", qe_trace, "Traceability"),
        StageSpec("sign", qe_sign, "Release sign-off", approval=_doc_gate(5, "release", "release_doc", lambda s: f"Verdict {s['summary']['verdict']}: {s['summary']['passed']}/{s['summary']['executed']} tests passed."), next="END"),
    ], routes={"execute": ["heal", "trace"], "heal": ["execute", "trace"], "trace": ["sign"]})


REGISTRY["qe"] = qe_definition
