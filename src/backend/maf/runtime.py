"""Agent construction on the real Microsoft Agent Framework, with middleware and JSON validation."""
from __future__ import annotations

import asyncio
import json
import re
import time
import weakref
from contextvars import ContextVar
from pathlib import Path
from typing import Callable, TypeVar

from agent_framework import (
    Agent,
    ContextProvider,
    FunctionInvocationContext,
    SlidingWindowStrategy,
    function_middleware,
)
from pydantic import BaseModel, ValidationError

from backend.config import MODEL_CONCURRENCY, MODEL_NO_CACHE, RUN_TOKEN_LIMIT
from backend.core import auth, documents, ledger, prompts
from backend.core.errors import AllowanceError, ModelJsonError, ModelSchemaError, ModelTruncated
from backend.core.security import redact
from backend.db import db, new_id, now, rows
from backend.maf import governance, llm, observability, tools
from backend.repos import ingest

T = TypeVar("T", bound=BaseModel)

CHAT_AGENTS = {key: policy.name for key, policy in governance.POLICIES.items() if policy.chat_tools is not None}
_emit: ContextVar[Callable | None] = ContextVar("agent_emit", default=None)


_gates: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _model_gate() -> asyncio.Semaphore:
    """Bound concurrent model calls for the process, so parallel workflows queue instead of exhausting a small server."""
    loop = asyncio.get_running_loop()
    return _gates.setdefault(loop, asyncio.Semaphore(MODEL_CONCURRENCY))


def set_emitter(callback: Callable | None) -> None:
    """Workflow runs bind this so tool activity lands on the live run timeline."""
    _emit.set(callback)


class ProjectContext(ContextProvider):
    """MAF context provider: injects project facts, repo summary, memories, and the document index."""

    def __init__(self, project_id: str, full: bool = True):
        super().__init__("project-context")
        self.project_id, self.full = project_id, full

    async def before_run(self, *, agent, session, context, state) -> None:
        with db() as con:
            project = dict(con.execute("SELECT name, description FROM projects WHERE id=?", (self.project_id,)).fetchone())
            memories = rows(con.execute("SELECT content FROM memories WHERE project_id=? ORDER BY created_at DESC LIMIT 25", (self.project_id,)))
        repo = ingest.get(self.project_id)
        parts = [f"Project: {project['name']}. {project['description']}".strip()]
        if repo:
            a = repo["analysis"]
            parts.append(f"Repository ({repo['kind']}: {repo['url']}, commit {repo['commit_sha'][:10]}): languages {a['languages']}, frameworks {a['frameworks']}, test runners {a['test_runners']}, {a['total_files']} files, {a['test_file_count']} test files.")
        else:
            parts.append("No repository connected.")
        # workflow agents get a precise task; a document list only tempts them to wander off it
        docs = documents.list_for(self.project_id)[:30] if self.full else []
        if docs:
            parts.append("Saved documents: " + "; ".join(f"{d['id']} [{d['kind']}] {d['title']} v{d['current_version']} ({d['status']})" for d in docs))
        if memories and self.full:
            parts.append("Remembered facts for this project:\n" + "\n".join(f"- {m['content']}" for m in memories))
        context.extend_instructions(self.source_id, "\n".join(parts))


def tool_audit(agent_key: str, project_id: str, run_id: str | None, source: str):
    """Every tool call is timed, filtered, shown on the run timeline, and stored for observability, redacted."""

    @function_middleware
    async def audit(context: FunctionInvocationContext, call_next) -> None:
        started = time.perf_counter()
        name = context.function.name
        args = context.arguments.model_dump() if isinstance(context.arguments, BaseModel) else dict(context.arguments)
        failure = ""
        try:
            await call_next()
            context.result = governance.guard_tool_result(agent_key, name, context.result, project_id, run_id)
        except Exception as exc:
            failure = str(exc) or type(exc).__name__
            raise
        finally:
            took = int((time.perf_counter() - started) * 1000)
            observability.record_tool(agent_key, project_id, run_id, source, name, args, took, failure)
            emit = _emit.get()
            if emit:
                emit("tool", f"{name} {redact(json.dumps(args, default=str))[:180]}", {"tool": name, "ms": took})

    return audit


