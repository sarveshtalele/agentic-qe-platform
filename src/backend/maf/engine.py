"""Run manager over real MAF workflows: typed stages, HITL via request_info, file checkpoints, durable events.

Resume always rebuilds the workflow and restores the latest checkpoint, so an app restart between a gate
request and its decision behaves exactly like the normal path.
"""
from __future__ import annotations

import asyncio
import json
import logging
import traceback
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

from backend.config import CHECKPOINTS
from backend.core import gates, ledger
from backend.core.security import redact
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


def add_event(run_id: str, kind: str, stage: str, message: str, data: dict | None = None) -> None:
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        seq = con.execute("SELECT COALESCE(MAX(seq),0)+1 FROM run_events WHERE run_id=?", (run_id,)).fetchone()[0]
        con.execute("INSERT INTO run_events VALUES (?,?,?,?,?,?,?)", (run_id, seq, kind, stage, redact(message), json.dumps(data or {}, default=str), now()))


_stage_errors: dict[str, str] = {}


async def _safely(rc: RunContext, awaitable):
    """MAF reduces executor failures to the exception type, so the real message is kept for the run record."""
    try:
        return await awaitable
    except Exception as exc:
        _stage_errors[rc.run_id] = f"{rc.stage}: {exc}"
        rc.log(str(exc), kind="error")
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
    except Exception as exc:  # the failure is surfaced on the run, never swallowed
        traceback.print_exc()
        _finish(run_id, "failed", _stage_errors.pop(run_id, str(exc)))


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


async def start(project_id: str, workflow: str, payload: dict) -> dict:
    if workflow not in REGISTRY:
        raise ValueError(f"Unknown workflow {workflow}. Use one of: {', '.join(sorted(REGISTRY))}")
    llm_check = agent_module.llm.client  # fails early with a clear message when no model is configured
    llm_check()
    run_id = new_id("run")
    with db() as con:
        con.execute("INSERT INTO runs (id, project_id, workflow, status, input, started_at) VALUES (?,?,?,?,?,?)",
                    (run_id, project_id, workflow, "running", json.dumps(payload), now()))
    ledger.append(project_id, "user", "run.started", run_id, {"workflow": workflow})
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
    if approval["gate"] is not None:
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
    for approval in found["approvals"]:
        approval["payload"] = json.loads(approval["payload"])
    return found


def events(run_id: str, after: int = 0) -> list[dict]:
    with db() as con:
        items = rows(con.execute("SELECT * FROM run_events WHERE run_id=? AND seq>? ORDER BY seq", (run_id, after)))
    for item in items:
        item["data"] = json.loads(item["data"])
    return items


__all__ = ["StageSpec", "Definition", "FanOut", "RunContext", "REGISTRY", "start", "decide", "recover", "get", "events"]
