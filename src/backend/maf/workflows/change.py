"""Change workflow: feature, bug fix, or traceback diagnosis on an isolated branch with real tests."""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

from pydantic import BaseModel, Field

from backend.config import project_dir, repo_dir
from backend.core import documents
from backend.core.security import (
    safe_path,
)
from backend.db import db
from backend.maf.engine import REGISTRY, Definition, RunContext, StageSpec
from backend.maf.runtime import AgentCall
from backend.maf.workflows.edits import ChangeSet, Edit, guarded_apply
from backend.maf.workflows.shared import (
    _analysis,
    code_pack,
)
from backend.qe import execution
from backend.repos import git, github, ingest, scan, static_analysis


async def change_prepare(rc: RunContext, state: dict) -> dict:
    root = repo_dir(rc.project_id)
    if not root.exists():
        raise ValueError("Connect a repository or upload a ZIP first")
    if not state.get("spec", "").strip() and not state.get("finding_id"):
        raise ValueError("Describe the change or pick a finding")
    spec = state.get("spec", "")
    if state.get("finding_id"):
        with db() as con:
            finding = dict(con.execute("SELECT * FROM findings WHERE id=? AND project_id=?", (state["finding_id"], rc.project_id)).fetchone())
        spec = f"Fix this finding.\nRule {finding['rule']} ({finding['severity']}): {finding['title']}\nLocation: {finding['file']}:{finding['line']}\nEvidence: {finding['evidence']}\n{finding['explanation']}\n{spec}"
        state["title"] = state.get("title") or f"Fix {finding['title'][:50]}"
    slug = re.sub(r"[^a-z0-9]+", "-", (state.get("title") or state.get("kind", "change")).lower()).strip("-")[:40] or "change"
    branch = f"atlas/{slug}-{rc.run_id[-6:]}"
    worktree = project_dir(rc.project_id) / "worktrees" / rc.run_id
    worktree.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(git.add_worktree, root, worktree, branch)
    rc.log(f"Isolated worktree on branch {branch}")
    # tests run before the change, so a repo that already fails is never blamed on the agent
    analysis = await asyncio.to_thread(_rescan, worktree)
    if state.get("install_deps"):
        await asyncio.to_thread(execution.install_dependencies, worktree, analysis, rc.log)
    baseline = {}
    for runner in execution.choose_runners(analysis):
        result = await asyncio.to_thread(execution.run_suite, runner, worktree, "." if runner == "pytest" else "", worktree.parent / f"{rc.run_id}-baseline")
        baseline[runner] = execution.failed_names(result)
        rc.log(f"Before the change, {runner}: {result['passed']} passed, {result['failed']} failed", {"reason": result["reason"]}, "test")
    return {"branch": branch, "worktree": str(worktree), "spec": spec, "attempt": 0, "baseline": baseline, "title": state.get("title") or slug, "finding_file": finding["file"] if state.get("finding_id") else ""}


class FileSelection(BaseModel):
    files: list[str] = Field(min_length=1)


async def _select_files(rc: RunContext, state: dict, worktree: Path) -> list[str]:
    """Pick the files a change needs, so they travel in the message. Tool results can be lost between model rounds."""
    tree = scan.tree(worktree)
    tests = [f for f in tree if scan.TEST_NAME.search(f)][:6]
    if state.get("finding_file"):
        return [state["finding_file"], *tests]
    if len(tree) <= 15:
        return tree
    picked = await AgentCall(rc.run_id, rc.project_id, "repo_analyst").typed(
        f"Choose up to 12 existing files needed to do this task, including one that shows how similar things are done and one related test.\nTASK:\n{state['spec'][:1500]}\n\nFILES:\n" + "\n".join(tree[:800]), FileSelection)
    chosen = [f for f in picked.files if f in tree]
    return chosen[:12] or static_analysis.rank_files_for_review(worktree, _analysis(rc.project_id), 12)


def spec_gaps(worktree: Path, state: dict) -> list[str]:
    """Deterministic completeness check. Old tests passing does not mean the requested work exists."""
    diff = git.diff(worktree)
    gaps = [f"function {name} named in the task is not in the diff" for name in sorted(set(re.findall(r"\b[a-z]+(?:_[a-z0-9]+)+(?=\()", state["spec"]))) if name not in diff]
    changed = git.run(["diff", "--name-only"], cwd=worktree).splitlines()
    has_tests = any(scan.TEST_NAME.search(f) for f in scan.tree(worktree))
    if state.get("kind") == "feature" and has_tests and not any(scan.TEST_NAME.search(f) for f in changed):
        gaps.append("no test file was added or changed")
    if state.get("finding_file") and state["finding_file"] not in changed:
        gaps.append(f"{state['finding_file']}, the file with the finding, was not changed")
    return gaps


