# Microsoft Agent Framework guide

Page numbers refer to the official documentation PDF, `agent-framework.pdf`, in the project root.

Which MAF features Agentic QE Platform uses, where, and why. Packages: `agent-framework-core`, `agent-framework-openai`, `agent-framework-ag-ui`. Page numbers refer to `agent-framework.pdf`. Python APIs were confirmed against the installed package source, because many PDF samples are C#.

## Used

| MAF feature | API | File | How Agentic QE Platform uses it | PDF page |
|---|---|---|---|---|
| Model client | `OpenAIChatCompletionClient` | `src/backend/maf/llm.py` | One client for any OpenAI-compatible endpoint, from Settings or `.env` | 34, 439 |
| Tool loop limits | `function_invocation_configuration` (`max_iterations`, `max_function_calls`) | `src/backend/maf/llm.py` | 10 rounds and 30 calls instead of the default 100 rounds. MAF then forces a final answer with tools off | 277 |
| Chat middleware | `@chat_middleware` | `src/backend/maf/governance.py` `telemetry` | Before each model round it checks the account's token limits (`auth.check_allowance`), so a tool loop stops at a limit. After it, records tokens, latency, tool calls, status, the model, and the account for each round, streamed or not | 92 |
| Agents | `Agent` | `src/backend/maf/runtime.py` `build` | 13 specialists, each with a versioned prompt from the database | 6, 24 |
| Structured edits | `Agent` plus a pydantic schema | `src/backend/maf/workflows/edits.py` `ChangeSet`, `guarded_apply` | Edit agents get code in the message, have no tools, and reply with edits. Agentic QE Platform code applies them through path, secret, and scope guards | 323 |
| Function tools | `@tool` | `src/backend/maf/tools/` (one file per tool) | Repository, document, memory, and workflow tools, closed over one project | 8, 277 |
| Context providers | `ContextProvider.before_run` | `src/backend/maf/runtime.py` `ProjectContext` | Adds project facts, repo summary, document index, and memories to each run | 48 |
| Function middleware | `@function_middleware` | `src/backend/maf/runtime.py` `tool_audit` | Times and redacts each tool call, filters tool results for prompt injection, and puts the call on the run timeline | 81, 86 |
| Tool call records | `@function_middleware` | `src/backend/maf/runtime.py` `tool_audit`, `src/backend/maf/observability.py` | Stores every tool call, in workflows and chat, for the Observability page | 226 |
| Compaction | `SlidingWindowStrategy` | `src/backend/maf/runtime.py` `build` | Bounds long agent conversations | 63 |
| Workflows | `WorkflowBuilder`, `Executor`, `@handler` | `src/backend/maf/engine.py` `Stage`, `compile_workflow` | Each stage is an executor. Graphs are defined in `maf/workflows/` | 14, 121, 125 |
| Conditional edges | `add_edge(condition=)` | `src/backend/maf/engine.py` `route` | Review loops, rework after rejection, execute to heal to execute | 130 |
| Fan-out and fan-in | `add_fan_out_edges`, `add_fan_in_edges` | `src/backend/maf/engine.py`, `workflows/bug_scan.py` `bug_scan_definition`, `Merge` | Static scanners and agent review run in parallel, then merge | 130 |
| Human in the loop | `ctx.request_info`, `@response_handler` | `src/backend/maf/engine.py` `Stage.run`, `Stage.decided` | Every gate and diff approval pauses here | 751 |
| Checkpoints | `FileCheckpointStorage`, `run(checkpoint_id=)` | `src/backend/maf/engine.py` `_storage`, `_resume` | Each decision restores from a checkpoint, so a restart loses nothing | 755 |
| Streaming run events | `workflow.run(stream=True)` | `src/backend/maf/engine.py` `_consume` | Handles requests, outputs, and failures. Progress is stored for SSE | 121, 159 |
| AG-UI | `AgentFrameworkAgent` | `src/backend/maf/agui.py` | Turns a project-scoped agent into an AG-UI event stream | 549, 552 |
| Evaluation | `evaluate_agent`, `LocalEvaluator`, `evaluator` | `src/backend/maf/evals.py`, `evals/*.json` | Quality and safety cases for all 11 agents with content, JSON schema, Gherkin, and score checks. Scores are stored per prompt version | 219 |
| Agent Skills validator | `FileSkillsSource` | `src/backend/core/skills.py` | Loads `skills/` once. A skill MAF cannot load is a startup warning and is absent. Its frontmatter gives name, description, version | 228 to 234 |
| Agent Skills in chat | `SkillsProvider`, `FilteringSkillsSource` | `src/backend/maf/runtime.py` `build` | Only for a model that passed the live tool check (`llm.tool_check`): `disable_load_skill_approval=True`, `disable_read_skill_resource_approval=True`, no script runner, filtered to the agent's skills | 228 to 234, 248 |
| Observability | `configure_otel_providers` | `src/backend/app.py` `lifespan` | Turns on when `OTEL_EXPORTER_OTLP_ENDPOINT` is set | 213, 590 |