def build(agent_key: str, project_id: str, tool_list=None, *, root=None, chat: bool = False, run_id: str | None = None, source: str = "workflow") -> Agent:
    governance.require_enabled(agent_key)
    auth.check_allowance(project_id)
    instructions = prompts.active(agent_key)["body"]
    # deny by default: a tool reaches the model only if this agent's policy lists it
    tool_list = governance.allowed(agent_key, tools.repo_tools(project_id, root) + list(tool_list or []), chat)
    options = {"max_tokens": governance.token_limit(agent_key)}
    if MODEL_NO_CACHE:  # LiteLLM's proxy cache would answer a retried prompt with the same bad reply
        options["extra_body"] = {"cache": {"no-cache": True}}
    middleware = [tool_audit(agent_key, project_id, run_id, source), governance.telemetry(agent_key, project_id, run_id, source)]
    providers = [ProjectContext(project_id, full=chat)]
    return Agent(
        client=llm.client(auth.model_for(project_id)), name=agent_key, instructions=instructions, tools=tool_list, context_providers=providers, middleware=middleware,
        compaction_strategy=SlidingWindowStrategy(keep_last_groups=30), default_options=options,
    )


def _strip_tool_markup(text: str) -> str:
    """Some models write tool syntax as text when tools are switched off for the final answer."""
    return re.sub(r"<[｜|]DSML[｜|].*", "", text, flags=re.S).strip()


_LENIENT = json.JSONDecoder(strict=False)  # models put raw line breaks inside strings
_BAD_ESCAPE = re.compile(r'\\(?!["\\/bfnrtu])')


def _decode(text: str, start: int):
    try:
        return _LENIENT.raw_decode(text, start)[0]
    except json.JSONDecodeError:
        return _LENIENT.raw_decode(_BAD_ESCAPE.sub(r"\\\\", text[start:]))[0]  # paths and regexes often carry a lone backslash


class ReplyError(ValueError):
    """Why a reply gave no usable JSON. kind is "json" when it is not JSON at all and "shape" when it is JSON of the wrong shape."""

    def __init__(self, message: str, pos: int | None = None, kind: str = "json"):
        super().__init__(message)
        self.pos, self.kind = pos, kind


_LOOKS_LIKE_JSON = re.compile(r'[\[{]\s*(?:["\[{}\]]|$)')  # prose brackets such as [FR-001] or {note} do not match


def _list_is_answer(text: str, start: int, required: tuple[str, ...]) -> bool:
    """A list that is the value of some other key belongs to a bigger object, so on its own it is a fragment."""
    key = re.search(r'"([^"\\]+)"\s*:\s*$', text[max(0, start - 200) : start])
    return key is None or key.group(1) in required


def extract_json(text: str, required: tuple[str, ...] = ()):
    """Return the first real object or list of objects. Prose can hold brackets like [FR-001].

    A reply that starts as JSON but does not parse is an error with the position. An inner fragment is never the
    answer: an object needs every required name, and a list must be the answer itself or the value of a required name.
    """
    broken = None
    seen = None
    for match in re.finditer(r"[\[{]", text):
        try:
            found = _decode(text, match.start())
        except json.JSONDecodeError as exc:
            if broken is None and _LOOKS_LIKE_JSON.match(text, match.start()):
                broken = (match.start() + exc.pos, exc.msg)
            continue
        if isinstance(found, dict) and found and all(name in found for name in required) and (required or not broken):
            return found
        if isinstance(found, list) and found and all(isinstance(item, dict) for item in found) and _list_is_answer(text, match.start(), required):
            return found
        if isinstance(found, dict) and found and seen is None:
            seen = found
    if broken:
        raise ReplyError(f"not valid JSON near character {broken[0]} of {len(text)}: {broken[1]}", broken[0])
    if seen is not None:
        raise ReplyError(f"valid JSON but without the required fields {[name for name in required if name not in seen]}; it has {sorted(seen)}", kind="shape")
    raise ReplyError("not JSON at all: no object or list was found")