async def change_implement(rc: RunContext, state: dict) -> dict:
    worktree = Path(state["worktree"])
    agent = "defect_diagnostician" if state.get("kind") in {"bugfix", "diagnose"} else "feature_engineer"
    if not state.get("paths"):
        state["paths"] = await _select_files(rc, state, worktree)
    rc.log(f"Working on {len(state['paths'])} files", {"files": state["paths"]})
    message = f"TASK (do exactly this and nothing else):\n{state['spec']}\n\nCODE (current files, complete; you have no read tools and do not need them):\n{code_pack(rc.project_id, worktree, state['paths'], 60_000)}\n\nThe line numbers are not part of the files, so never put them in a search. Include a real test that fails without the change when the repo has a test setup.\n\nRepeat of the TASK: {state['spec'][:600]}"
    if state.get("failure"):
        message += f"\n\nThe last attempt broke these tests. Fix only this; do not touch unrelated code or tests.\nCurrent diff:\n{git.diff(worktree)[:8000]}\n\nFailures:\n{state['failure'][:5000]}"
    if state.get("feedback"):
        message += f"\n\nReviewer feedback on the last diff:\n{state['feedback']}\nCurrent diff:\n{git.diff(worktree)[:8000]}"
    finding_file = state.get("finding_file")

    def finding_scope(edit: Edit) -> str | None:
        """A finding's fix may change only that file and tests, so the agent cannot drift to another bug."""
        path = edit.path.replace("\\", "/")
        name = path.rsplit("/", 1)[-1]
        is_test = path.startswith("tests/") or name.startswith("test_")
        if finding_file and path != finding_file and not is_test:
            return f"This task may only change {finding_file} and test files. Fix {finding_file}."
        if not safe_path(worktree, path).exists() and Path(path).suffix.lower() not in {*scan.LANGUAGES, ".json", ".yaml", ".yml", ".toml", ".md"}:
            return f"Refused new file {path}: only source, test, and configuration files belong in this change."
        return None

    call = AgentCall(rc.run_id, rc.project_id, agent)
    before = git.diff(worktree)
    summary, prompt, paths = "", message, state["paths"]
    for _ in range(3):
        result = await call.typed(prompt, ChangeSet)
        summary = result.summary or summary
        applied, refused = await asyncio.to_thread(guarded_apply, worktree, result.edits, finding_scope)
        rc.log(f"Applied {applied or 'no edits'}" + (f"; refused {refused}" if refused else ""), kind="warning" if refused else "artifact")
        paths = [*paths, *[p for p in applied if p not in paths]]
        gaps = spec_gaps(worktree, state)
        changed = git.diff(worktree) != before
        if changed and not refused and not gaps:
            break
        prompt = f"Not finished. Refused edits: {refused or 'none'}. Missing: {gaps or ('no file changed yet' if not changed else 'nothing')}. Send only the remaining edits for this task: {state['spec'][:600]}\n\nCURRENT FILES:\n{code_pack(rc.project_id, worktree, paths, 40_000)}"
    if git.diff(worktree) == before and not state.get("attempt"):
        raise RuntimeError("The agent finished without changing any file")
    # on a retry, keeping the earlier edits is valid: a person then reviews them with the honest failing verdict
    if finding_file and finding_file not in git.run(["diff", "--name-only"], cwd=worktree):
        raise RuntimeError(f"The agent did not change {finding_file}, the file with the finding")
    rc.log(f"Changes applied: {summary[:300]}", kind="artifact")
    return {"summary": summary[:1000], "test_target": "", "attempt": state.get("attempt", 0) + 1, "feedback": "", "paths": state["paths"]}