## Connected to MAF

| Integration | File | Notes |
|---|---|---|
| CopilotKit runtime with `HttpAgent` | `src/frontend/app/api/copilotkit/[[...path]]/route.ts` | One AG-UI agent per chat agent key, as PDF page 550 describes |
| CopilotKit chat UI | `src/frontend/components/Chat.tsx` | Headless `useAgent` and `runAgent` with our own view. `CopilotChat`'s thread connect step dropped messages sent during it and conflicted with restored history |
| Test double | `tests/scripted_client.py` | A real `BaseChatClient` subclass with scripted replies. Tests only |

## Agent governance

Each agent has its own file in `src/backend/maf/agents/`, which declares its policy. The folder is scanned into one registry, `POLICIES`. In workflows, agents get code in the message and no tools unless their policy lists some. Measured on 2026-11-01: tool calls through the configured proxy are unreliable on every model tried. Long tool loops also outgrew the model's context and burned tokens. So workflow agents get code in the message with no tools, using `code_pack` in `maf/workflows/shared.py`. Chat agents keep their read tools.

| Control | Where | Behavior |
|---|---|---|
| Tool policy | `governance.allowed` | Deny by default, separately for workflow and chat |
| Kill switch and token limit | `governance.update_settings`, `require_enabled` | Named person required, written to the ledger |
| Run budget | `runtime.AgentCall.text`, `ATLAS_RUN_TOKEN_LIMIT` | Stops a run with a clear error |
| Secret and injection guardrails | `governance.guard_text`, `neutralize`, `guard_tool_result` | Applied to input, output, and tool results, and recorded |
| Provider blocks | `governance.explain_error` | Plain error plus a recorded event |
| Telemetry | `governance.telemetry`, table `agent_calls` | Shown on the Agents page and in Runs & Metrics |
| Deterministic review | `core/doc_checks.py`, `cap_for_failed_tests` in `maf/workflows/change.py` | The lower of the model score and the checks wins. A failing change is capped at 60 |
| Per-case confidence | `qe/confidence.py`, `review_cases` and `review_with_send_back` in `maf/workflows/shared.py`, used by `qe_plan`, `qe_design`, `qe_generate` | `AgentCall.typed` with the `Review` schema, batches of 8 run together with `asyncio.gather` inside the model limit. Code recomputes totals and verdicts and checks every cited `file:line` through `safe_path`. A REJECT goes back alone to its agent once. `AgentCall.tokens` reports what each review used |

## Agentic QE Platform agents

| Agent | Prompt | Type | Used by |
|---|---|---|---|
| `project-copilot` | `prompts/project-copilot.md` | `Agent` | Chat |
| `business-analyst` | `prompts/business-analyst.md` | `Agent`, with a section per artifact: requirements document and Gherkin | `ba` draft, Gherkin, refine, chat |
| `repo-intelligence-analyst` | `prompts/repo-intelligence-analyst.md` | `Agent`, code supplied in the message | `qe` discover, chat |
| `requirements-analyst` | `prompts/requirements-analyst.md` | `Agent`, code supplied in the message | `qe` requirements, chat |
| `principal-test-architect` | `prompts/principal-test-architect.md` | `Agent` | `qe` plan, chat |
| `test-design-architect` | `prompts/test-design-architect.md` | `Agent` | `qe` design, chat |
| `test-automation-engineer` | `prompts/test-automation-engineer.md` | `Agent`, code supplied in the message | `qe` generate |
| `defect-diagnostician` | `prompts/defect-diagnostician.md` | `Agent`, code in the message, replies with structured edits; read tools in chat | `qe` heal, `change`, chat |
| `confidence-reviewer` | `prompts/confidence-reviewer.md` | `Agent`, with a section per review type: requirements document, evidence, design cases, generated tests, and plan | `ba` review, on-demand document review, `qe` plan and sign |
| `feature-engineer` | `prompts/feature-engineer.md` | `Agent`, code in the message, replies with structured edits | `change` |
| `bug-reviewer` | `prompts/bug-reviewer.md` | `Agent`, code supplied in the message | `bug_scan`, chat |

