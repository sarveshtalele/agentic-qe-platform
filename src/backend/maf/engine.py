"""Run manager over real MAF workflows: typed stages, HITL via request_info, file checkpoints, durable events.

Resume always rebuilds the workflow and restores the latest checkpoint, so an app restart between a gate
request and its decision behaves exactly like the normal path.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import hashlib
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from agent_framework import (
    Executor,
    FileCheckpointStorage,
    Workflow,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    response_handler,
)

from backend.config import CHECKPOINTS, RUN_TOKEN_LIMIT, RUNS
from backend.core import auth, gates, ledger
from backend.core.errors import AllowanceError, classify, stack_of
from backend.core.security import redact, safe_path
from backend.db import db, new_id, now, row, rows
from backend.maf import runtime as agent_module

# rework loops back to the same stage on purpose, guarded by routing conditions and max_iterations
logging.getLogger("agent_framework._workflows._validation").setLevel(logging.ERROR)


@dataclass
class ApprovalRequest:
    """Payload MAF carries through request_info and checkpoints. State is JSON so it stays portable."""

    stage: str = ""
    gate: int = -1  # -1 means a run-level approval that is not a numbered quality gate
    title: str = ""
    summary: str = ""
    payload: str = "{}"
    state: str = "{}"


@dataclass
class StageSpec:
    id: str
    fn: Callable[["RunContext", dict], Awaitable[dict]]
    label: str = ""
    # returns a gate request ({gate, title, summary, payload}) or None to continue without stopping
    approval: Callable[["RunContext", dict], dict | None] | None = None
    on_approved: Callable[["RunContext", dict, dict], Awaitable[dict]] | None = None
    on_rejected: str | None = None  # stage to loop back to with reviewer feedback; None ends the run
    next: str | None = None
    forward: bool = False  # sends to fan-out edges instead of naming a single next stage


class RunContext:
    def __init__(self, run_id: str, project_id: str, stage: str = ""):
        self.run_id, self.project_id, self.stage = run_id, project_id, stage

    def log(self, message: str, data: dict | None = None, kind: str = "log") -> None:
        add_event(self.run_id, kind, self.stage, message, data)

    def emit(self, kind: str, message: str, data: dict | None = None) -> None:
        add_event(self.run_id, kind, self.stage, message, data)

    def _part(self, key: str):
        return safe_path(RUNS / self.run_id, f"parts/{self.stage}/{key}.json", for_write=True)

    def keep(self, key: str, data) -> None:
        """Save one finished batch as it completes, so a retry of this stage repeats only what is missing."""
        path = self._part(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(redact(json.dumps(data, default=str)), encoding="utf-8")

    def kept(self, key: str):
        path = self._part(key)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None  # nothing saved, or unreadable: the batch is simply done again

    def clear_parts(self) -> None:
        shutil.rmtree(safe_path(RUNS / self.run_id, f"parts/{self.stage}", for_write=True), ignore_errors=True)

    def earlier_failures(self) -> int:
        """Failures of this stage since it last finished, so an old failure does not shorten a later rework."""
        with db() as con:
            return con.execute(
                """SELECT COUNT(*) FROM run_events WHERE run_id=? AND stage=? AND type='error'
                   AND seq > COALESCE((SELECT MAX(seq) FROM run_events WHERE run_id=? AND stage=? AND type='stage_end'), 0)""",
                (self.run_id, self.stage, self.run_id, self.stage)).fetchone()[0]


def part_key(*inputs) -> str:
    """Names a batch by what it was asked, so a changed request never reuses an old result."""
    return hashlib.sha256(json.dumps(inputs, default=str, sort_keys=True).encode()).hexdigest()[:16]


def add_event(run_id: str, kind: str, stage: str, message: str, data: dict | None = None) -> None:
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        seq = con.execute("SELECT COALESCE(MAX(seq),0)+1 FROM run_events WHERE run_id=?", (run_id,)).fetchone()[0]
        con.execute("INSERT INTO run_events VALUES (?,?,?,?,?,?,?)", (run_id, seq, kind, stage, redact(message), json.dumps(data or {}, default=str), now()))


_failures: dict[str, dict] = {}
log = logging.getLogger("aqe.engine")


def record_failure(run_id: str, stage: str, exc: BaseException) -> dict:
    """One diagnostic row per failure, redacted. The whole rejected reply goes to a file under the run, never into a column."""
    error = classify(exc)
    d = error.detail
    error_id = new_id("err")
    reply_file = ""
    if d.get("reply"):
        reply_file = f"failures/{error_id}-reply.txt"
        path = safe_path(RUNS / run_id, reply_file, for_write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(redact(str(d["reply"])), encoding="utf-8")
    failure = {
        "id": error_id, "run_id": run_id, "code": error.code, "message": redact(error.message), "action": error.action, "retryable": int(error.retryable), "stage": stage,
        "agent": d.get("agent", ""), "attempt": d.get("attempt"), "prompt_ref": d.get("prompt_ref", ""), "model": d.get("model", ""), "finish_reason": d.get("finish_reason", ""),
        "tokens_in": d.get("tokens_in"), "tokens_out": d.get("tokens_out"), "duration_ms": d.get("duration_ms"), "parse_pos": d.get("parse_pos"),
        "parse_context": redact(d.get("parse_context", "")), "technical": redact(str(d.get("technical", "")))[:2000], "reply_file": reply_file,
        "stack": stack_of(exc), "provider_status": d.get("provider_status"), "provider_request_id": redact(str(d.get("provider_request_id", ""))), "created_at": now(),
    }
    with db() as con:
        con.execute(f"INSERT INTO run_failures ({', '.join(failure)}) VALUES ({', '.join('?' * len(failure))})", tuple(failure.values()))
    log.error("run %s stage %s failed: %s error_id=%s %s", run_id, stage, error.code, error_id, failure["message"],
              extra={"fields": {"run_id": run_id, "stage": stage, "agent": failure["agent"], "error_id": error_id, "code": error.code}})
    return failure


async def _safely(rc: RunContext, awaitable):
    """MAF reduces executor failures to the exception type, so the real failure is recorded here and handed to _guarded."""
    try:
        return await awaitable
    except Exception as exc:
        failure = _failures[rc.run_id] = record_failure(rc.run_id, rc.stage, exc)
        rc.log(f"{failure['code']} {failure['message']}", {"error_id": failure["id"], "code": failure["code"]}, kind="error")
        raise


class Stage(Executor):
    """One workflow step as a MAF executor. Routing lives in the message state, edges read it."""

    def __init__(self, spec: StageSpec, run_id: str, project_id: str):
        super().__init__(id=spec.id)
        self.spec, self.run_id, self.project_id = spec, run_id, project_id

    def _ctx(self) -> RunContext:
        rc = RunContext(self.run_id, self.project_id, self.spec.id)
        agent_module.set_emitter(rc.emit)
        return rc

    async def _advance(self, state: dict, ctx: WorkflowContext) -> None:
        with db() as con:
            con.execute("UPDATE runs SET state=? WHERE id=?", (json.dumps(_public_state(state), default=str), self.run_id))
        target = state.pop("_next", None) or self.spec.next
        if self.spec.forward:
            await ctx.send_message(state)
        elif target == "END" or target is None:
            await ctx.yield_output(json.dumps(state, default=str))
        else:
            await ctx.send_message({**state, "_to": target})

    @handler
    async def run(self, state: dict, ctx: WorkflowContext[dict, str]) -> None:
        rc = self._ctx()
        rc.log(f"Started {self.spec.label or self.spec.id}", kind="stage_start")
        state = {**state, **(await _safely(rc, self.spec.fn(rc, state)) or {})}
        if not state.get("partial"):  # a partial result keeps its batches for the rework that follows
            rc.clear_parts()
        state.pop("_to", None)
        rc.log(f"Finished {self.spec.label or self.spec.id}", kind="stage_end")
        request = self.spec.approval(rc, state) if self.spec.approval else None
        if request:
            await ctx.request_info(
                ApprovalRequest(stage=self.spec.id, gate=request.get("gate", -1), title=request["title"], summary=request["summary"],
                                payload=json.dumps(request.get("payload", {}), default=str), state=json.dumps(state, default=str)),
                str,
            )
            return
        await self._advance(state, ctx)

    @response_handler
    async def decided(self, original: ApprovalRequest, decision: str, ctx: WorkflowContext[dict, str]) -> None:
        rc = self._ctx()
        answer = json.loads(decision)
        state = json.loads(original.state)
        if answer["approved"]:
            rc.log(f"Approved by {answer['by']}", {"feedback": answer.get("feedback", "")}, "approved")
            if self.spec.on_approved:
                state = {**state, **(await _safely(rc, self.spec.on_approved(rc, state, answer)) or {})}
            state.pop("feedback", None)
            await self._advance(state, ctx)
            return
        rc.log(f"Rejected by {answer['by']}: {answer.get('feedback', '')}", kind="rejected")
        if self.spec.on_rejected:
            await ctx.send_message({**state, "feedback": answer.get("feedback", ""), "_to": self.spec.on_rejected})
        else:
            await ctx.yield_output(json.dumps({**state, "rejected": True}, default=str))


class Merge(Executor):
    """Fan-in target. MAF delivers a list once every fan-out branch has finished."""

    def __init__(self, id: str, fn, next_stage: str | None, run_id: str, project_id: str):
        super().__init__(id=id)
        self.fn, self.next_stage, self.run_id, self.project_id = fn, next_stage, run_id, project_id

    @handler
    async def merge(self, branches: list[dict], ctx: WorkflowContext[dict, str]) -> None:
        rc = RunContext(self.run_id, self.project_id, self.id)
        state = await _safely(rc, self.fn(rc, branches))
        if self.next_stage:
            await ctx.send_message({**state, "_to": self.next_stage})
        else:
            await ctx.yield_output(json.dumps(state, default=str))


@dataclass
class FanOut:
    source: str
    branches: list[str]
    merge_id: str
    merge_fn: Callable
    next: str | None = None


@dataclass
class Definition:
    name: str
    stages: list[StageSpec]
    fan_out: FanOut | None = None
    routes: dict[str, list[str]] = field(default_factory=dict)  # extra dynamic targets, e.g. review to draft


def _public_state(state: dict) -> dict:
    return {k: v for k, v in state.items() if not k.startswith("_") and k not in {"context", "source_text"}}


def compile_workflow(definition: Definition, run_id: str, project_id: str, storage) -> Workflow:
    stages = {s.id: Stage(s, run_id, project_id) for s in definition.stages}
    first = stages[definition.stages[0].id]
    builder = WorkflowBuilder(start_executor=first, name=definition.name, checkpoint_storage=storage, max_iterations=120)

    def route(target: str):
        return lambda state: isinstance(state, dict) and state.get("_to") == target

    edges: set[tuple[str, str]] = set()
    fan = definition.fan_out
    for spec in definition.stages:
        targets = set(definition.routes.get(spec.id, []))
        if spec.next and spec.next != "END":
            targets.add(spec.next)
        if spec.on_rejected:
            targets.add(spec.on_rejected)
        for target in targets:
            if fan and spec.id in fan.branches:
                continue
            if (spec.id, target) not in edges:
                builder.add_edge(stages[spec.id], stages[target], condition=route(target))
                edges.add((spec.id, target))
    if fan:
        merge = Merge(fan.merge_id, fan.merge_fn, fan.next, run_id, project_id)
        builder.add_fan_out_edges(stages[fan.source], [stages[b] for b in fan.branches])
        builder.add_fan_in_edges([stages[b] for b in fan.branches], merge)
        if fan.next:
            builder.add_edge(merge, stages[fan.next], condition=route(fan.next))
    return builder.build()


REGISTRY: dict[str, Callable[[], Definition]] = {}
_tasks: set[asyncio.Task] = set()
_active: dict[str, asyncio.Task] = {}


def _storage(run_id: str) -> FileCheckpointStorage:
    folder = CHECKPOINTS / run_id
    folder.mkdir(parents=True, exist_ok=True)
    return FileCheckpointStorage(folder, allowed_checkpoint_types=["backend.maf.engine:ApprovalRequest"])


async def _consume(run_id: str, project_id: str, stream) -> None:
    pending: list = []
    output = None
    async for event in stream:
        if event.type == "request_info":
            pending.append(event)
        elif event.type == "output":
            output = event.data
        elif event.type == "failed":
            raise RuntimeError(str(event.details))
    if pending:
        for event in pending:
            _register_approval(run_id, project_id, event)
        _finish(run_id, "waiting_approval")
    else:
        state = json.loads(output) if isinstance(output, str) else {}
        with db() as con:
            con.execute("UPDATE runs SET state=? WHERE id=?", (json.dumps(_public_state(state), default=str), run_id))
        _finish(run_id, "rejected" if state.get("rejected") else "completed")


def _register_approval(run_id: str, project_id: str, event) -> None:
    data: ApprovalRequest = event.data
    with db() as con:
        con.execute(
            "INSERT OR REPLACE INTO approvals (id, run_id, project_id, gate, title, summary, payload, status, created_at) VALUES (?,?,?,?,?,?,?,'pending',?)",
            (event.request_id, run_id, project_id, data.gate if data.gate >= 0 else None, data.title, data.summary, data.payload, now()),
        )
    add_event(run_id, "approval_required", data.stage, data.title, {"approval_id": event.request_id, "gate": data.gate})


def _finish(run_id: str, status: str, error: str = "") -> None:
    terminal = status in {"completed", "failed", "rejected", "interrupted", "cancelled"}
    with db() as con:
        con.execute("UPDATE runs SET status=?, error=?, ended_at=? WHERE id=?", (status, redact(error), now() if terminal else None, run_id))
        project_id = con.execute("SELECT project_id FROM runs WHERE id=?", (run_id,)).fetchone()["project_id"]
    add_event(run_id, "status", "", status, {"error": redact(error)} if error else None)
    ledger.append(project_id, "system", f"run.{status}", run_id, {"error": redact(error)[:400]} if error else {})


async def _guarded(run_id: str, project_id: str, stream) -> None:
    try:
        await _consume(run_id, project_id, stream)
    except asyncio.CancelledError:
        _finish(run_id, "cancelled")
        raise
    except Exception as exc:  # recorded in run_failures with a redacted stack, then shown on the run
        failure = _failures.pop(run_id, None) or record_failure(run_id, "", exc)
        _finish(run_id, "failed", f"{failure['stage']}: {failure['message']}" if failure["stage"] else failure["message"])


def _spawn(run_id: str, coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    _active[run_id] = task
    task.add_done_callback(_tasks.discard)
    return task


def cancel(run_id: str) -> dict:
    """Stop a running run, or close one waiting on a human so its approval can no longer be used."""
    run = get(run_id)
    task = _active.get(run_id)
    if task and not task.done():
        task.cancel()
    elif run["status"] == "waiting_approval":
        with db() as con:
            con.execute("UPDATE approvals SET status='cancelled' WHERE run_id=? AND status='pending'", (run_id,))
        _finish(run_id, "cancelled")
    else:
        raise ValueError(f"Run is already {run['status']}")
    return get(run_id)


ACTIVE = ("running", "waiting_approval")  # a waiting run still holds its worktree, so it keeps the slot


class RunActive(ValueError):
    """Another run of this kind is in progress in this project. Names it, and where to open it."""

    def __init__(self, project_id: str, workflow: str):
        with db() as con:
            found = row(con.execute("SELECT id, status, started_at FROM runs WHERE project_id=? AND workflow=? AND status IN ('running','waiting_approval') ORDER BY started_at LIMIT 1", (project_id, workflow))) or {}
        self.run_id = found.get("id", "")
        super().__init__(f"A {workflow} run is already {found.get('status', 'in progress').replace('_', ' ')} in this project: {self.run_id}, started {found.get('started_at', '')}. "
                         f"Open it at /projects/{project_id}/runs/{self.run_id}, and finish or cancel it before starting another.")


async def start(project_id: str, workflow: str, payload: dict, model: str = "") -> dict:
    if workflow not in REGISTRY:
        raise ValueError(f"Unknown workflow {workflow}. Use one of: {', '.join(sorted(REGISTRY))}")
    llm_check = agent_module.llm.client  # fails early with a clear message when no model is configured
    llm_check()
    starter = (auth.current_user.get() or {}).get("id")
    auth.model_for(project_id, "", None, starter, model)  # refuses at once a model this account may not use, or an account with none
    auth.check_allowance(project_id, starter)
    run_id = new_id("run")
    with db() as con:  # one statement inside one write transaction decides who wins, so two starts cannot both take the slot
        con.execute("BEGIN IMMEDIATE")
        claimed = con.execute(
            """INSERT INTO runs (id, project_id, workflow, status, input, started_at, user_id, model)
               SELECT ?,?,?,?,?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM runs WHERE project_id=? AND workflow=? AND status IN ('running','waiting_approval'))""",
            (run_id, project_id, workflow, "running", json.dumps(payload), now(), starter, model.strip(), project_id, workflow)).rowcount
    if not claimed:
        raise RunActive(project_id, workflow)
    ledger.append(project_id, starter or "system", "run.started", run_id, {"workflow": workflow, "model": model.strip()})
    add_event(run_id, "status", "", "running")
    storage = _storage(run_id)
    compiled = compile_workflow(REGISTRY[workflow](), run_id, project_id, storage)
    state = {**payload, "project_id": project_id, "run_id": run_id, "_to": ""}
    _spawn(run_id, _guarded(run_id, project_id, compiled.run(state, stream=True)))
    return get(run_id)


async def decide(approval_id: str, approved: bool, by: str, feedback: str = "", extra: dict | None = None) -> dict:
    if not by.strip():
        raise ValueError("A named human signer is required")
    with db() as con:
        approval = row(con.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)))
    if not approval:
        raise KeyError(approval_id)
    if approval["status"] != "pending":
        raise ValueError(f"Approval already {approval['status']}")
    if approved and (partial := json.loads(approval["payload"]).get("partial")):
        raise ValueError(f"This result is partial and cannot be approved. Missing: {partial['missing']}. Send it back, or approve nothing and retry after fixing the cause.")
    if approval["gate"] is not None:
        auth.require_gate_signer(approval["project_id"], approval["gate"])  # the account's role, not a name in the request
        gates.decide(approval["project_id"], approval["gate"], approved, by, feedback, approval["run_id"])
    else:
        ledger.append(approval["project_id"], by, "approval." + ("approved" if approved else "rejected"), approval["title"], {"run_id": approval["run_id"], "feedback": feedback})
    with db() as con:
        con.execute("UPDATE approvals SET status=?, decided_by=?, feedback=?, decided_at=? WHERE id=?",
                    ("approved" if approved else "rejected", by, feedback, now(), approval_id))
        run = row(con.execute("SELECT * FROM runs WHERE id=?", (approval["run_id"],)))
        con.execute("UPDATE runs SET status='running' WHERE id=?", (run["id"],))
    response = json.dumps({"approved": approved, "by": by, "feedback": feedback, **(extra or {})})
    _spawn(run["id"], _guarded(run["id"], run["project_id"], _resume(run, approval_id, response)))
    return get(run["id"])


async def retry(run_id: str) -> dict:
    """Resume a failed or interrupted run from its latest checkpoint. Finished batches are kept by the stage itself."""
    run = get(run_id)
    agent_module.llm.client()  # a missing model fails now, with its own message
    auth.check_allowance(run["project_id"], auth.acting_user(run["project_id"], run_id))
    if run["tokens_in"] + run["tokens_out"] >= RUN_TOKEN_LIMIT:
        raise AllowanceError(f"Run stopped: it used {run['tokens_in'] + run['tokens_out']} tokens, over the limit of {RUN_TOKEN_LIMIT}.", action="Raise ATLAS_RUN_TOKEN_LIMIT, or ask your administrator, then retry.")
    with db() as con:  # one statement decides who wins, so two retries cannot both start, nor can a retry take a slot a newer run holds
        con.execute("BEGIN IMMEDIATE")
        claimed = con.execute(
            """UPDATE runs SET status='running', error='', ended_at=NULL WHERE id=? AND status IN ('failed','interrupted')
               AND NOT EXISTS (SELECT 1 FROM runs o WHERE o.project_id=runs.project_id AND o.workflow=runs.workflow AND o.status IN ('running','waiting_approval'))""", (run_id,)).rowcount
    if not claimed:
        if get(run_id)["status"] in {"failed", "interrupted"}:
            raise RunActive(run["project_id"], run["workflow"])
        raise ValueError(f"Run is {get(run_id)['status']}; only a failed or interrupted run can be retried")
    ledger.append(run["project_id"], (auth.current_user.get() or {}).get("id", "system"), "run.retried", run_id, {"after": run["status"]})
    add_event(run_id, "status", "", "running", {"retry": True})
    _spawn(run_id, _guarded(run_id, run["project_id"], _rerun(run)))
    return get(run_id)


async def _rerun(run: dict):
    storage = _storage(run["id"])
    workflow = compile_workflow(REGISTRY[run["workflow"]](), run["id"], run["project_id"], storage)
    latest = await storage.get_latest(workflow_name=workflow.name)
    if latest is None:  # it failed before the first checkpoint, so it starts again from its input
        stream = workflow.run({**run["input"], "project_id": run["project_id"], "run_id": run["id"], "_to": ""}, stream=True)
    else:
        stream = workflow.run(checkpoint_id=latest.checkpoint_id, checkpoint_storage=storage, stream=True)
    async for event in stream:
        yield event


async def _resume(run: dict, approval_id: str, response: str):
    storage = _storage(run["id"])
    workflow = compile_workflow(REGISTRY[run["workflow"]](), run["id"], run["project_id"], storage)
    latest = await storage.get_latest(workflow_name=workflow.name)
    if latest is None:
        raise RuntimeError("No checkpoint found to resume this run")
    async for _ in workflow.run(checkpoint_id=latest.checkpoint_id, checkpoint_storage=storage, stream=True):
        pass  # replays the pending request so the response below has something to answer
    async for event in workflow.run(responses={approval_id: response}, stream=True):
        yield event


def recover() -> None:
    """Tasks do not survive a restart. Waiting runs are safe on their checkpoint; running ones are not."""
    with db() as con:
        for item in rows(con.execute("SELECT id FROM runs WHERE status='running'")):
            con.execute("UPDATE runs SET status='interrupted', error='Application restarted during this run', ended_at=? WHERE id=?", (now(), item["id"]))


def get(run_id: str) -> dict:
    with db() as con:
        found = row(con.execute("SELECT * FROM runs WHERE id=?", (run_id,)))
        if not found:
            raise KeyError(run_id)
        found["approvals"] = rows(con.execute("SELECT * FROM approvals WHERE run_id=? ORDER BY created_at", (run_id,)))
    for key in ("input", "state"):
        found[key] = json.loads(found[key])
    with db() as con:
        found["failure"] = row(con.execute("SELECT * FROM run_failures WHERE run_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1", (run_id,)))
    for approval in found["approvals"]:
        approval["payload"] = json.loads(approval["payload"])
    return found


def events(run_id: str, after: int = 0) -> list[dict]:
    with db() as con:
        items = rows(con.execute("SELECT * FROM run_events WHERE run_id=? AND seq>? ORDER BY seq", (run_id, after)))
    for item in items:
        item["data"] = json.loads(item["data"])
    return items


__all__ = ["RunActive", "StageSpec", "Definition", "FanOut", "RunContext", "REGISTRY", "start", "decide", "retry", "recover", "get", "events", "part_key"]