async def change_verify(rc: RunContext, state: dict) -> dict:
    worktree = Path(state["worktree"])
    analysis = await asyncio.to_thread(_rescan, worktree)
    results = []
    for runner in execution.choose_runners(analysis):
        result = await asyncio.to_thread(execution.run_suite, runner, worktree, state.get("test_target") or ("." if runner == "pytest" else ""), worktree.parent / f"{rc.run_id}-results")
        results.append(result)
        rc.log(f"{runner}: {result['passed']} passed, {result['failed']} failed", {k: result[k] for k in ("exit_code", "reason")}, "test")
    outcome = execution.compare_to_baseline(results, state.get("baseline", {}))
    rc.log(f"Verdict {outcome['verdict']}. {outcome['reason']}".strip(), {"new_failures": [c["name"] for c in outcome["new_failures"]][:20]}, "test")
    suites = [{k: r.get(k) for k in ("runner", "verdict", "passed", "failed", "skipped", "exit_code", "reason")} for r in results]
    gaps = spec_gaps(worktree, state)
    if gaps and outcome["verdict"] in {"PASS", "NO NEW FAILURES"}:
        outcome |= {"verdict": "INCOMPLETE", "reason": "; ".join(gaps)}
    update = {"verification": {"changed_assertions": _changed_assertions(worktree), "verdict": outcome["verdict"], "reason": outcome["reason"], "new_failures": len(outcome["new_failures"]), "existing_failures": outcome["existing_failures"], "suites": suites}, "failure": ""}
    # retry only what the change broke; environment failures are not the agent's to fix
    # failing test files go first in paths, because code_pack drops whatever is over its limit
    if outcome["verdict"] == "FAIL" and state["attempt"] < 3:
        update |= {"failure": "\n".join(f"{c['classname']}::{c['name']}: {c['message'][:800]}" for c in outcome["new_failures"][:10]), "_next": "implement", "paths": list(dict.fromkeys([*_failing_files(worktree, outcome["new_failures"]), *state["paths"]]))}
    return update


def _changed_assertions(worktree: Path) -> list[str]:
    """Existing assertions this change removed or altered. Editing a test can hide a bug, so the reviewer must see these."""
    return [line[1:].strip() for line in git.diff(worktree).splitlines() if line.startswith("-") and not line.startswith("---") and execution.ASSERTION.search(line)][:20]


def _failing_files(worktree: Path, cases: list[dict]) -> list[str]:
    """Test files behind failures, so a retry can read them. ponytail: pytest class names only; other runners keep the files already chosen."""
    return [f for f in scan.tree(worktree) if f.endswith(".py") and any(c["classname"].startswith(f[:-3].replace("/", ".")) for c in cases)][:4]


def _rescan(worktree: Path) -> dict:
    from backend.repos.scan import analyze

    return analyze(worktree)


def change_gate(rc: RunContext, state: dict):
    worktree = Path(state["worktree"])
    patch = git.diff(worktree)
    doc = documents.create(rc.project_id, "patch", state["title"], patch or "(no changes)", f"agent:{state.get('kind', 'feature')}", note=state.get("summary", ""), run_id=rc.run_id, data=state.get("verification"))
    state["patch_doc"] = doc["id"]
    verdict = state["verification"]["verdict"]
    can_pr = bool((repo := ingest.get(rc.project_id)) and repo["credential_id"] and github.parse_slug(repo["url"]))
    return {"title": f"Review change: {state['title']}", "summary": f"Test verdict {verdict}. {state.get('summary', '')}",
            "payload": {"diff": patch[:60000], "patch_document": doc["id"], "branch": state["branch"], "verification": state["verification"], "can_open_pr": can_pr}}


async def change_deliver(rc: RunContext, state: dict, answer: dict) -> dict:
    worktree = Path(state["worktree"])
    commit = await asyncio.to_thread(git.commit_all, worktree, f"{state['title']}\n\n{state.get('summary', '')}\n\nApproved by {answer['by']} in Agentic QE Platform run {rc.run_id}")
    rc.log(f"Committed {commit[:10]} on {state['branch']}", kind="artifact")
    outcome = {"commit": commit}
    repo = ingest.get(rc.project_id)
    if answer.get("open_pr") and repo and repo["credential_id"]:
        slug = github.parse_slug(repo["url"])
        if slug:
            token = github.token_for(repo["credential_id"])
            await asyncio.to_thread(git.push, worktree, state["branch"], token)
            base = repo["ref"] or await asyncio.to_thread(git.run, ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], repo_dir(rc.project_id), None, 30, False)
            pr = await github.open_pr(token, slug[0], slug[1], state["branch"], (base or "main").removeprefix("origin/"), state["title"], f"{state.get('summary', '')}\n\nTest verdict: {state['verification']['verdict']}\nApproved by {answer['by']}.")
            outcome["pull_request"] = pr
            rc.log(f"Opened pull request {pr['url']}", pr, "artifact")
    return outcome


def change_definition() -> Definition:
    return Definition("change", [
        StageSpec("prepare", change_prepare, "Prepare branch", next="implement"),
        StageSpec("implement", change_implement, "Implement", next="verify"),
        StageSpec("verify", change_verify, "Run tests", approval=lambda rc, s: None if s.get("_next") else change_gate(rc, s), on_approved=change_deliver, on_rejected="implement", next="END"),
    ], routes={"verify": ["implement"]})


REGISTRY["change"] = change_definition
