# Microsoft Agent Framework guide

Page numbers refer to the official documentation PDF, `agent-framework.pdf`, in the project root.

Which MAF features Agentic QE Platform uses, where, and why. Packages: `agent-framework-core`, `agent-framework-openai`, `agent-framework-ag-ui`. Page numbers refer to `agent-framework.pdf`. Python APIs were confirmed against the installed package source, because many PDF samples are C#.

## Used

| MAF feature | API | File | How Agentic QE Platform uses it | PDF page |
|---|---|---|---|---|
| Model client | `OpenAIChatCompletionClient` | `src/backend/maf/llm.py` | One client for any OpenAI-compatible endpoint, from Settings or `.env` | 34, 439 |
| Tool loop limits | `function_invocation_configuration` (`max_iterations`, `max_function_calls`) | `src/backend/maf/llm.py` | 10 rounds and 30 calls instead of the default 100 rounds. MAF then forces a final answer with tools off | 277 |
| Chat middleware | `@chat_middleware` | `src/backend/maf/governance.py` `telemetry` | Records tokens, latency, tool calls, and status for each model round, streamed or not | 92 |
| Agents | `Agent` | `src/backend/maf/runtime.py` `build` | 13 specialists, each with a versioned prompt from the database | 6, 24 |
| Structured edits | `Agent` plus a pydantic schema | `src/backend/maf/workflows/edits.py` `ChangeSet`, `guarded_apply` | Edit agents get code in the message, have no tools, and reply with edits. Agentic QE Platform code applies them through path, secret, and scope guards | 323 |
| Function tools | `@tool` | `src/backend/maf/tools/` (one file per tool) | Repository, document, memory, and workflow tools, closed over one project | 8, 277 |
| Context providers | `ContextProvider.before_run` | `src/backend/maf/runtime.py` `ProjectContext` | Adds project facts, repo summary, document index, and memories to each run | 48 |
| Function middleware | `@function_middleware` | `src/backend/maf/runtime.py` `tool_audit` | Times and redacts each tool call, filters tool results for prompt injection, and puts the call on the run timeline | 81, 86 |
| Tool call records | `@function_middleware` | `src/backend/maf/runtime.py` `tool_audit`, `src/backend/maf/observability.py` | Stores every tool call, in workflows and chat, for the Observability page | 226 |
| Compaction | `SlidingWindowStrategy` | `src/backend/maf/runtime.py` `build` | Bounds long agent conversations | 63 |
| Workflows | `WorkflowBuilder`, `Executor`, `@handler` | `src/backend/maf/engine.py` `Stage`, `compile_workflow` | Each stage is an executor. Graphs are defined in `workflows.py` | 14, 121, 125 |
| Conditional edges | `add_edge(condition=)` | `src/backend/maf/engine.py` `route` | Review loops, rework after rejection, execute to heal to execute | 130 |
| Fan-out and fan-in | `add_fan_out_edges`, `add_fan_in_edges` | `src/backend/maf/engine.py`, `workflows/bug_scan.py` `bug_scan_definition`, `Merge` | Static scanners and agent review run in parallel, then merge | 130 |
| Human in the loop | `ctx.request_info`, `@response_handler` | `src/backend/maf/engine.py` `Stage.run`, `Stage.decided` | Every gate and diff approval pauses here | 751 |
| Checkpoints | `FileCheckpointStorage`, `run(checkpoint_id=)` | `src/backend/maf/engine.py` `_storage`, `_resume` | Each decision restores from a checkpoint, so a restart loses nothing | 755 |
| Streaming run events | `workflow.run(stream=True)` | `src/backend/maf/engine.py` `_consume` | Handles requests, outputs, and failures. Progress is stored for SSE | 121, 159 |
| AG-UI | `AgentFrameworkAgent` | `src/backend/maf/agui.py` | Turns a project-scoped agent into an AG-UI event stream | 549, 552 |
| Evaluation | `evaluate_agent`, `LocalEvaluator`, `evaluator` | `src/backend/maf/evals.py`, `evals/*.json` | Quality and safety cases for all 13 agents with content, JSON schema, Gherkin, and score checks. Scores are stored per prompt version | 219 |
| Observability | `configure_otel_providers` | `src/backend/app.py` `lifespan` | Turns on when `OTEL_EXPORTER_OTLP_ENDPOINT` is set | 213, 590 |

## Connected to MAF