def _fit_schema(found, schema: type[BaseModel]):
    """Some models send a bare list when the schema is one object holding a list, such as {"cases": [...]}."""
    if isinstance(found, list):
        names = [name for name, field in schema.model_fields.items() if field.is_required()]
        if len(names) != 1:
            raise ValueError("Expected one JSON object, not a list")
        return {names[0]: found}
    return found


def format_rule(schema: type[BaseModel]) -> str:
    return f"Reply with only one JSON object matching this schema:\n{json.dumps(schema.model_json_schema())}"


class AgentCall:
    """One agent bound to a run: tracks tokens and records which prompt version produced an output."""

    def __init__(self, run_id: str | None, project_id: str, agent_key: str, *, root: Path | None = None, tool_list=None, source: str = "workflow", chat: bool = False):
        self.run_id, self.project_id, self.key = run_id, project_id, agent_key
        self.agent = build(agent_key, project_id, tool_list, root=root, run_id=run_id, source=source, chat=chat)
        self.prompt_ref = prompts.ref(agent_key)
        # one session per call, so retries keep the conversation
        self.session = self.agent.create_session()
        self.has_tools = bool(self.agent.default_options.get("tools"))
        self.last_response = None
        self.last_call: dict = {}

    def _facts(self, **more) -> dict:
        """What a failure record needs to prove what was asked of which model."""
        return {"agent": self.key, "prompt_ref": self.prompt_ref, "model": str(getattr(self.agent.client, "model", "") or ""), **self.last_call, **more}

    async def text(self, message: str, tools_allowed: bool = True, *, cut_off_ok: bool = False) -> str:
        if self.run_id:
            with db() as con:
                used = con.execute("SELECT tokens_in+tokens_out FROM runs WHERE id=?", (self.run_id,)).fetchone()[0]
            if used >= RUN_TOKEN_LIMIT:
                raise AllowanceError(f"Run stopped: it used {used} tokens, over the limit of {RUN_TOKEN_LIMIT}.", action="Raise ATLAS_RUN_TOKEN_LIMIT, or ask your administrator, then retry the stage.", agent=self.key)
        auth.check_allowance(self.project_id)  # long runs can reach a limit part way through
        options = {"tool_choice": "none"} if not tools_allowed and self.has_tools else {}
        emit = _emit.get()
        if emit:
            emit("agent_call", f"{self.key} is working, waiting for the model", {"agent": self.key})
        message = governance.guard_text(self.key, message, "input", self.project_id, self.run_id)
        started = time.perf_counter()
        try:
            async with _model_gate():
                response = await self.agent.run(message, session=self.session, options=options)
        except Exception as exc:
            self.last_call = {"duration_ms": int((time.perf_counter() - started) * 1000)}
            error = governance.typed_error(self.key, exc, self.project_id, self.run_id)
            error.detail = {**self._facts(), **error.detail}
            raise error from exc
        self.last_response = response
        usage = response.usage_details or {}
        tokens = (usage.get("input_token_count") or 0) + (usage.get("output_token_count") or 0)
        self.last_call = {"tokens_in": usage.get("input_token_count") or 0, "tokens_out": usage.get("output_token_count") or 0, "duration_ms": int((time.perf_counter() - started) * 1000),
                          "finish_reason": str(getattr(response.finish_reason, "value", response.finish_reason) or "")}
        if self.run_id:
            with db() as con:
                con.execute("UPDATE runs SET tokens_in=tokens_in+?, tokens_out=tokens_out+? WHERE id=?",
                            (usage.get("input_token_count") or 0, usage.get("output_token_count") or 0, self.run_id))
        emit = _emit.get()
        if emit:
            emit("agent", f"{self.key} replied ({tokens} tokens)", {"agent": self.key, "tokens": tokens, "prompt": self.prompt_ref})
        ledger.append(self.project_id, f"agent:{self.key}", "agent.run", self.prompt_ref, {"run_id": self.run_id, "usage": dict(usage)})
        # response.text joins narration from every tool round; the answer is the last assistant message
        final = next((clean for m in reversed(response.messages) if m.role == "assistant" and (clean := _strip_tool_markup(m.text or "")).strip()), "")
        if not final.strip() and self.has_tools:
            final = "The agent finished without a written summary."
        if not final.strip():
            raise ModelJsonError(f"Agent {self.key} returned an empty reply", **self._facts())
        final = governance.guard_text(self.key, final.strip(), "output", self.project_id, self.run_id)
        if self.last_call["finish_reason"] == "length" and not cut_off_ok:
            raise ModelTruncated(f"Agent {self.key} was cut off at the token limit after {len(final)} characters.", reply=final, **self._facts())
        return final

    async def typed(self, message: str, schema: type[T], attempts: int = 3) -> T:
        """Ask for JSON matching schema, feeding validation errors back until it passes."""
        rule = format_rule(schema)
        prompt = f"{message}\n\n{rule}"
        failure = None
        for attempt in range(1, attempts + 1):
            # some models narrate after tool calls and never answer, so retries answer from what was already read
            reply = await self.text(prompt, tools_allowed=attempt == 1, cut_off_ok=True)
            facts = self._facts(attempt=attempt, reply=reply)
            # a cut-off reply can still hold a parseable fragment, so it never reaches the parser
            if facts["finish_reason"] == "length":
                failure = ModelTruncated(f"Agent {self.key} was cut off at the token limit after {len(reply)} characters.", **facts)
                prompt = f"Your reply was cut off at the token limit. Send the complete answer again with every text field much shorter. {rule}"
                continue
            try:
                required = tuple(name for name, field in schema.model_fields.items() if field.is_required())
                return schema.model_validate(_fit_schema(extract_json(reply, required), schema))
            except ReplyError as exc:
                where = {"parse_pos": exc.pos, "parse_context": redact(reply[max(0, exc.pos - 80) : exc.pos + 80])} if exc.pos is not None else {}
                failure = (ModelSchemaError if exc.kind == "shape" else ModelJsonError)(f"Agent {self.key} sent a reply that is {exc}.", technical=str(exc), **where, **facts)
                error = str(exc)
            except ValidationError as exc:
                fields = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'reply'}: {e['msg']}" for e in exc.errors()[:5])
                failure = ModelSchemaError(f"Agent {self.key} sent JSON that does not match {schema.__name__}: {fields}.", technical=str(exc)[:1500], **facts)
                error = str(exc)[:1500]
            except ValueError as exc:
                failure = ModelSchemaError(f"Agent {self.key} sent JSON of the wrong shape: {exc}.", technical=str(exc), **facts)
                error = str(exc)
            # same session, so the agent keeps what it read and only has to format its answer
            prompt = f"That reply was rejected: {error}\nUsing what you have already read, send the complete answer now. {rule}"
        raise failure


def memory_add(project_id: str, content: str, source: str) -> dict:
    memory = {"id": new_id("mem"), "content": redact(content.strip()), "source": source, "created_at": now()}
    with db() as con:
        con.execute("INSERT INTO memories VALUES (?,?,?,?,?)", (memory["id"], project_id, memory["content"], source, memory["created_at"]))
    return memory


__all__ = ["AgentCall", "CHAT_AGENTS", "build", "extract_json", "memory_add", "set_emitter", "Path"]
