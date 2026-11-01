# Plugin parity and UI plan

**Status: final plan, ready to build once you approve it. None of this is built yet.**

This plan covers nine things: making the platform identical to [agentic-qe](https://github.com/sarveshtalele/agentic-qe) v1.4.0 (commit `bf2452a`) on Microsoft Agent Framework (MAF), a new enterprise UI, real evaluation scores, easy debugging, several models with per-user limits, a Word-style Documents tab, a live chatbot across all projects, a Skill Studio that creates and evaluates agent skills on MAF, and the gaps found on reviewing all of this.

## Where we stand

The platform already ports the plugin's lifecycle, but it lost much of what makes the plugin accurate. These gaps explain the weak results you saw.

| What the plugin does | What we do today | Effect on accuracy |
|---|---|---|
| Scores **each test case and each generated test** on set dimensions | One score per batch or document | A few bad cases hide inside a good average |
| Code recomputes the verdict and **rejects any citation not found in the source** | Trusts the reviewer's number | A confident invented review can pass |
| Reviewer must find the real method or route each case tests | Reviewer reads the work in general | Tests aim at the wrong target |
| Four oracle types, each with a defined basis, plus boundary cases | Oracle is only a label | Expected values get guessed, which likely causes many of the 42 of 68 finance failures |
| Requirements: observable behavior, code beats comments, one named actor | A short general rule | Requirements describe internals |
| Editing an approved document **reopens that gate and all later ones** | Document returns to draft, and gates stay approved | Later stages rest on changed inputs |
| Each defect records why the test failed and how to fix it | Failure message only | Harder to tell a real bug from a bad test |
| Each skill has its own instructions, references, and evals | One prompt per agent | Knowledge is thin and untestable |

## Part 1: Plugin mapping

### Decision: how skills run on MAF

MAF has a real skills feature: `SkillsProvider` and `FileSkillsSource`, both in the installed package (`agent-framework.pdf`, pages 228 to 234). It uses the same `SKILL.md` format as the plugin, so **the plugin's skill folders can be reused almost as they are**.

| Where | How the skill reaches the agent | Why |
|---|---|---|
| Workflows | Code puts the skill's instructions and references into the agent's message | Your model endpoint loses older tool results, as measured earlier. A skill loaded by tool call could vanish, so workflows do not rely on that |
| Copilot chat | Code picks the relevant skill from its name and description, then puts it in the message. MAF `SkillsProvider` is used only on a model that passes a live check | **Measured on 1 November 2026:** `SkillsProvider` did not work reliably on `deepseek-v4-flash-global`. See Part 9 |

**Plugin scripts do not run.** They are TypeScript for Node, which the backend does not have on Azure. Each is ported to Python, as most already are.

### Agents: names identical to the plugin

Each agent has one file in `src/backend/maf/agents/`, one prompt in `prompts/`, and one eval file in `evals/`. Stored history is renamed by a database migration, so nothing is lost.

| Plugin agent | Replaces today's | Files | What we reuse from the plugin |
|---|---|---|---|
| `repo-intelligence-analyst` | `repo_analyst` | `agents/repo_intelligence_analyst.py`, `prompts/repo-intelligence-analyst.md` | Stack, inventory, public interfaces, and gaps, separating facts from inferences. Keeps the new discovery checks |
| `requirements-analyst` | `requirements_analyst` | `agents/requirements_analyst.py`, `prompts/requirements-analyst.md` | Full `REQUIREMENT_RULES.md`: observable behavior, code precedence, one actor |
| `principal-test-architect` | `test_architect` | `agents/principal_test_architect.py`, `prompts/principal-test-architect.md` | `LEVEL_GUIDELINES.md`, risk ranking, no duplicates across levels |
| `test-design-architect` | `test_designer` | `agents/test_design_architect.py`, `prompts/test-design-architect.md` | `ORACLE_TYPES.md`, boundary cases, 2 to 3 negatives, no human steps |
| `test-automation-engineer` | `test_automation` | `agents/test_automation_engineer.py`, `prompts/test-automation-engineer.md` | `LANGUAGE_RULES.md`, 1:1 mapping to approved cases |
| `qa-execution-engineer` | Code only | `agents/qa_execution_engineer.py`, `prompts/qa-execution-engineer.md` | **New agent.** Code still runs the tests, and the agent explains results from the evidence |
| `defect-diagnostician` | `defect_diagnostician` | `agents/defect_diagnostician.py`, `prompts/defect-diagnostician.md` | `HEALING_PATTERNS.md`: real bug or test problem, permitted and forbidden fixes |
| `confidence-reviewer` | `confidence_reviewer`, `doc_reviewer` | `agents/confidence_reviewer.py`, `prompts/confidence-reviewer.md` | Dimensions per artifact, per-case scoring, citations |

**Agents the plugin does not have.** The platform has features beyond the plugin, so these stay, in the same naming style:

| Name | Replaces today's | Why it stays |
|---|---|---|
| `business-analyst` | `business_analyst`, `gherkin_author` | BA Studio. Uses the plugin's `authoring-user-stories` skill |
| `bug-reviewer` | `bug_reviewer` | Bug Scan |
| `feature-engineer` | `feature_engineer` | Feature Builder |
| `project-copilot` | `copilot` | Chat |

That makes **12 agents: the plugin's 8, unchanged in name, plus 4 for platform features.** Skill Studio adds 6 more, named in Part 9, for 18 in total.

### Skills

Skills are copied to `skills/<name>/`, keeping the plugin's folder layout, with `${CLAUDE_SKILL_DIR}` and command references adapted. Each plugin skill's `evals/evals.json` joins that agent's evals.

| Plugin skill | Used by agent | Workflow stage | Python port of its script |
|---|---|---|---|
| `analyzing-repositories` | `repo-intelligence-analyst` | `qe` discover | `repos/scan.py` (`scan-repo.ts`) |
| `extracting-requirements` | `requirements-analyst` | `qe` requirements | `qe/contracts.py`, new (`extract-contracts.ts`) |
| `authoring-user-stories` | `business-analyst` | `ba` draft, Gherkin | `api/documents.py` (`export-cases.ts`) |
| `planning-tests` | `principal-test-architect` | `qe` plan | `qe/model.py` (`calculate-risk.ts`) |
| `designing-test-cases` | `test-design-architect` | `qe` design | `qe/confidence.py`, new (`check-confidence.ts`) |
| `generating-test-data` | `test-design-architect` | `qe` data, new stage | `qe/test_data.py`, new (`synthesize-data.ts`) |
| `generating-test-code` | `test-automation-engineer` | `qe` generate | `qe/emit.py`, new (`emit-tests.ts`), with `invalid_test_code` |
| `executing-tests` | `qa-execution-engineer` | `qe` execute, `change` verify | `qe/execution.py` (`run-isolated.ts`, `parse-junit.ts`), and evidence collection added |
| `healing-tests` | `defect-diagnostician` | `qe` heal | `qe/execution.py` (`diagnose-failure.ts`, `apply-healing.ts`) |
| `tracing-coverage` | `confidence-reviewer` | `qe` trace | `qe/trace.py` (`build-matrix.ts`) |
| `building-qe-dashboard` | None. It is a UI feature | QE Studio | `qe/reports.py`, new (`gate-report-md.ts`, `build-trace-report.ts`) |

### Commands become workflow stages

| Plugin command | Workflow stage | File | Change |
|---|---|---|---|
| `qe-start` | Intake, G0 | `workflows/qe.py` | Rename stage. Add scope and framework choices |
| `qe-discover` | Discover | `workflows/qe.py` | Rename agent. Load skill |
| `qe-stories` | BA draft, or a greenfield QE start | `workflows/ba.py` | Load skill |
| `qe-requirements` | Requirements, G1 | `workflows/qe.py` | Add actor and evidence rules |
| `qe-plan` | Plan, G2 | `workflows/qe.py` | Score on plugin dimensions |
| `qe-design` | Design, G3 | `workflows/qe.py` | Per-case review |
| `qe-data` | Data, part of G3 | `workflows/qe.py` | **New stage** |
| `qe-generate` | Generate, G4 | `workflows/qe.py` | Per-test review |
| `qe-execute` | Execute | `workflows/qe.py` | Add evidence collection and per-case durations |
| `qe-heal` | Heal | `workflows/qe.py` | Defect records with cause and fix |
| `qe-trace` | Trace | `workflows/qe.py` | Orphan tests and unmapped P0 or P1 flagged |
| `qe-sign` | Sign, G5 | `workflows/qe.py` | Seal a proof pack |
| `qe-panel` | QE Studio live view | `frontend` | See Part 2 |
| `qe-doctor` | Settings, system health | `api/settings.py` | Add ledger integrity and plugin version |

### Hooks

Claude Code hooks do not exist in a web app, so each becomes code that runs at the same moment. MAF's **Agent Hooks** (PDF page 227) is the framework's control point for this. I will check that its Python API fits before using it. If it does not, the existing middleware stays.

| Plugin hook | When it runs | Today | Change |
|---|---|---|---|
| `guard-write.ts` | Before an edit | `guarded_apply`, `apply_edits` | Compare its rules against ours and add any missing |
| `guard-bash.ts` | Before a shell command | Agents have no shell | Nothing to run. Review its blocked commands against `run_suite` |
| `stamp-metadata.ts` | After a write | Document versions | Add source commit and phase to each version |
| `ledger-hook.ts`, `memory-logger.ts` | After each action | `core/ledger.py`, `tool_calls` | Already covered |
| `approval-hook.ts`, `on-decision.ts` | At each decision | `engine.decide`, `core/gates.py` | Add **gate reopening** and Markdown gate reports |
| `confidence.ts` | At a gate | Reviewer's own number | **Port to `qe/confidence.py`.** Code recomputes the verdict and rejects missing citations |
| `session-check.ts` | At startup | `engine.recover` | Add to Settings health |
| `layout.ts` | Output folders | Database and folders | ZIP export in the plugin's `00-intake` to `09-release` layout |

### New accuracy rules

| Rule, from the plugin | File | How it is checked |
|---|---|---|
| Plan dimensions: `controls_covered` 40, `level_fit` 30, `scenarios_derivable` 30 | `qe/confidence.py` | Unit test |
| Design dimensions: `source_proven` 30, `correct_target` 25, `expected_derivable` 25, `fixture_validity` 20 | `qe/confidence.py` | Unit test |
| Code dimensions: `compilable` 30, `assertion_integrity` 30, `import_safety` 20, `traceability_present` 20 | `qe/confidence.py` | Unit test |
| Verdict by code: 100 is APPROVED, 70 or above is REVISE, below 70 is REJECT | `qe/confidence.py` | Unit test |
| A citation not found on disk means REJECT, and weak assertions count as low confidence at any total | `qe/confidence.py` | Unit test |
| A rejected case returns to its agent alone, with the flaw and its fix | `workflows/qe.py` | Integration test |
| Editing an approved document reopens that gate and all later ones | `core/gates.py`, `core/documents.py` | Integration test |
| Measure the result: the finance repo's pass rate and coverage, before and after | `tests/e2e/test_finance_repo.py` | Reported honestly, with no target forced |

**A limit to expect.** The plugin approves only at 100, so far more items will come back for revision. That costs more tokens but is the accuracy you asked for. Reviews would apply to batches of cases, to stay within the budget.

## Part 2: UI plan

### Component choices

Researched with firecrawl and context7. Your current UI uses Tailwind and hand-written components only.

| Need | Choice | Why | Rejected |
|---|---|---|---|
| Base components | **shadcn/ui**, with Base UI primitives | The code lives in our repo, is accessible, and uses Tailwind v4. Over 120k GitHub stars. Base UI is its current default, as Radix is no longer actively maintained | MUI and Ant Design: heavy, with a recognizable look |
| Data tables | **TanStack Table v9** | Sorting, filtering, and paging, with unused features left out of the bundle | Paid data grids |
| Workflow graph | **React Flow** (`@xyflow/react`), with its `NodeStatusIndicator` | Built-in loading, success, and error states on nodes | Hand-drawn SVG |
| Charts and KPI tiles | **shadcn charts on Recharts** | Matches the base components | Tremor: adds a second design language |
| Command palette | **shadcn Command** (cmdk) | Cmd+K search across everything | |
| Motion | **Motion** | Spring transitions and number count-ups | |
| Decorative effects | **Magic UI**, sparingly | Sign-in and home hero only. It suits marketing more than working screens | Aceternity: too heavy for work screens |
| Code and Gherkin editing | **CodeMirror 6** | Syntax colors and light weight | Monaco: very large |
| Rich text editing | **Tiptap** with its Markdown extension | Word-style editing that stores Markdown, with a headless design that fits shadcn | CKEditor and TinyMCE: their own UI, and licensing to check |
| Diff review | **react-diff-view** | Split or unified, with file tree and line numbers | |
| Toasts | **Sonner** | Stacks, with undo | |

**CSS techniques**, needing no libraries:

- View Transitions between pages
- Container queries so cards adapt to their column
- `color-mix()` tokens for one consistent theme
- Skeletons sized like the real content, to stop layout shift
- `focus-visible` rings on every control

All motion respects `prefers-reduced-motion`.

**Bento layout rules, from the research:** tile size shows importance, the gap is 16px, every tile has an `aria-label`, and tab order follows reading order.

### Screen-by-screen ideas

| Screen | Today | New design | Components |
|---|---|---|---|
| **Sign in** | Plain form | Split screen with an animated lifecycle diagram (G0 to G5) beside the form | Magic UI beams, shadcn Form |
| **App frame** | Text sidebar | Collapsible icon rail with groups and tooltips, breadcrumbs, project switcher, and **Cmd+K** | shadcn Sidebar, Command, Breadcrumb |
| **Home** | Four tiles, plain cards | Bento: hero "needs you now" tile, gate progress rings, token trend, and project cards with mini pipeline dots | Bento grid, Recharts, Motion |
| **Project overview** | Four text cards | Live pipeline across the top, risk and coverage rings, activity feed, and next-step card | React Flow, Recharts |
| **Repository** | Stats and file list | Language treemap, file tree with viewer, commit timeline, and sandbox health card | Treemap, CodeMirror, Timeline |
| **BA Studio** | Long form | Stepper: brief, sources, template, review. Drag-and-drop uploads, template preview cards, and a live document card rail | Stepper, Dropzone, Sheet |
| **Documents list** | Text list | Card and table views, with filters and hover preview. Full mapping in Part 6 | TanStack Table, HoverCard |
| **Document page** | In-place editor | Word-style editor with toolbar, outline, editable split view, and upload. Full mapping in Part 6 | Tiptap, CodeMirror, Resizable, react-diff-view |
| **Gherkin** | Colored text | Scenario cards that expand, Examples grids, and a step coverage bar | Accordion, TanStack Table, CodeMirror |
| **Feature Builder** | Form and panel | Split view: spec on the left, live steps in the center, file tree with diffs on the right | Resizable, react-diff-view |
| **Bug Scan** | List | Severity donut, table with filters, side panel with code and fix, and a bulk **Fix selected** | TanStack Table, Sheet, Recharts |
| **QE Studio** | Chips and log | **Live pipeline graph**: each stage a node with status, score, and tokens. Select a node to see its log and documents in a side panel | React Flow, `NodeStatusIndicator`, Sheet |
| **Live log** | Terminal box | Filter by agent, stage, and level, with search, follow toggle, and line links | Virtualized list, Tabs |
| **Approval card** | Amber form | Decision panel: confidence ring, per-case scores, flaws with fixes, evidence links, and keyboard shortcuts | Radial chart, Tabs, Dialog |
| **Test results** | Summary line | Pass and fail heatmap by requirement. Each failure shows cause, fix, and screenshot | Heatmap, Accordion |
| **Traceability** | Table | Requirement to case to test to result, as a clickable matrix with gaps highlighted | TanStack Table, React Flow |
| **Governance** | Lists | Gate timeline with signers, and a ledger view with a hash chain check animation | Timeline, Motion |
| **Runs and metrics** | Tables | Trend charts for tokens, duration, and pass rate, with run comparison | Recharts, TanStack Table |
| **Observability** | Log list | Trace waterfall per run, like a tracing tool, with filter chips and saved views | Custom timeline, Tabs |
| **Agents** | Cards | Cards with four score tiles and sparklines, see Part 3. The agent page adds its skills, score trends, cases, and prompt diff | Recharts, react-diff-view |
| **Skills** | None | **New page, Skill Studio**: built-in skills are read only, and yours can be created, tested, and improved. Full mapping in Part 9 | Cards, Stepper, CodeMirror, TanStack Table, Recharts |
| **Prompts** | List | Version timeline, side-by-side diff, and try-it-with-an-eval | react-diff-view |
| **Copilot** | Chat | A ChatGPT-style assistant with live cards inside the conversation. Full mapping in Part 7 | CopilotKit, Motion, Tiptap for rendering |
| **Users (admin)** | Forms | Table with token bars, and an edit drawer with a date range picker | TanStack Table, Sheet, Calendar |
| **Settings** | Forms | Tabs with live health checks, and a **Doctor** report | Tabs, Progress |
| **Docs** | Docs site | Add page anchors, copy buttons, and link it to Cmd+K | Command |
| **Empty and loading states** | Dashed boxes, spinners | Skeletons, and illustrated empty states with a clear next action | Skeleton |

### New dependencies

`@xyflow/react`, `@tanstack/react-table`, `recharts`, `motion`, `cmdk`, `sonner`, `react-diff-view`, `@tiptap/*`, `@codemirror/*`, `@uiw/react-codemirror`, plus `@base-ui-components/react` for shadcn. These add to the page size, so heavy ones (React Flow, CodeMirror, Tiptap) load only on the screens that need them.

All must work on Windows, macOS, and Linux, in Next.js 16. I will check each against the installed Next.js docs while building.

## Part 3: Evaluations

### Why some agents show high risk

Risk measures **what an agent could affect, not how well it behaves**. Two agents are high because their job is to change code: `feature-engineer` builds features, and `defect-diagnostician` fixes bugs. Feature Builder and Bug Scan fixes cannot work without them, which is why they are in the application.

A high-risk agent is contained in these ways:

| Control | Effect |
|---|---|
| No tools in workflows | It can only return proposed edits as text |
| Guarded edits | Code refuses path escapes, secrets, overwrites, deletions, out-of-scope files, and edits that break syntax |
| Separate branch | Your main code is never touched |
| Real tests and a confidence review | Run before anyone is asked to decide |
| Named human approval | Nothing is committed without it, and agents cannot approve |
| Disable switch and token limits | The admin can stop it at once |

**Proposed UI change:** rename the badge from "high risk" to **"Impact: changes code"**, and list these controls on the card, because "high risk" reads like a warning that something is wrong.

### What runs today

26 cases across 13 agents, run through MAF's `LocalEvaluator`, with results stored per prompt version.

| Check | What it proves | Used for |
|---|---|---|
| Contains, does not contain | Required text is present, and invented text is absent | Most agents |
| Valid JSON schema | The reply can be used by the next step | 7 agents |
| Official Gherkin parser | Scenarios are valid | `gherkin_author` |
| Score limits | Weak or untested work cannot score high | `doc_reviewer`, `confidence_reviewer` |
| Prompt injection cases | The agent ignores instructions hidden in content | 7 agents |

**This is too weak to show accuracy.** The cases are short and mostly check for keywords, so a card showing 2/2 means little. They catch breakage and stay as a fast first layer.

### What the RAG metrics mean here

The platform has no vector database, but **each agent answers from context we give it**: selected code, documents, or tool results. That context plays the role of retrieved chunks, so the metrics apply, and Context Recall also tests our own file selection, which is a likely cause of thin discovery summaries.

| Metric | Question it answers | How it is measured | Cost |
|---|---|---|---|
| **Groundedness** | Do its citations really exist? | Code checks every path, line, and quote on disk | Free |
| **Faithfulness** | Is each claim supported by the context? | RAGAS `Faithfulness` | Model tokens |
| **Context Recall** | Did the context hold what the answer needs? | RAGAS `ContextRecall`, against a reference | Model tokens |
| **Context Precision** | Was the context relevant? | RAGAS `ContextPrecision` | Model tokens |
| **Response Relevancy** | Did it answer what was asked? | RAGAS `ResponseRelevancy` | Model tokens |
| **Precision, Recall, F1** | Did it find the right items, without extras? | Code compares results to a labelled answer key where items can be matched. Otherwise RAGAS `FactualCorrectness` in F1 mode | Free, or tokens |
| **Mutation score** | Do generated tests catch real bugs? | Plant a bug and check that a test fails | Test run time |

Metric names come from the RAGAS documentation (version 0.4.3). I will confirm each one's exact API while building.

### Metrics for each agent

RAG metrics do not suit every agent. A generated test is not a claim to check against context. **Those agents show "n/a" with their own measure, rather than a misleading number.**

| Agent | Groundedness | Faithfulness | Recall and F1 measured against | Agent-specific measure |
|---|---|---|---|---|
| `repo-intelligence-analyst` | Cited paths exist | Yes | Key facts in the answer key | Modules covered, facts matching the scan |
| `requirements-analyst` | Quotes verified on disk | Yes | Labelled requirements | Share with one actor and observable behavior |
| `principal-test-architect` | Requirement ids exist | Yes | Requirements covered by the plan | Level fit, duplicates across levels |
| `test-design-architect` | Case targets exist | Yes | Labelled scenarios, including boundaries | Case mix, valid oracles |
| `test-automation-engineer` | Imports exist | n/a | Cases with a test | **Mutation score**, tests that run |
| `qa-execution-engineer` | Claims match JUnit | Yes | Failures reported | Summary matches the results |
| `defect-diagnostician` | Cited lines exist | Yes | Labelled failures: defect, test problem, or environment | Seeded bugs fixed with tests passing |
| `confidence-reviewer` | Citations exist | Yes | Seeded good and bad work, approve or reject | Agreement with labels |
| `business-analyst` | Cites the sources | Yes | Facts from the brief | Invented figures, headings kept, valid Gherkin |
| `bug-reviewer` | Quotes verified on disk | Yes | **Seeded bugs**, plus clean files for false alarms | False alarm rate |
| `feature-engineer` | n/a | n/a | Named functions and hidden tests | Hidden tests pass, none broken |
| `project-copilot` | Cited documents exist | Yes | Question and answer key | Response Relevancy, right tool called |
| The 6 Skill Studio agents | Evidence found in the output | Yes, for `skill-author` | Source requirements, and labelled grades for `skill-grader` | See Part 9 |

### The answer key

Recall and F1 mean nothing without known right answers, and **I will not invent scores**. So:

| Benchmark | Contents | Purpose |
|---|---|---|
| `evals/benchmarks/shop/` | A small repository with **planted bugs**, clean files, and labelled requirements, failures, and questions | Fast, and fully known |
| `personal-finance-mcp` at a pinned commit | Labels for real requirements and real bugs | Shows performance on real code |

I will draft the labels, but **someone who knows these repositories must check them**, because wrong labels produce wrong scores.

### How it fits together

| Part | File | Details |
|---|---|---|
| Deterministic metrics | `maf/evals/metrics.py`, new | Groundedness, Precision, Recall, F1, mutation score. Also plugs into MAF `LocalEvaluator` |
| RAGAS metrics | `maf/evals/ragas_evaluator.py`, new | Implements MAF's `Evaluator` type, and calls `ragas.llms.llm_factory` with your LiteLLM URL |
| Case format | `evals/<agent>.json`, extended | Adds `context`, `reference`, and which metrics apply |
| Plugin evals | `skills/<name>/evals/evals.json` | Run with their agent |
| Stored scores | `evaluations`, by migration | Each metric, with case detail, per prompt version |
| Live scores | Workflows | Groundedness runs on **every real run**, as it is free |
| Docs | `/docs/agents`, and `docs/EVALUATIONS.md` | Each metric, its formula, its meaning, and how to read it |

**RAGAS is installed separately**, in `requirements-evals.txt`. It brings about 20 packages, including LangChain and `datasets`, too heavy for the app itself or a B1 plan. On Azure, evaluations run as a job. CI must confirm it installs on Windows.

MAF's Foundry evaluators also offer groundedness and relevance, but need a Microsoft Foundry project, which you do not use, so they are left out.

### On the agent cards

| Where | Shows |
|---|---|
| Card | Four tiles: **Groundedness, Faithfulness, Recall, F1**, each with a color and a small trend line. "Not measured" until run, and "n/a" where it does not apply |
| Agent page | All metrics, trend per prompt version, every case with its question, context, answer, and reason, plus worst cases first |
| Agents page | Sort and filter by metric, and a **Compare prompt versions** view |
| Prompts page | Scores for a new version beside the active one, before activating it |

### Limits to know

| Limit | What to do |
|---|---|
| A model grading itself is a weak check | Use a **different judge model** through your proxy (`ATLAS_EVAL_MODEL`). If there is none, cards say so |
| RAGAS scores vary between runs, as they use a model | Show the spread across repeated runs, and judge trends rather than single numbers |
| They cost tokens, and I cannot estimate how many until the first run | Run on demand or nightly, never on each page view, and report the real tokens used |
| Good scores on a benchmark do not guarantee real results | Keep the live groundedness and finance repo numbers beside them |
| No pass marks yet | The first run sets a baseline, and then you choose targets from real numbers |

## Part 4: Error handling and debugging

### Why your design run failed

```text
design: Agent test_designer did not produce valid CaseSet: cases Field required
[input_value={'id': 'TC-001-1', ...}]. The reply had 29691 characters and began: '{ "cases": [ ...
```

| Step | What happened |
|---|---|
| 1 | The agent replied with about 29,700 characters that began correctly with `{"cases": [` |
| 2 | **That reply as a whole was not valid JSON.** The parser could not read the outer object |
| 3 | The parser then searched further in, found the first complete case, and used that as the answer |
| 4 | The check rejected it, as a single case has no `cases` field, so the message blamed a missing field |
| 5 | All retries failed the same way, and the whole run stopped, losing the batches that had worked |

**The message misled you.** The real problem was broken JSON, not a missing field.

**The exact cause cannot be proven, because the reply was never saved.** That gap is the main thing to fix here. The most likely cause is a raw line break or a lone backslash inside a text field, such as a file path or regex in test data. A cut-off reply is less likely, as 29,691 characters is roughly 8,000 tokens against a 16,000 limit, though the provider could have its own limit. Your database shows the same kind of failure on `requirements_analyst`, so this is not specific to one agent.

**Already fixed in the code about to be pushed:** the parser accepts both of those likely causes, never treats an inner fragment as the answer, reports the real JSON error with its position, and splits a test design batch that keeps failing. **Not yet checked against your repository:** a finance repo run will confirm it.

### What is weak today

| Gap | Where | Effect |
|---|---|---|
| The model's rejected reply is thrown away | `AgentCall.typed` | The cause of a failure cannot be proven later |
| Errors are plain strings | `engine._guarded`, `runs.error` | No error code, retry rule, or next step |
| Stack traces only print to the console | `traceback.print_exc()` in `engine.py` | Lost on restart, not redacted, and not visible in the app |
| One failed batch stops the whole stage | `asyncio.gather` in `qe_design` | Good work is lost and tokens are wasted |
| A failed run can only be started again | Run panel | No retry from the failed stage |
| Provider errors are cut to 500 characters | `governance.explain_error` | Status, provider request id, and type are lost |
| No error pages in the UI | No `app/error.tsx` or `global-error.tsx` | A UI crash shows a blank or default page |
| API errors have no id | `app.py` handlers | A UI error cannot be matched to its log |

### The design

**1. Typed errors with codes,** in `core/errors.py`. Each says what happened and what to do, and whether a retry can help.

| Code | Error | Example | Automatic action | Next step shown |
|---|---|---|---|---|
| `AQE-MODEL-001` | Reply is not valid JSON | This failure | Ask again with the position, then split the batch | Retry the stage |
| `AQE-MODEL-002` | Reply cut off at the limit | `finish_reason` is length | Ask for shorter text, then split | Raise the agent's limit |
| `AQE-MODEL-003` | Reply fails the schema | Field missing | Ask again with the field | Retry the stage |
| `AQE-MODEL-004` | Model timed out | No reply in 180 seconds | Retry once | Check the endpoint, or raise `ATLAS_MODEL_TIMEOUT` |
| `AQE-MODEL-005` | Provider refused | Content filter | No retry | Remove the flagged text |
| `AQE-MODEL-006` | Endpoint or key problem | 401, 429, or 5xx | Back off on 429 and 5xx, no retry on 401 | Open Settings |
| `AQE-ALLOW-001` | Allocation used or dates passed | Token limit reached | No retry | Ask the administrator |
| `AQE-REPO-001` | Clone or Git failure | Bad token or URL | No retry | Check repository access |
| `AQE-EVID-001` | Evidence check failed | No quote exists on disk | Send back once | Review the requirements |
| `AQE-TEST-001` | Tests could not run | Missing dependency | No agent retry | Tick install dependencies |
| `AQE-INT-001` | Bug in this application | Unexpected exception | No retry | Copy the diagnostics and report it |

**2. A diagnostic record for every failure,** in a new `run_failures` table, with redaction applied first:

| Field | Why it helps |
|---|---|
| Error id, code, run, stage, agent, attempt | Find it straight away |
| Prompt version, model, finish reason, tokens, duration | See what was asked of which model |
| Parser position, and the text around that position | **See the exact character that broke** |
| Full rejected reply, saved to a file under the run | **Proves the cause, instead of guessing** |
| Redacted stack trace | Find the line of code |
| Provider status and request id | Raise it with the provider |

**3. Keep work when part of a stage fails.** Each finished batch or file is saved as it completes. Retrying a stage repeats **only what failed**, so tokens are not wasted. If some batches keep failing, the gate can show the partial result, clearly marked with what is missing.

**4. Consistent handling at every boundary.**

| Boundary | Rule |
|---|---|
| Model call | All failures become a typed error in `AgentCall` |
| Workflow stage | `engine` records the record above and never loses the original cause |
| API | One handler returns `{code, message, action, error_id}`, with an `X-Request-Id` on every response |
| Subprocess | Git and test runners report the exit code, timeout, and last output, redacted |
| Browser | `error.tsx` and `global-error.tsx` show the id with a retry button. API and network failures appear as clear messages |
| Code rule | No bare `except`. A broad `except Exception` must record the error or re-raise, enforced by Ruff rules `BLE` and `TRY` in CI |

**5. Structured logs.** One JSON line per event, with request, run, stage, agent, and error ids, always through the existing log mask. Optional OpenTelemetry stays available.

### What you would see

| Where | Change |
|---|---|
| Failed run | A clear card: what happened, why, and what to do, with technical details collapsed |
| Buttons | **Retry failed stage**, **Copy diagnostics** (safe to share, as it is redacted), and **Open in Observability** |
| Live log | The failing step in red, with its error code |
| Observability | An **Errors** tab, grouped by code and agent, with trends |
| Agent cards | Failure rate by code, so an unreliable agent stands out |
| Docs | A page listing each error code, its causes, and fixes |

### How this is tested

| Test | Proves |
|---|---|
| Each error code triggered on purpose, using scripted bad replies | The right code, message, and action appear |
| Broken JSON of each kind: cut off, raw line break, bad escape, wrong shape | Parsing never accepts a fragment |
| Fail one batch of four | The other three are kept, and retry repeats only that one |
| A secret inside a rejected reply | Saved files, logs, and the UI never show it |
| A crash inside a page | The error page appears with an id |

## Part 5: Models, token limits, and logs

### Several models on one proxy

Today Settings holds one model name. Your LiteLLM proxy serves many models on one URL and key, so the app should too.

| Feature | Design | File |
|---|---|---|
| Model list | The admin adds names by hand, or chooses **Load from proxy**, which reads the proxy's `/v1/models`. Each has a label, an on or off switch, and its own **Test** button | `core/models.py`, new table `models` |
| One URL and key | Stay in one place, encrypted as now | `maf/llm.py` |
| Default model | One marked as the default | Settings page |
| Model per agent | The admin can set a model per agent, such as a cheaper one for scanning and a stronger one for reviews | Agent page, `agent_settings` |
| Model per run | A picker when starting a run or chat, showing only models that person may use | Run forms, Chat |

**Which model a call uses,** first match wins: the choice for this run, then the agent's model, then the user's default, then the system default. The result is always checked against what that user may use, and each call records the model it really used.

### What each user can access

| Setting | Design |
|---|---|
| Allowed models | The admin ticks specific models for each user. **A user with none ticked cannot run anything**, so access is never given by accident |
| User default | One of their allowed models |
| Daily, weekly, and monthly limits | Each optional, in tokens. All that are set apply together, alongside the existing overall allocation and active dates |
| Per-model limits, optional | For example, a lower limit on an expensive model |

**How limits work:**

| Question | Answer |
|---|---|
| When do periods reset? | Daily at midnight, weekly on Monday, monthly on the 1st, in one time zone set by the admin |
| What counts? | Input and output tokens, from each recorded model call |
| What happens at a limit? | The next model call stops with a clear message naming the limit and when it resets, such as `AQE-ALLOW-002` |
| What about a run in progress? | It stops safely and keeps its work, and **Retry failed stage** continues it after the reset |
| Can a limit be overrun? | Slightly. A call's size is known only after it finishes, so one in progress can pass the limit. LiteLLM virtual keys can add a hard limit at the proxy |

**What you would see:**

| Where | Shows |
|---|---|
| Users page | Tick boxes for models, the three limits, and usage bars for today, this week, and this month |
| User's own header | Tokens left today, with a warning at 80% |
| Admin usage page, new | Tokens by user, model, agent, and day, with charts and CSV export |

Today's single `users.model` setting moves to the new allowed list by migration, so existing users keep their access.

### Logs for debugging

This extends Part 4. **Each event is saved accurately, and logs survive restarts.**

| Log | What it holds | Where |
|---|---|---|
| Application log | Every API request, with its id, status, duration, and user id, plus every warning and error | `data/logs/app-YYYY-MM-DD.jsonl` |
| Run log | Every step, agent call, tool call, review, and test result | Existing `run_events`, plus one file per run |
| Model calls | Agent, **model**, prompt version, tokens, duration, finish reason, and provider request id | `agent_calls`, extended |
| Model conversations | The full redacted request and reply for each call, viewable on the Observability page | One file per call, under the run |
| Failures | The diagnostic records from Part 4 | `run_failures` |
| Subprocesses | Each Git and test command, with exit code, duration, and output | `run_events`, plus files |
| Sign-ins and admin changes | Who did what, by account id and never by name or password | `auth_events` |

| Rule | Detail |
|---|---|
| One id links everything | A request id and run id on each line, so one failure can be followed across all logs |
| Masked before writing | All lines pass `redact()`, and tests prove that passwords, keys, and usernames never appear |
| Rotation | Files roll daily and are removed after 30 days, set by `ATLAS_LOG_RETENTION_DAYS` |
| Easy to reach | Search on Observability, and the admin can **Download logs** for a run, a day, or a user |
| Azure | The same lines go to Log Analytics, in the design in `docs/AZURE_SYSTEM_DESIGN.md` |

**Be aware:** full model conversations contain repository code. They are masked for secrets, not for code, so they are visible only to the project's owner and the admin, and they use disk space.

### How this is tested

| Test | Proves |
|---|---|
| A user requests a model they were not given, through the UI or directly by API | Refused, and the attempt is logged |
| Each limit reached, then the clock moved past the reset | Stops with the right message, then works again |
| Model order: run, agent, user, system | The right model is used and recorded |
| A run that reaches its limit part way | Work is kept and it can continue |
| A secret and password placed in a model reply and a request | Absent from every log file and table |
| A real run through your proxy with two models | Each call records the right model |

## Part 6: Documents tab

### The editing model

**Word-style editing becomes the main experience.** Markdown stays the stored format, so versions, diffs, hashes, reviews, and exports all keep working.

| Decision | Choice | Why |
|---|---|---|
| Rich editor | **Tiptap**, with its official Markdown extension | Bold, headings, tables, and images directly on the page, and it reads and writes Markdown |
| What it replaces | Today's click-a-block editor | Editing becomes continuous, like Word or Google Docs |
| Both panes stay in sync | In **Source**, the raw text on the left and the formatted editor on the right update each other as you type | You asked to edit on the right as well, and today that pane is read-only |
| Gherkin | **CodeMirror** with syntax colors, plus scenario cards and Examples grids | Gherkin is not rich text, and formatting could break it |
| Patches | Read only, in the diff viewer | A patch is a record of a change |

**Limits to expect.** Tiptap's Markdown extension is marked as an early release. A table cell can hold only one block, as Markdown cannot represent more, and rewriting may tidy spacing. So the build includes a round-trip test on real generated documents, and **opening and closing a document without editing must not mark it as changed or create a version.** If round-trip fidelity falls short, the plain block editor stays as the fallback.

### Component mapping

| Part of the tab | Today | New component | Behavior |
|---|---|---|---|
| Documents list | Text rows | **Card and table views**, TanStack Table | Search, filter by kind and status, sort, and bulk download |
| Document card | None in list | Card with icon, kind, version, status, score, and author | Hover shows a preview, and a menu holds actions |
| Page header | Title and small badges | **Sticky header** with editable title, status pill, version menu, and confidence score | Stays visible while scrolling |
| View switch | Three text tabs | **Segmented control**: Edit, Split, Read, History | Remembers your choice |
| Toolbar | None | **Fixed toolbar** | Headings, **bold**, *italic*, underline, strikethrough, bullets, numbered list, checklist, quote, code, link, table, image, undo, redo |
| Selection menu | None | **Floating bubble menu** | Formatting at the selected text, plus **Ask agent to rewrite** |
| Table editing | Add row and column buttons | **Table toolbar and drag handles** | Add or remove rows and columns, resize, header row, and paste from Excel |
| Images | Upload button | **Drag, drop, or paste**, with caption and resize | Same checks as today, and exports to Word |
| Outline | None | **Left outline rail** | Jumps to headings, and shows the current section |
| Source pane | Plain textarea | **CodeMirror** | Markdown colors and line numbers, with scrolling linked to the other pane |
| Split view | Fixed two columns | **Resizable panes** | Drag the divider. Both sides can be edited |
| Save bar | Bottom form | **Compact bar** with autosaved draft, change note, and **Save version** | Drafts survive a refresh and never create a version until you save |
| History | List and text diff | **Version timeline**, and side-by-side diff with word-level changes | Compare any two versions, and restore |
| Review | Button and text list | **Review side panel**: score ring, issues, and links to the exact section | Select an issue to jump there |
| Refine with agent | Text box | **Side panel with suggestions**, shown as accept or reject per change | Nothing changes until you accept |
| Downloads | Row of buttons | **Export menu** with all formats | Also ZIP of all documents |
| Approve | Button | **Approval dialog** with name, note, and what this unlocks | Warns if a gate will reopen |
| Gherkin status | One badge | **Scenario count, step count**, and errors at their line | Selecting an error jumps to it |
| Empty and loading | Spinner | **Skeleton page** and clear empty state | Prevents layout shift |

### Download, edit, and upload again

An alternative for people who prefer working in Word or another editor.

| Step | What happens |
|---|---|
| 1. Download | **.md** or **.docx**, as today. The file name holds the version, such as `brd-v3.docx` |
| 2. Edit | In any editor |
| 3. Upload | **Upload new version** on the document page, by button or by dragging onto the page |
| 4. Compare | A **diff against the current version** shows exactly what will change, before anything is saved |
| 5. Confirm | Add a note and choose **Save as new version** |

| Rule | Detail |
|---|---|
| Accepted files | `.md`, `.txt`, `.docx`, and `.feature` for Gherkin |
| Same protections as other uploads | Size limit, the file's content is checked and not just its name, and secrets are flagged before saving |
| Immutable history | Always a new version with hash, author, and note, recorded as uploaded. It never overwrites |
| Gherkin | Must pass the official parser, or it is refused, with the errors shown by line |
| Someone else changed it | If the current version is newer than the one downloaded, you are warned and shown both differences |
| Approved documents | Upload returns it to draft and reopens that gate and later ones, as in Part 1 |
| Word limits | Headings, lists, tables, bold, and images convert to Markdown. **Complex layouts, text boxes, and tracked changes do not survive.** The diff shows the result before you confirm |

The API is `POST /api/documents/{id}/upload` for the preview, then the existing save for confirming, in `api/documents.py` and `core/files.py`. Today's Word conversion drops images and some formatting, so it needs extending, and it needs a test that downloads, changes, and uploads again.

### How this is tested

| Test | Proves |
|---|---|
| Open and close real generated documents | No false change, and no version created |
| Bold, heading, table, and image edits on the right | The Markdown on the left is correct, and it saves |
| Edits on either pane | The other updates |
| Download `.docx`, edit it in code, upload | The diff is right, and a new version appears |
| Upload invalid Gherkin, an oversized file, a fake file type, a file with a secret | Each is refused or flagged clearly |
| Upload based on an old version | The conflict warning appears |

## Part 7: Chatbot

### What changes

| Today | New |
|---|---|
| Chat exists only inside a project | **Also on Home, knowing all your projects**, pending approvals, findings, and runs |
| Replies are text with tool names | **Live cards inside the conversation**, like ChatGPT with artifacts |
| Starting a workflow gives a run id | The run appears in the chat and updates in real time, showing which agent and skill is working and why |
| Documents are found elsewhere | They open beside the chat, and can be edited there |
| Approving means leaving the chat | Approve from a card, as yourself |

### How it is built

| Part | Choice | File |
|---|---|---|
| Live cards | CopilotKit's `useRenderToolCall`, which fits our headless chat, and `useRenderTool` for each card | `components/chat/`, new |
| Asking before acting | CopilotKit `useHumanInTheLoop` for confirmations in the chat | `components/chat/ConfirmCard.tsx` |
| Workspace chat | `project-copilot` with a workspace tool set, covering only projects the signed-in user can see | `maf/tools/`, `maf/agui.py` |
| Threads without a project | `chat_threads.project_id` becomes optional, and threads gain `owner_id`, by migration | `migrations/` |
| Live run updates | The card follows the existing run event stream | `components/chat/RunCard.tsx` |

**New workspace tools**, each checking `auth.can_see_project`, and each with its own file:

| Tool | Answers |
|---|---|
| `list_projects` | Your projects, with repository, gates, and health |
| `list_pending_approvals` | What is waiting for you, across projects |
| `search_all_documents` | Find a document in any of your projects |
| `list_all_findings` | Open bugs across projects |
| `list_recent_runs` | What ran, what failed, and why |
| `usage_summary` | Tokens used and left |
| `start_workflow` | Now takes a project, and asks you first |

### Rules that do not change

| Rule | How chat keeps it |
|---|---|
| **Agents never approve** | There is no approval tool. The Approve button calls the API with **your** session, and the agent only learns the outcome |
| Workflows start only with consent | `start_workflow` shows a confirmation card first, naming the project, workflow, model, and estimated scope. Text inside a repository cannot start a run without you clicking |
| Users see only their own data | Every tool checks ownership, tested per tool |
| Documents stay governed | Chat can **propose** a document or edit, shown as a diff. It becomes a saved version only when you accept, and approval still happens at its gate |

### Chat UI, modeled on ChatGPT

| Part | Design | Component |
|---|---|---|
| **Home entry** | A large "What should we work on?" prompt at the top of Home, with suggestions from real data, such as "2 approvals are waiting" | Hero prompt, Motion |
| **Layout** | Threads on the left, conversation in the middle, and an **artifact pane** on the right | Resizable |
| **Message input** | Grows as you type, with attachments, `@` for projects and documents, `/` for commands, a model and agent picker, and a stop button | Tiptap mention, Command |
| **Streaming** | Text appears smoothly, with code highlighting and copy, and tables rendered as tables | react-markdown, CodeMirror |
| **Agent activity** | A collapsible "Working" line, showing each step: reading, searching, or calling a tool, with duration | Accordion, Motion |
| **Messages** | Copy, regenerate, edit and resend, and show which model and tokens were used | Hover actions |
| **Citations** | Answers link to the file and line, or document section, they rely on. Selecting one opens it in the pane | Popover |
| **Threads** | Search, rename, pin, delete, and group by date and project | Sidebar |
| **Everywhere** | A floating assistant button on every page, aware of the page you are on | Sheet |
| **New window** | As today, with the same features | |

### A card for each feature

| Feature | You ask | Card shown in the chat | Actions on the card |
|---|---|---|---|
| Portfolio | "How are my projects?" | Project summary grid, with gates and findings | Open project |
| Approvals | "What needs me?" | Approval list, with confidence scores | Approve, Send back, Open |
| One approval | "Show Gate 2" | The decision panel, with issues | Approve as yourself |
| Repository | "Connect owner/repo" | Clone progress, then stats | Open, Scan |
| Sandbox | "Is my sandbox ready?" | Sandbox status | Re-sync |
| BA Studio | "Write a BRD for this" | Confirmation, then live run card | Start, Cancel |
| Documents | "Open the BRD" | Document card, opening in the pane | Edit, Download, Review |
| Document edits | "Shorten the scope section" | **Diff, with accept or reject** | Accept, Reject |
| Gherkin | "Add a scenario" | Scenario card with validity | Accept, Open |
| Bug Scan | "Scan this repo" | Live run card, then a severity chart and top findings | Fix, Fix all, Dismiss |
| One finding | "Explain this bug" | Code snippet, cause, and fix | Fix on a branch |
| Feature Builder | "Add a savings tool" | Confirmation, live run card, then a diff with verdict | Approve, Send back |
| QE lifecycle | "Run QE" | **Live pipeline graph**, with the current agent and skill | Open each stage |
| Test results | "What failed?" | Pass and fail chart, with causes and fixes | Open evidence |
| Traceability | "What is not covered?" | Coverage bar and gaps | Open matrix |
| Governance | "Check the ledger" | Integrity result, and gate timeline | Open ledger |
| Observability | "Why did that run fail?" | Failure card, with error code and fix | Retry stage, Copy diagnostics |
| Agents | "How is the bug reviewer scoring?" | Agent card, with scores and trend | Open agent |
| Prompts | "Show prompt changes" | Version diff | Open |
| Usage | "How many tokens are left?" | Usage bars by day, week, and month | |
| Users (admin) | "Who is near their limit?" | User table | Open user |
| Settings | "Is everything healthy?" | Doctor report | Open Settings |
| Skill Studio | "Make a skill from this BRD" | Confirmation, live run card, then a skill card with scores | Open, Review results, Publish |
| Skill results | "Is my skill better than no skill?" | With and without comparison | Open results |

### The live run card

| Shown | Detail |
|---|---|
| Stages | A compact pipeline with status icons, using the same data as QE Studio |
| Right now | "`test-design-architect` is using `designing-test-cases`, waiting for the model, 14s" |
| Why | The reason this step runs, from the workflow definition |
| Numbers | Elapsed time and tokens, updated live |
| Documents | Cards appear as they are created, and open in the pane |
| Approval | The decision panel appears inside the card when a gate is reached |
| Failure | Error code, what to do, and **Retry failed stage** |

**Moving away from the page does not stop a run.** Reopening the thread shows its current state, from stored events.

## Part 8: Design system and component upgrades

### Foundations

| Element | Today | New |
|---|---|---|
| Color | Tailwind grays, one indigo | Tokens for surface, text, border, and status, using `color-mix()`, in light and dark, checked for 4.5:1 contrast |
| Type | System fonts | **Inter** for text and **JetBrains Mono** for code, bundled through Next.js, so nothing loads from a font host |
| Spacing and radius | Mixed | 4px scale, three radius sizes |
| Elevation | Borders only | Soft layered shadows and subtle borders |
| Motion | None | 150 to 250ms transitions, spring effects on cards, and none when reduced motion is set |
| Icons | Lucide | Lucide, kept, with consistent size and weight |

### Each shared component

| Component | Today | Upgrade | Interaction added |
|---|---|---|---|
| Button | Solid and outline | Primary, secondary, ghost, danger, and icon, with press effect | Loading state, keyboard shortcut hint |
| Card | Bordered box | Levels of emphasis, with header and footer areas | Hover lift when clickable, whole card clickable |
| Badge | Colored text | Status pill with icon and shape, so meaning never relies on color alone | Tooltip explaining the status |
| Input and select | Plain | Floating validation, helper text, and searchable select | Inline errors, clear button |
| Table | Plain HTML | TanStack Table | Sort, filter, resize, sticky header, row selection, and export |
| Tabs | Text underline | Animated indicator | Remembers choice, arrow keys |
| Dialog | Basic | Modal and side Sheet | Focus trapped, Esc closes |
| Toast | Single | Sonner stack | Undo and action buttons |
| Empty state | Dashed box | Illustration, explanation, and the next action | Direct button |
| Loading | Spinner | Skeleton in the content's shape | No layout shift |
| Error | Red text | Error card with code, cause, and fix | Retry, Copy diagnostics |
| Tooltip | Browser title | Styled, with delay | Works on keyboard focus |
| Metric tile | Number and label | Number, trend line, and change | Count-up, opens the detail |
| Progress | None | Bar, ring, and stepper | Live updates |
| Timeline | None | Shared vertical timeline | Expandable items |
| Date picker | Browser input | Date range picker | Presets |
| File upload | Browser input | Dropzone with progress and checks | Drag and drop |
| Navigation | Text list | Icon rail with groups | Collapse, badges, Cmd+K |
| Notifications | None | **Bell with a list**: approvals, finished runs, and limits | Mark read, opens the item |

## Part 9: Skill Studio

A new page where a person turns requirements into an agent skill, tests it against real prompts, and improves it until the numbers and a human agree. It follows the [Agent Skills specification](https://agentskills.io/specification.md), the [evaluation guide](https://agentskills.io/skill-creation/evaluating-skills.md), and Anthropic's [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator) (commit `ca45fc4`, Apache 2.0), rebuilt on MAF in Python.

### Why skill-creator cannot be used as it is

| skill-creator relies on | Why it does not work here | MAF version |
|---|---|---|
| The `claude -p` command for trigger tests | Not on the server, and tied to one product | The model through your proxy, with MAF's skill format |
| Subagents in a coding session | A web app has none | A fresh MAF `Agent` per run, which gives the same clean context |
| A local HTML viewer | Separate from the app, and stores nothing | A results page in the app, with stored feedback |
| Files in a workspace folder | Not versioned or audited | Immutable versions and the ledger, with the same folder layout on export |

The logic is ported, not copied, and `NOTICE` credits the source as Apache 2.0 requires.

### What I measured on your endpoint

These throwaway tests used one small skill on `deepseek-v4-flash-global`, so they are a first signal rather than a benchmark.

| Test | Result | What it means for the design |
|---|---|---|
| MAF `SkillsProvider`, full tool loop, 3 prompts | `load_skill` called for 1 of 3. **No answer used the skill.** The model also called tools that do not exist, until MAF stopped it after 3 errors | Do not depend on it on this model. A live check decides per model |
| `SkillsProvider` with default settings | Paused for approval on `load_skill` | Approvals must be set on purpose, as the PDF says on page 248 |
| Skill text placed in the message | **6 of 6** skill facts appeared, against 1 of 6 without the skill | Output evaluations are reliable this way, and show a clear difference |
| Picking from names and descriptions, should use the skill | 6 of 6 correct | Trigger tests work this way |
| Same, with 2 near-miss prompts | **4 of 6 wrongly used the skill** | The test finds a description that is too broad, which is its purpose |
| Same prompt sent twice | Identical reply, in 0.36s | Repeated runs need the cache turned off, or spread figures mean nothing |

### Mapping to MAF

From `agent-framework.pdf` pages 228 to 254, checked against the installed package (`agent-framework` 1.24).

| Skill Studio need | MAF feature | How it is used |
|---|---|---|
| Read and check a skill folder | `FileSkillsSource` | If MAF cannot load it, it fails validation. This is the real test of the format |
| Skill format fields | `SkillFrontmatter` | Name, description, license, compatibility, metadata, and allowed tools |
| Offer skills to an agent | `SkillsProvider` | Used on models that pass the live check. Otherwise code does the same two steps |
| Built-in plus user skills | `AggregatingSkillsSource`, `DeduplicatingSkillsSource` | One list, first name wins, so a user skill cannot replace a built-in one |
| Who sees which skill | `FilteringSkillsSource` | By user, project, and agent |
| Detect that a skill was used | `@function_middleware` on `load_skill` | Records and stops the call, for the live trigger test |
| Run a script safely | `SkillScriptRunner`, our own | MAF calls its sample subprocess runner unsuitable for production (page 235), so ours adds a timeout, `clean_env()`, and no shell |
| The workflow | `WorkflowBuilder`, through the existing `Definition` and `StageSpec` | Same engine, live log, and token limits as other workflows |
| Human decisions | `ctx.request_info` | Same approval cards, signed by the account |
| Survive a restart | `FileCheckpointStorage` | Long evaluation runs resume |
| Clean context for each run | A new `Agent` per run | With and without the skill never share memory |
| Assertions by code | `LocalEvaluator`, `evaluator` | Plugs in the checks below |
| RAGAS | `Evaluator`, `EvalResults`, `EvalScoreResult` | The evaluator from Part 3 |

### Agents

Named in the plugin's style, each with one file, one prompt, and one eval file.

| Agent | Source in skill-creator | Job | Output checked by code |
|---|---|---|---|
| `skill-author` | `SKILL.md`, "Capture Intent" and "Improving" | Interview, draft, write test cases, and improve | Spec validator and source traceability |
| `skill-executor` | Test runs | Does the test prompt, with or without the skill, with no tools | Output and tokens recorded |
| `skill-grader` | `agents/grader.md` | Passes or fails each assertion, with evidence, and criticizes weak assertions | **Quoted evidence must exist in the output, or it is a FAIL** |
| `skill-comparator` | `agents/comparator.md` | Judges outputs A and B without knowing which is which | Labels are shuffled by code and revealed afterward |
| `skill-analyzer` | `agents/analyzer.md` | Explains the patterns code found | Numbers come from code only |
| `description-optimizer` | `scripts/improve_description.py` | Rewrites the description from failed queries | 1024-character limit, and it never sees held-out queries |

The grader uses the judge model from Part 3 when one is set, because a model grading itself is a weak check.

### The workflow, step by step

Two workflows, `maf/workflows/skill_create.py` and `maf/workflows/skill_eval.py`, so an existing skill can skip straight to evaluation.

| Step | skill-creator or guide | Stage | What happens | Who decides |
|---|---|---|---|---|
| 1 | Capture Intent | `capture` | Reads the source. Finds what the skill does, when it applies, and its output, and asks about gaps | **S0: you answer and confirm** |
| 2 | Write the SKILL.md | `draft` | Writes `SKILL.md` and references. Validator runs, and failures go back once | |
| 3 | Test Cases | `test_set` | Writes 2 to 3 realistic prompts, including an edge case, with expected outputs | **S1: you edit and approve** |
| 4 | Spawning runs | `run` | Each prompt runs with the skill, and without it or with the last version, in parallel within the model limit | |
| 5 | Capture timing | `run` | Real tokens and duration saved per run | |
| 6 | Grading | `grade` | Code checks first, then the grader for the rest | |
| 7 | Aggregating | `aggregate` | Code computes mean, spread, minimum, maximum, and difference | |
| 8 | Analyzing patterns | `analyze` | Code flags the patterns below, and the analyzer explains them | |
| 9 | Unit tests | `verify` | Script tests, plus the deeper metrics you chose | |
| 10 | Human review | `review` | You read each output and leave feedback | **S2: improve, or accept** |
| 11 | Iterating | `improve` | The author revises from failed checks, feedback, and transcripts, then returns to step 4 as a new iteration | |
| 12 | Description Optimization | `optimize` | Runs the trigger test below, optional | **S3: you approve the queries, then the result** |
| 13 | Package | `publish` | A new approved version, and a `.skill` file | **S4: you publish** |

Every step writes to the ledger. Agents never decide S0 to S4.

### Starting points

| Source | How | Reuses |
|---|---|---|
| **BA document** | Pick an approved BRD, PRD, stories, or Gherkin from any of your projects, at a set version | `documents.get`. The skill records its id, version, and SHA-256, so you can see when the source has changed |
| **Write it in BA Studio** | **Create a skill from this document** on a BA document, or a link from Skill Studio to write one first | BA workflow, templates, and review |
| **Upload a requirements file** | `.md`, `.txt`, `.pdf`, or `.docx`, saved as a document | `core/files.extract_text` and upload checks |
| **Type a brief** | A text box | Saved as a document, so it is versioned too |
| **Import an existing skill** | A `.skill` or `.zip` file, to evaluate or improve | `ingest.safe_extract`. Treated as untrusted |

### Evaluation layers

Each layer answers a different question, and they run cheapest first.

| Layer | Question | Method | Cost |
|---|---|---|---|
| **1. Format unit tests** | Is it a valid skill? | Code: all spec rules, including name matching its folder, no double hyphens, field limits, and valid YAML. Also under 500 lines, references that exist, no angle brackets, and MAF loads it | Free |
| **2. Content checks** | Is it safe and clean? | Code: no secrets, leftover template text, or hidden text. Runs `redact()` and flags instructions aimed at the agent from source content | Free |
| **3. Script unit tests** | Do bundled scripts work? | `pytest` through `run_suite`. **Zero tests executed is INCONCLUSIVE.** `assert True` is refused, using our existing checks | Run time |
| **4. Trigger test** | Does it activate at the right time? | 20 queries, half near misses, 3 runs each, passing above 0.5. **Precision, Recall, and F1** | Tokens |
| **5. Output evaluation** | Is the result better than no skill? | With and without, graded by assertion. **Pass rate, time, tokens, and the difference** | Tokens |
| **6. Requirements coverage** | Did it capture the requirements? | Each source requirement traced to the skill, and each skill rule traced back, for **Recall, Precision, and F1** | Tokens |
| **7. RAG metrics** | Are outputs grounded? | **Groundedness** by code. **Faithfulness**, **Context Recall**, and **Response Relevancy** with RAGAS, with the skill as context | Tokens |
| **8. Safety evaluation** | Does it resist bad input? | Prompt injection cases from our existing evals, run with the skill loaded | Tokens |
| **9. Blind comparison** | Is the new version really better? | `skill-comparator`, on demand | Tokens |
| **10. Human review** | Does it miss the point? | Your feedback per case | Your time |

**The trigger test, as skill-creator does it:** queries are split 60% train and 40% held out, and at most 5 rounds run. **The best description is chosen by held-out score**, so it does not simply memorize the queries.

**Patterns flagged by code, from the guide:**

| Pattern | What it means | Shown as |
|---|---|---|
| Passes both with and without the skill | The assertion proves nothing | "Remove or replace" |
| Fails in both | Broken assertion, or too hard | "Fix this first" |
| Passes only with the skill | The skill's real value | "Skill adds value" |
| Results differ across runs | Flaky, or unclear instructions | "Tighten instructions" |
| A run costs 3 times the others | Wasted work | "Read the transcript" |

**Honest results.** No test run shows INCONCLUSIVE, never a pass. A score from fewer than 3 runs shows no spread. A skill that needs real tools, such as creating a chart file, cannot be fully judged by a tool-free run, so those assertions show INCONCLUSIVE with the reason.

### Storage and files

| Item | Design | Reuses |
|---|---|---|
| Skill versions | Document kind `skill`. `SKILL.md` is the content, with other files in its data. Each save is immutable, with SHA-256, author, and prompt reference | `core/documents.py`, so diff, restore, and history work at once |
| Test cases | `evals/evals.json`. Imports both `assertions` from the guide and `expectations` from skill-creator, and exports `assertions` | Inside the version |
| Iterations and runs | New tables `skill_iterations` and `skill_runs`: configuration, output, tokens, duration, grades, and feedback | Migration |
| Disk copy | `data/projects/<id>/skills/<name>/v<N>/`, written through `safe_path` so MAF can load it | `core/files` |
| Export | ZIP in the guide's layout: `iteration-N/eval-x/with_skill/`, `timing.json`, `grading.json`, `benchmark.json`, and `feedback.json` | Works with other tools |
| Package | `.skill` file, leaving out `evals/` and caches as skill-creator does. Built with `zipfile`, so it works on every system | |

| New file | Holds |
|---|---|
| `core/skills.py` | Validation, disk copy, import, and package |
| `maf/skill_evals.py` | Trigger test, benchmark maths, and pattern flags |
| `maf/workflows/skill_create.py`, `skill_eval.py` | The workflows |
| `maf/agents/skill_*.py`, `description_optimizer.py` | The 6 agents, with prompts and evals |
| `api/skills.py` | Routes, each with an ownership rule in `core/auth.py` |
| `app/skills/` | The screens below |

### Security

A skill is **instructions that agents obey**, so it is the most sensitive thing a user can create here.

| Risk | Control |
|---|---|
| Hidden instructions in a requirements file reach a skill | Source content is untrusted data for `skill-author`. Layer 2 flags it, and a person reads the skill at S1 and S4 |
| A published skill misleads an agent | Skills are off until a named person publishes them. User skills never reach workflow agents unless the admin attaches them |
| A skill grants itself tools | `allowed-tools` is recorded but **ignored**. Each agent's tool list stays fixed in code |
| A bundled script is hostile | Scripts never run automatically. They need approval, a timeout, `clean_env()`, and no shell, and are off on Azure until sandbox jobs exist (decision 18) |
| A hostile ZIP | `safe_extract`, plus limits on file count and size. MAF's own archive limits (page 241) are the starting values |
| Another user's skill | Ownership checks on every route, tested for each |
| A skill replaces a built-in one | First name wins, and built-in skills load first |

### Screens

| Screen part | Design | Component | Interaction |
|---|---|---|---|
| **Skills page** | Tabs: Built-in, Mine, Published. Each card shows name, version, status, and scores | Cards, Tabs | Search, filter, **New skill** |
| **Skill card** | Tiles: Format, Trigger F1, With-skill pass rate, and difference from no skill | Metric tiles, Sparkline | "Not measured" until run |
| **New skill wizard** | Stepper: Source, Intent, Draft, Test cases, Evaluate | Stepper | Saved at each step |
| **Source step** | Four cards: BA document, upload, write in BA Studio, or import | Dropzone, searchable picker | Preview before choosing |
| **Intent step** | The agent's understanding and its questions | Form | Answer in place, sign S0 |
| **Editor** | File tree, editor, and live preview, with validation as you type | CodeMirror, Tiptap, Resizable | Errors at their line |
| **Description field** | Character count to 1024, with hints | Input | Warns if it only says what, and not when |
| **Test case grid** | Prompt, expected output, files, and assertions | TanStack Table, Dropzone | Inline edit, add, and **Suggest assertions** |
| **Token estimate** | Runs, tokens, and limit left, before starting | Dialog | Refuses if over your limit |
| **Live run matrix** | Each case against with and without, each cell showing live status, tokens, and time | Grid, Motion | Select a cell to watch its log |
| **Outputs tab** | One case at a time: prompt, output, grades with evidence, and feedback box | Tabs, Accordion | Arrow keys, autosaved feedback, and last iteration's output |
| **Benchmark tab** | With, without, and difference, per case, with pattern flags | TanStack Table, Recharts | Sort, and open the flagged case |
| **Trigger tab** | Each query with its trigger rate, train and held-out F1, by round | Table, Line chart | Edit queries, and see before and after |
| **Coverage tab** | Requirement to skill section, with gaps | Matrix | Opens the source and section |
| **Metrics tab** | Faithfulness, Groundedness, Recall, and F1 | Metric tiles | Worst cases first |
| **Iterations** | Timeline of versions, with scores and what changed | Timeline, react-diff-view | Compare any two, or restore |
| **Compare** | A and B side by side, revealed after judging | Resizable | Blind comparison |
| **Publish panel** | Checklist of all layers, with a warning for anything inconclusive | Dialog | Sign S4, then download |
| **Use panel** | Which agents use it, and on and off switches | Switch | Admin only for shared use |
| **Failures** | Error card with code, cause, and fix: `AQE-SKILL-001` format, `002` import, `003` script, `004` nothing executed | Error card | Retry the stage |

### How this is tested

| Test | Proves |
|---|---|
| Each spec rule, valid and invalid, offline | The validator matches the specification |
| Every valid example from the spec loads in MAF `FileSkillsSource` | We agree with MAF |
| Benchmark maths on known numbers | Figures are right |
| Evidence not found in the output, using `ScriptedClient` | The grade becomes FAIL |
| No runs, and no tests | INCONCLUSIVE, never a pass |
| With and without runs share nothing | Clean context |
| Held-out queries are absent from the optimizer's prompt | No leakage |
| Hostile ZIP, hidden instructions, another user's skill, and `allowed-tools` asking for more | Each refused or flagged |
| `.skill` export reloaded by MAF, on Windows, macOS, and Linux | Packages work everywhere |
| **Real end to end:** finance repo BRD to published skill, in a browser, on the real model | The loop works, with real numbers reported whatever they show |
| **Real benchmark:** three skills with known strengths, one deliberately weak | The evaluation can tell good from bad |

## Part 10: Review of this plan

I reviewed the whole plan twice against the code, the latest end-to-end runs, and live measurements. Each gap is now covered, with its phase.

### Serious gaps

| Gap | Why it matters | Fix | Phase|
|---|---|---|---|
| **Approver name is typed in by hand** (`DecisionIn.by`) | Anyone signed in can approve as anyone, which undermines the audit trail now that accounts exist | The signer is taken from the signed-in account, and the typed field goes. Gates and agent controls too | 1 |
| **Any user can approve their own gates** | The plugin expects roles such as QE Lead and Platform Admin at sign-off | Roles per user: Admin, QE Lead, BA, Developer, Viewer, and which role may sign each gate. Configurable, defaulting to the project's owner | 3 |
| **Repository code still shares the machine** | One user's test could read another's data | Keep untrusted users out until sandbox jobs exist, as in `docs/AZURE_SYSTEM_DESIGN.md`. **Sandbox jobs are not in this plan's phases. Decide below** | Decision|
| **Live API key is in old Git history** | Already reported | You rotate the key. History can be rewritten if you approve | Decision|
| **Fix all marks findings fixed even if tests fail** | Seen in testing, after approving a FAIL | Mark as fixed only when the verdict is not FAIL. Otherwise "fix attempted" | 1 |
| **Editing a test case table does not change its CSV export** | Exports use stored data, so the two can disagree | Parse the table back into data on save | 1 |

### Product gaps

| Gap | Fix | Phase|
|---|---|---|
| Users cannot change their own password | Account page, with password change | 3 |
| Projects cannot be shared | Project members with roles, and the admin can transfer ownership when someone leaves | 3 |
| No notifications | Bell, as in Part 8 | 8 |
| No onboarding | First-run checklist: model, repository, first scan | 11 |
| Runs can collide | One active run per project and workflow kind, or a clear queue message | 2 |
| Too many test cases: 119 for 15 requirements | Cap by risk, with P0 and P1 first, and the admin can set the limit | 5 |
| Generated tests cost a lot on large designs | Show an estimate before G3 and G4 | 5 |
| No cost view | Tokens are shown, not money. Show ₹ when the proxy reports cost | 3 |
| Mobile and small screens | Usable to 768px, and read-and-approve on phones | 8 |
| Single sign-on | Not now. The sign-in layer allows adding Microsoft Entra later | Later|

### Technical gaps

| Gap | Fix | Phase|
|---|---|---|
| Observability loads up to 5,000 rows per source into memory | Page and filter in SQL, with indexes | 2 |
| Chat stream hangs for minutes with no explanation | Show elapsed time and a stall warning at 60 seconds, with Stop | 10 |
| Chat stream and Azure's 230-second limit | Send keep-alive messages through the chat stream | 10 |
| Renaming agents breaks stored history | Migration covers `prompts`, `agent_calls`, `tool_calls`, `agent_settings`, `evaluations`, and `chat_threads`, with a test on a copy of real data | 1 |
| `ToolApprovalMiddleware` exists in MAF | Use it for tool approvals in chat where it fits, rather than building that | 10 |
| UI rewrite could break browser tests | Keep `data-testid` values, and update tests in the same phase | 8 onward |
| No automated accessibility check | `axe` in browser tests for every page, to WCAG 2.1 AA | 8 onward |
| No visual check | Screenshot comparison on key screens | 8 onward |
| CI has no browser tests, as they need the real model | Add browser tests in CI that need no model: sign-in, navigation, and access, while real-model runs stay local and before each release | 2 |
| Backup and restore are untested | A script and a test that restores a backup | 12 |
| Old `data/sdlc.sqlite3` projects | Decide below | Decision|

### Found in the second review

| Gap | Evidence | Fix | Phase |
|---|---|---|---|
| **The proxy returns stored replies for an identical prompt** | The same prompt sent twice gave the same reply, the second in 0.36s | Retries, repeated evaluations, and spread figures would measure nothing. Send the proxy's no-cache option on these calls, and add a unique marker if it is ignored. Test it on the real proxy | 2 |
| **Generated tests score high, then fail** | One full run: `tests_review` 95, then 92 of 124 tests failed and coverage was 50%. The latest: 22 of 86 failed, with coverage at 85%. Results vary between runs | Cap the score once results exist, as a code change now does | 5 |
| **Generated tests call functions wrongly** | 22 failures were `required_monthly_savings()` given a keyword it does not accept | Check each call against the real signature with `ast` before running, and send it back to its agent | 5 |
| **Tests fail for setup reasons** | 20 async failures in that run and 5 in the latest, plus 12 from the app's own rate limit returning 429 | Add a setup step that finds async plugins and rate limits, and classify the rest as environment, not defects | 5 |
| **A skill is instructions that agents obey** | A requirements file becomes a skill, and a skill reaches an agent. Hidden text could travel that route | See "Security" in Part 9. Nothing reaches an agent without a named person publishing it | 7 |
| Runs and documents need a project | `runs.project_id` and `documents.project_id` are required | A skill library project per user, so nothing about them changes. Decision 17 | 7 |
| Plan moves files, which needs your permission | `CLAUDE.md` rule | Listed below. Decision 21 | 1 |

### Files this plan moves or replaces

Approving decision 21 approves exactly this list. **Nothing else is moved or removed, and history is kept with `git mv`.**

| From | To | Phase |
|---|---|---|
| `maf/agents/*.py`, `prompts/*.md`, and `evals/*.json` under old agent names | Plugin names, as listed in Part 1 | 1 |
| `prompts/gherkin_author.md`, `prompts/doc_reviewer.md`, their agents, and evals | Merged into `business-analyst` and `confidence-reviewer`, then removed | 1 |
| `maf/evals.py` | `maf/evals/__init__.py`, beside the new metric files | 6 |
| The block editing code inside `components/DocumentEditor.tsx` | Replaced by the Tiptap editor, if the round-trip test passes | 11 |
| Screens and shared components | Rewritten in place, keeping their paths | 8 onward |

### Corrections to earlier parts

| Part | Change|
|---|---|
| Part 1 | Chat skills use `SkillsProvider`, but **must be tested on your endpoint**, since it loses older tool results. If it fails, chat also gets skills injected into its messages|
| Part 3 | Metrics need the benchmarks first, so they follow accuracy work, as ordered below|
| Part 5 | Limits apply to chat, runs, and Skill Studio evaluations a user starts. The built-in agent evaluations an admin runs do not count against a user's limit|
| Part 6 | Rich editing also opens in the chat's artifact pane, using one shared component|

## What is not included

| Left out | Why | When to add |
|---|---|---|
| Sandbox jobs on Azure, PostgreSQL, and Blob Storage | Designed in `docs/AZURE_SYSTEM_DESIGN.md`, but a separate piece of work | Before admitting untrusted users. Can be added, see decision 14 |
| Multi-tenant organizations | One organization is enough | When selling to several companies |
| Single sign-on | Not needed yet | When a company requires it |
| Voice in chat, and ChatGPT-style memory across users | Not needed | If requested |
| Real-time co-editing of documents | Large, with little need so far | If several people edit at once |

## Delivery order

Each phase ends with tests, a commit, and a push, with progress written to `progress.md` as it happens. Size is relative, not a time estimate.

| Phase | Size | Work | Finished when |
|---|---|---|---|
| 1. Names and integrity | M | Plugin names with migration, signer from the account, Fix all and CSV corrections | All tests pass, and a real data copy migrates |
| 2. Errors and logs | M | Typed errors, diagnostic records, saved logs, retry a stage, partial results, error pages, SQL paging, one active run, CI browser tests, proxy cache control | Every error code tested on purpose |
| 3. Models, limits, and access | M | Model list, allowed models, daily, weekly, and monthly limits, usage page, roles, project members, account page | A real run with two models, and each limit tested |
| 4. Skills | M | Copy skills, inject them in workflows, chat skill selection, model check for `SkillsProvider` | Each agent's evals pass with its skill |
| 5. Accuracy | L | Per-case confidence, code-computed verdicts, gate reopening, data stage, defect records, case limits, signature checks, setup step | Finance repo re-run, with before and after numbers |
| 6. Evaluations | L | Benchmarks, deterministic metrics, RAGAS, stored scores, docs | First real scores for every agent, with tokens used |
| 7. Skill Studio engine | L | Skill storage, spec validator, both workflows, 6 agents, trigger and output evaluations, benchmark, packaging, API | A real skill built from a real BRD, with honest with and without results |
| 8. UI foundation | L | Design tokens, shared components, app frame, Cmd+K, notifications, skeletons, accessibility tests | Every page works in the new frame |
| 9. Skill Studio screens | M | Wizard, editor, test case grid, live matrix, results viewer, versions, publishing | Browser test of the full loop on the real model |
| 10. Chatbot | L | Home and floating chat, artifact pane, all feature cards, live run card, workspace tools | Browser tests on the real model |
| 11. Key screens | L | QE live graph, approval panel, home bento, Documents tab with rich editor and upload, agent score cards, onboarding | Browser tests and screenshots |
| 12. Remaining screens | M | The rest of Part 2, backup and restore | Browser tests and screenshots |
| 13. Final check | S | Full tests on all three systems, docs updated, deploy guide rechecked, Azure package includes `skills/` | Green CI and a real finance run |

## Definition of done

Each phase is finished only when all of these hold:

| Check | Requirement |
|---|---|
| Tests | Offline tests pass on Windows, macOS, and Linux in CI |
| Real run | Changed flows run on the real model and `personal-finance-mcp`, with results reported honestly, including failures |
| Rules | `CLAUDE.md` is followed: no invented data, no weakened tests, and every route has an access rule |
| Security | Tests show secrets and login details absent from logs and storage |
| UI | Works in light and dark, passes `axe`, works by keyboard, and has been checked by eye from screenshots |
| Docs | `specs.md`, `tasks.md`, `maf-guide.md`, the docs site, and `docs/PROJECT_STRUCTURE.md` are updated |
| Tracking | `progress.md` records each step and decision |

## Decisions for you

Approve as recommended, or reply with changes. **Only decision 6 needs something from you before phase 6.**

| # | Decision | Recommendation |
|---|---|---|
| 1 | Keep 4 platform agents with plugin-style names, as "identical to the plugin" cannot cover BA Studio, Bug Scan, Feature Builder, or chat | Yes |
| 2 | Merge `doc_reviewer` into `confidence-reviewer`, and `gherkin_author` into `business-analyst` with a skill | Yes |
| 3 | Verdict rule: plugin's strict approval at 100 only, which means more revisions and tokens | Yes for gates, but with a human able to approve a REVISE |
| 4 | Move to shadcn/ui and the libraries in Part 2 | Yes |
| 5 | Order: phases 1 to 6 first, then UI, since accuracy is your stated top goal | Yes |
| 6 | Judge model for RAGAS, which should differ from the agents' `deepseek-v4-flash-global`. **I need a model name from your proxy** | A stronger model, used only for evaluations |
| 7 | Who checks the answer key labels | You, or someone who knows these repositories |
| 8 | Rename "high risk" to "Impact: changes code" | Yes |
| 9 | How often RAGAS runs | On demand and when a prompt changes, to control tokens |
| 10 | Save full model conversations and rejected replies. They are masked for secrets, but hold repository code | Yes, removed after 30 days |
| 11 | Time zone for daily, weekly, and monthly resets | Asia/Kolkata |
| 12 | Should users pick a model per run, or only admins? | Users pick from their allowed list |
| 13 | Rich editor as the default view on Documents | Yes, with Read and Split a click away |
| 14 | Build Azure sandbox jobs, PostgreSQL, and Blob Storage as well | Yes, as a follow-on after phase 13, unless untrusted users arrive sooner |
| 15 | Rewrite Git history to remove the old API key | Rotate the key first, then yes if others have access to the repository. This needs a force push, so only with your explicit yes |
| 16 | Import projects from the old `data/sdlc.sqlite3` | No. They predate this design, so keep the file as an archive |
| 17 | Where skills live: a private **Skill library** project for each user, created on first use, so runs, versions, limits, and logs all work unchanged | Yes |
| 18 | Skill scripts: run only after a named person approves them, with a timeout and no platform secrets. **Off on Azure** until sandbox jobs exist | Yes |
| 19 | Who can attach a published skill: its owner for their own chat. Only the admin for shared use or workflow agents | Yes |
| 20 | Skill evaluation defaults: 3 test cases and 1 run each at first, 3 runs when benchmarking, 20 trigger queries with 3 runs each, and at most 5 improvement rounds, always with a token estimate first | Yes |
| 21 | Approve the file moves and removals listed in Part 10 | Yes |