| Integration | File | Notes |
|---|---|---|
| CopilotKit runtime with `HttpAgent` | `src/frontend/app/api/copilotkit/[[...path]]/route.ts` | One AG-UI agent per chat agent key, as PDF page 550 describes |
| CopilotKit chat UI | `src/frontend/components/Chat.tsx` | Headless `useAgent` and `runAgent` with our own view. `CopilotChat`'s thread connect step dropped messages sent during it and conflicted with restored history |
| Test double | `tests/scripted_client.py` | A real `BaseChatClient` subclass with scripted replies. Tests only |

## Agent governance

Each agent has its own file in `src/backend/maf/agents/`, which declares its policy. The folder is scanned into one registry, `POLICIES`. In workflows, agents get code in the message and no tools unless their policy lists some. Long tool loops outgrew the model's context and burned tokens, so `code_pack` in `workflows.py` replaced them.

| Control | Where | Behavior |
|---|---|---|
| Tool policy | `governance.allowed` | Deny by default, separately for workflow and chat |
| Kill switch and token limit | `governance.update_settings`, `require_enabled` | Named person required, written to the ledger |
| Run budget | `agents.AgentCall.text`, `ATLAS_RUN_TOKEN_LIMIT` | Stops a run with a clear error |
| Secret and injection guardrails | `governance.guard_text`, `neutralize`, `guard_tool_result` | Applied to input, output, and tool results, and recorded |
| Provider blocks | `governance.explain_error` | Plain error plus a recorded event |
| Telemetry | `governance.telemetry`, table `agent_calls` | Shown on the Agents page and in Runs & Metrics |
| Deterministic review | `core/doc_checks.py` | The lower of the model score and the checks wins |

## Agentic QE Platform agents

| Agent | Prompt | Type | Used by |
|---|---|---|---|
| Project copilot | `prompts/copilot.md` | `Agent` | Chat |
| Business analyst | `prompts/business_analyst.md` | `Agent` | `ba` draft, refine, chat |
| Document reviewer | `prompts/doc_reviewer.md` | `Agent` | `ba` review, on-demand review |
| Gherkin author | `prompts/gherkin_author.md` | `Agent` | `ba` Gherkin, refine |
| Repository analyst | `prompts/repo_analyst.md` | `Agent`, code supplied in the message | `qe` discover, chat |
| Requirements analyst | `prompts/requirements_analyst.md` | `Agent`, code supplied in the message | `qe` requirements, chat |
| Test architect | `prompts/test_architect.md` | `Agent` | `qe` plan, chat |
| Test designer | `prompts/test_designer.md` | `Agent` | `qe` design, chat |
| Test automation | `prompts/test_automation.md` | `Agent`, code supplied in the message | `qe` generate |
| Defect diagnostician | `prompts/defect_diagnostician.md` | `Agent`, code in the message, replies with structured edits; read tools in chat | `qe` heal, `change`, chat |
| Confidence reviewer | `prompts/confidence_reviewer.md` | `Agent` | `qe` plan and sign |
| Feature engineer | `prompts/feature_engineer.md` | `Agent`, code in the message, replies with structured edits | `change` |
| Bug reviewer | `prompts/bug_reviewer.md` | `Agent`, code supplied in the message | `bug_scan`, chat |

## Considered and not used

| Feature | Decision | Add when |
|---|---|---|
| `add_agent_framework_fastapi_endpoint` | Replaced by a thin route, because agents are built per request with project-scoped tools. `AgentFrameworkAgent` still produces the stream | Agents become global |
| AG-UI tool approval (`require_confirmation`) | Off. Chat tools are read-only or versioned, and gates live in workflows | Chat gains a destructive tool |
| `HistoryProvider` | Chat history is in `chat_messages`, and CopilotKit sends the thread each run | Server-owned history is needed |
| Orchestrations (`SequentialBuilder`, `MagenticBuilder`, `GroupChatBuilder`) | Gates and rework need explicit graphs | An open-ended multi-agent task appears |
| Declarative workflows, Functional API | Graphs are defined in Python | Non-developers must edit workflows |
| Harness Agent (`create_harness_agent`) | Built, then tested on `personal-finance-mcp`. On the configured endpoint older tool results get lost, so it reread files, drifted to other work, and used 80k to 285k tokens per change | The endpoint keeps tool results, or a task needs open-ended exploration |
| `CopilotChat` prebuilt UI | Replaced by headless hooks for the reason above | CopilotKit fixes thread connect |
| Agent Skills (`SkillsProvider`) | Rules live in prompts and code checks | Prompts grow too large |
| RAG and vector stores | Keyword search over documents | Keyword search proves too weak |
| MCP tools | Tools run in-process | External tools are needed in agents |
| Durable, Foundry, A2A hosting | Local single-user app | Cloud deployment |
| Foundry evaluators | Local checks need no cloud | Hosted evals are wanted |