An agent key has hyphens, as in the plugin, and its policy file uses underscores (`maf/agents/repo_intelligence_analyst.py`) because Python modules cannot contain hyphens. `maf/agents/__init__.py` derives the key from the file name. A merged agent picks its section from an `Artifact:` or `Review type:` line at the start of the request. Migration `006_agent_plugin_names.sql` renamed the stored keys.

## Considered and not used

| Feature | Decision | Add when |
|---|---|---|
| `add_agent_framework_fastapi_endpoint` | Replaced by a thin route, because agents are built per request with project-scoped tools. `AgentFrameworkAgent` still produces the stream | Agents become global |
| AG-UI tool approval (`require_confirmation`) | Off. Chat tools are read-only or versioned, and gates live in workflows | Chat gains a destructive tool |
| `HistoryProvider` | Chat history is in `chat_messages`, and CopilotKit sends the thread each run | Server-owned history is needed |
| Orchestrations (`SequentialBuilder`, `MagenticBuilder`, `GroupChatBuilder`) | Gates and rework need explicit graphs | An open-ended multi-agent task appears |
| Declarative workflows, Functional API | Graphs are defined in Python | Non-developers must edit workflows |
| Harness Agent (`create_harness_agent`) | Built, then tested on `personal-finance-mcp`. On the configured endpoint older tool results get lost, so it reread files, drifted to other work, and used 80k to 285k tokens per change. Not used in workflows | The endpoint keeps tool results, or a task needs open-ended exploration. Planned for Skill Studio, which would use its `skills_provider` and `skills_paths`. Not built yet |
| `CopilotChat` prebuilt UI | Replaced by headless hooks for the reason above | CopilotKit fixes thread connect |
| RAG and vector stores | Keyword search over documents | Keyword search proves too weak |
| MCP tools | Tools run in-process | External tools are needed in agents |
| Durable, Foundry, A2A hosting | One process with SQLite and local files | Cloud deployment at scale |
| Foundry evaluators | Local checks need no cloud | Hosted evals are wanted |

## Errors and retries (phase 2)

- `Agent.run` returns an `AgentResponse` whose `finish_reason` is `"length"` when the model hit `max_tokens`; `AgentCall` turns that into `AQE-MODEL-002` and never parses it. Checked against the real proxy: `finish_reason` is `"stop"` on a normal reply.
- Provider failures reach us as `ChatClientException` with the OpenAI error as `__cause__`/`inner_exception`. `core.errors.classify` walks that chain for status, request id, timeout, and content filter.
- `default_options["extra_body"]` is passed straight to `chat.completions.create`. Setting `{"cache": {"no-cache": True}}` stops LiteLLM answering a repeated prompt from its cache (checked live: with it, the same prompt gave different replies at about 1.5 s each; without it the second reply was identical and about 0.9 s). `ATLAS_MODEL_NO_CACHE=0` turns it off.
- Retry of a failed run loads the latest `FileCheckpointStorage` checkpoint with `workflow.run(checkpoint_id=..., checkpoint_storage=..., stream=True)`; the failed stage's pending message is delivered again. A run that failed before its first checkpoint starts again from its input.

## Skills (phase 4)

Measured on the real proxy on 2026-11-01: with tools offered, every model called tools never offered (`read_file`, `list_files`, `grep`) and ignored tool results, even without MAF. Skill text in the message worked. So:

- Workflows never load a skill by tool. `AgentCall` puts the skill body and references into the first message of the session (`core/skills.py` `render`). `FileSkillsSource` is used as the validator and for frontmatter only.
- Chat picks a skill with one structured call (`maf/skill_chat.py`) and adds its text to that turn. On a model whose stored tool check passed, chat uses `SkillsProvider` instead.
- `llm.tool_check(model)` is the live check. Its result is stored on the `models` row.
- Skills are trusted platform text; repository and document text stays untrusted and goes through the same guardrails as before.
