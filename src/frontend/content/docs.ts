// Documentation pages. Each page is Markdown; ## headings fill the "On this page" list.
export type DocPage = { slug: string; title: string; summary: string; body: string };
export type DocGroup = { title: string; pages: DocPage[] };

export const groups: DocGroup[] = [
  {
    title: "Get started",
    pages: [
      {
        slug: "introduction",
        title: "Introduction",
        summary: "What Agentic QE Platform does and how a project flows through it.",
        body: `Agentic QE Platform is a workspace for business analysts and developers. It turns briefs into requirements, scans real repositories, builds features and fixes on separate branches, and runs a full test lifecycle with a person approving each stage.

## What you can do

| Area | What it gives you |
|---|---|
| BA Studio | Requirements from your own templates, with an independent review and validated Gherkin |
| Bug Scan | A review of the whole repository. Every finding quotes real code |
| Feature Builder | Code changes on a separate branch, checked by running your real tests |
| QE Studio | Requirements, plan, design, generated tests, execution, and traceability through six approval gates |
| Copilot | A chat that knows the project's documents, code, and history |
| Confidence review | An independent score beside each stage, with checks by code that can lower it |
| Observability | A record of every agent, tool, and decision |
| Access and limits | Roles, project members, several models, and token limits for each person |

## How it stays trustworthy

- **Evidence is checked by code.** A finding whose quote is not in the file is dropped, and Gherkin must pass the official parser.
- **People approve.** Agents cannot pass a gate. Every decision records a name.
- **Nothing is invented.** If a model or repository is missing, you get a clear error. Empty pages stay empty.
- **Zero tests is not a pass.** A run that executes no tests reports **INCONCLUSIVE**.

## Where to go next

Start with [Install and run](/docs/install), then follow [Your first project](/docs/first-project).`,
      },
      {
        slug: "install",
        title: "Install and run",
        summary: "Run the platform on Windows or macOS with one double-click.",
        body: `## Requirements

| Software | Version |
|---|---|
| Python | 3.12 or newer |
| Node.js | 20 or newer |
| Git | Any recent version |

You also need an OpenAI-compatible model endpoint and API key.

## Start the app

| System | Do this |
|---|---|
| Windows | Double-click \`start-windows.bat\` |
| macOS | Double-click \`start-mac.command\`. If macOS blocks it, right-click it and choose **Open** |
| Any terminal | Run \`python scripts/dev.py up\` |

The first run installs everything and takes a few minutes. The app then opens at http://127.0.0.1:3000. Press **Ctrl+C** in that window to stop it.

## Connect a model

1. Open **Settings**.
2. Enter the base URL, model name, and API key. The key is encrypted at rest.
3. Choose **Test connection**. It sends a real request and reports the reply and latency.

## If a port is busy

Set \`ATLAS_PORT\` for the API and \`ATLAS_UI_PORT\` for the UI, then start again.`,
      },
      {
        slug: "first-project",
        title: "Your first project",
        summary: "From an empty workspace to a reviewed change.",
        body: `## 1. Create the project

On **Projects**, choose **New project**. Give it a name, and add a Git URL or ZIP now or later.

## 2. Check the repository

Open **Repository**. You see the commit, files, languages, test runners, and the project's sandbox.

## 3. Follow the Next line

**Overview** shows a **Next** line with the most useful step. Select any card to open its tab.

## 4. Scan for bugs

Open **Bug Scan** and choose **Scan repository**. Static analyzers and an agent review every source file, and the result shows how many files were reviewed.

## 5. Fix and review

Choose **Fix on a branch** for one finding, or **Fix all** for the most severe ones. The tests run, and you review the diff and verdict before anything is committed.`,
      },
    ],
  },
  {
    title: "Features",
    pages: [
      {
        slug: "repository",
        title: "Repository and sandbox",
        summary: "How code enters a project and where work happens.",
        body: `## Connect code

| Source | How |
|---|---|
| Public Git | Paste an HTTPS URL or \`owner/repo\` |
| Private GitHub | Add a fine-grained token in **Settings**, then pick the connection and repository |
| ZIP | Upload it. No Git host is needed |
| Local folder | Enter the path. It is copied, and the original is not changed |

For private repositories, the token needs read access to contents. To open pull requests, it also needs write access to contents and pull requests. Tokens are encrypted and never placed in URLs.

## What a sandbox is

Each project gets its own sandbox, shown on the Repository page.

| Part | Purpose |
|---|---|
| Full clone | The complete repository with all history |
| Worktree per run | Each change or QE run works on its own branch, so your main checkout stays untouched |
| Python environment | Installed only if you tick **Install repository dependencies** |
| Clean environment | Test code runs without this platform's secrets |

> A sandbox separates projects by folder and environment. It is not an operating system container, so only install dependencies for repositories you trust.

## Replace a repository

Choose **Replace repository**, connect another source, or use **Re-sync** to fetch the latest commit.`,
      },
      {
        slug: "ba-studio",
        title: "BA Studio",
        summary: "Write requirements from a brief, sources, and a template.",
        body: `## Generate a document

1. Write a brief, and upload any sources: .md, .txt, .pdf, .docx, .xlsx, or .pptx.
2. Choose a template, or upload your own as Markdown or Word. Generated documents keep every heading.
3. Choose **Generate document**.
4. An independent reviewer scores the draft, and Gherkin scenarios are written and validated.
5. Approve at the gate, or send it back with feedback.

## Reviewer scores

Code caps the reviewer's score when it finds missing requirement ids, vague wording, leftover template text, empty sections, or figures that are not in your sources.`,
      },
      {
        slug: "documents",
        title: "Documents",
        summary: "Edit, compare, restore, and download versions.",
        body: `## Work with a document

- **Document** shows it formatted. Select any text to edit it where it is, with a live preview.
- Tables, including Gherkin Examples, are editable grids. Change cells, then use **Add row** or **Add column**.
- **Add text**, **Add table**, and **Add image** insert new content. Images can be PNG, JPEG, GIF, or WebP, up to 10 MB, and export to Word.
- **Source** shows the raw text beside a live preview.
- **Save version** creates one version. Typing does not.
- **History** lists each version, with diffs and restore.
- **Ask reviewer** scores the current version.
- **Refine with agent** saves a new version from your instructions.

Saving an approved document returns it to draft, and invalid Gherkin cannot be saved.

## Downloads

| Document | Formats |
|---|---|
| Any | .md, .docx |
| Gherkin | .feature |
| Test cases | .csv, Jira .csv |`,
      },
      {
        slug: "feature-builder",
        title: "Feature Builder",
        summary: "Build a change on a separate branch and review it.",
        body: `## Build a change

1. Describe the change. Name any functions you require.
2. Tick **Install repository dependencies** if the tests need them.
3. Choose **Build feature**.

## What happens

The tests run first for a baseline. The agent then proposes edits, and code applies them through path, secret, and scope checks. The tests run again, and only new failures count against the change.

## Read the verdict

| Verdict | Meaning |
|---|---|
| PASS | Tests ran and none fail |
| NO NEW FAILURES | Some tests already failed before this change |
| FAIL | The change broke tests after up to three attempts |
| INCOMPLETE | Tests pass, but a named function or a new test is missing |
| INCONCLUSIVE | Tests could not run in this environment |

A red box lists any existing assertion the change altered, so check those. After you approve, you can download the changed files, push, or open a pull request.`,
      },
      {
        slug: "bug-scan",
        title: "Bug Scan",
        summary: "Review the complete repository and fix what it finds.",
        body: `## Run a scan

Choose **Scan repository**. Ruff, secret, code, and manifest scanners run with an agent review of **every source file**. Large files are read in parts. The run reports how many files were reviewed and lists any that were not, for example if the token budget ran out.

An agent finding is kept only if the code it quotes exists in the file.

## Fix findings

| Action | Result |
|---|---|
| **Fix on a branch** | Fixes one finding |
| **Fix all** | Fixes up to 15 of the most severe open findings on one branch. Run it again for the next set |
| **Dismiss** | Hides a finding you do not need |

Each fix runs your tests and waits for your review. Findings are marked as fixed when you approve.

## Diagnose an error

Paste a traceback into **Diagnose an error**, and the diagnostician finds the cause and proposes a fix on a branch.`,
      },
      {
        slug: "qe-studio",
        title: "QE Studio",
        summary: "Run the full test lifecycle with six approval gates.",
        body: `## The gates

| Gate | You approve |
|---|---|
| G0 Intake | Scope and mode |
| G1 Requirements | Requirements with verified evidence |
| G2 Plan | Risk-ranked plan |
| G3 Design | Test cases and oracles |
| G4 Generate | Generated tests. Approving lets them run on this machine |
| G5 Release | Executed evidence and verdict |

## Watch it live

The run panel shows the current stage, elapsed time, tokens, and a **live log** of each step, including while an agent waits for the model. Documents appear as cards on the right as they are created.

## Confidence reviews

An independent reviewer scores the work before every gate: discovery, requirements, the plan, each batch of test cases, and the generated tests. A score below 70 sends the work back once, automatically. Test design and generation run in batches, and each batch is reviewed. For a code change, the review runs beside the tests and is capped at 60 when they fail. The score and issues show on the approval card. If a review could not run, the card says **not run**.

## Results

Zero executed tests gives **INCONCLUSIVE**, never PASS. Healing can repair selectors and fixtures only, so real application defects stay as failing tests.

Generated tests are checked before they run: their imports must exist in your code, and they must use only plugins your repository has.`,
      },
      {
        slug: "copilot",
        title: "Copilot",
        summary: "Ask about the project, in the app or a separate window.",
        body: `## Chats

Open **Copilot** in a project, or use **Open in new window**. Pick an agent per chat. Chats are saved and can be renamed or deleted, and project memory is shared by all chats.

## Commands

| Command | Does |
|---|---|
| \`/scan\` | Starts a bug scan |
| \`/fix <finding id>\` | Fixes a finding on a branch |
| \`/gates\` | Shows gate status |
| \`/verify\` | Verifies the audit ledger |
| \`/feature <text>\` | Starts a feature |
| \`/docs <query>\` | Searches documents |

Agents can start workflows, but only people approve gates.`,
      },
    ],
  },
  {
    title: "Govern and observe",
    pages: [
      {
        slug: "approvals-governance",
        title: "Approvals and governance",
        summary: "Who decided what, and proof it was not changed.",
        body: `## Approvals

**Approvals** lists each decision waiting for you, across projects. Each one records your name, and sending back needs feedback. The stage then reruns with it.

## Governance

**Governance** shows signed gate decisions and the hash-chained audit ledger, which flags any edit or deletion.

## Who may sign a gate

The admin lists, on **Settings**, the roles that may sign each gate, G0 to G5. A gate with no roles listed can be signed by anyone who can write in the project. Your name on a decision always comes from your account. A viewer cannot sign any gate, and the administrator can always sign.

## Prompts

**Prompts** shows each agent's versions. An edit creates a new version, and older ones can be reactivated. Each output records the prompt version that produced it.`,
      },
      {
        slug: "observability",
        title: "Observability",
        summary: "Trace and debug every run, in one project or all of them.",
        body: `## Where to find it

**Observability** in the left menu covers all projects, and each project has its own page. Every run has an **Open full trace** link.

## What is recorded

| Log type | Records |
|---|---|
| Skills | The agentic-qe skill each workflow stage carries out |
| Agents | Tokens, duration, prompt version, status, and source of each model call |
| Tools | Tool name, redacted arguments, duration, and status. Refused requests are included |
| MCP tools | MCP server tools. There are none, because this app connects to no MCP server |
| Workflow steps | Stage starts and ends, test results, warnings, and errors |
| Approvals | Who was asked and what they decided |
| Guardrails | Removed prompt injections and redacted secrets |
| Audit ledger | Hash-chained record of each state change |

## Debug a run

1. Choose the run in the **Run** list.
2. Select a type, or search for a name or message.
3. Open any line for details.
4. Use **Download JSON** to save what the filters show.

The **Errors** view groups failed stages by error code and agent, with the latest message and no stack trace.

## Application log

Each day writes one file, \`data/logs/app-YYYY-MM-DD.jsonl\`, with one line per request and one per warning or error. A line never holds a request body, query string, cookie, or username, and every value is masked for secrets. An administrator downloads one day's file from **Settings**. Files older than \`ATLAS_LOG_RETENTION_DAYS\` (30 by default) are deleted.`,
      },
      {
        slug: "accounts",
        title: "Accounts and access",
        summary: "Sign in, create users, and set what each one can use.",
        body: `## Sign in

Everyone signs in first. The admin login comes from \`ATLAS_ADMIN_USERNAME\` and \`ATLAS_ADMIN_PASSWORD\` in \`.env\`. A session ends after \`ATLAS_SESSION_HOURS\` (12 by default), or after \`ATLAS_SESSION_IDLE_MINUTES\` (480 by default) with no activity. After five wrong passwords, that username is locked for five minutes.

## Roles

The admin sets each account's role on **Users**. The environment administrator is always an administrator.

| Role | What it can do |
|---|---|
| Administrator | Everything, including users, models, limits, agents, prompts, and who may sign each gate |
| QE lead | Starts work, and approves where a gate allows its role |
| BA | Writes requirements and documents, and approves where a gate allows its role |
| Developer | Starts runs and changes code on branches. The default for new accounts |
| Viewer | Reads only. Cannot start, edit, run, or approve anything, in any project |

## Projects and members

The owner of a project has full control of it. The owner adds a member on the project page by typing the exact username and choosing a role: developer, QE lead, BA, or viewer. Only the owner and the administrator see the member list. A member's rights are the lesser of their account role and their project role, so a viewer on either side cannot write. Removing a member takes effect on their next request.

Only the administrator can transfer a project, by username. The previous owner loses access, unless they are added back as a member.

## Manage users

The admin opens **Users** and sets, for each person:

| Setting | What it does |
|---|---|
| Password | Stored only as a salted hash. It cannot be read back, only replaced |
| Role | What they may do, as above |
| Models | The models they may use, and their default. See [Models and limits](/docs/models) |
| Token limits | An allocation, plus daily, weekly, and monthly limits, and limits for one model |
| Active from and until | Outside these dates, they cannot sign in and their runs stop |

Changing a password or disabling an account ends that person's sessions.

## Your account

The **Account** link in the top bar shows your role, your models, your limits, and your usage. It also changes your password. Enter your current password and a new one of at least 10 characters. Your other sessions end, and this one stays. The administrator's password is set in \`ATLAS_ADMIN_PASSWORD\`, so change it there and restart.

## What each person sees

Users see only their own projects, and the projects they are added to as members, with everything in them. The admin sees everything and is the only one who can change model settings, agents, prompts, and private repository access.

## How login details are protected

- Passwords are salted scrypt hashes, and usernames are encrypted at rest.
- Sessions are stored only as hashes, in a cookie scripts cannot read.
- Logs pass through a mask, and audit records use account ids rather than names.

Use HTTPS outside your own machine, so sign-in details are encrypted in transit.`,
      },
      {
        slug: "agents",
        title: "Agents and evaluations",
        summary: "Policy, guardrails, and quality for all 12 agents.",
        body: `## What risk means

Risk shows what an agent **could affect**, not how it is behaving.

Agents marked "Impact: changes code" are in the application because Feature Builder and Bug Scan fixes need something that changes code. They have no tools in workflows, their edits pass code guards, they work only on a separate branch, and nothing is committed until a named person approves.

| Risk | Meaning | Agents |
|---|---|---|
| Low | Handles text only | business-analyst (documents and Gherkin), confidence-reviewer (document and evidence review), principal-test-architect, test-design-architect, qa-execution-engineer (explains test results from evidence) |
| Medium | Reads code, or acts on project data in chat | project-copilot, repo-intelligence-analyst, requirements-analyst, test-automation-engineer, bug-reviewer |
| Impact: changes code | Can change code, always on a branch with a person's review | feature-engineer, defect-diagnostician |

Select any agent's card to open its page, with its details, evaluations, and recent calls.

## Controls

| Control | What it does |
|---|---|
| Tool policy | An agent receives only the tools listed for it |
| Disable | Stops an agent at once. It needs your name and goes to the ledger |
| Token limit | Caps output per model call. Each run also has a token budget |
| Secret guardrail | Removes secrets from input and output |
| Injection guardrail | Removes instruction-like text from briefs, sources, and repository files |

## Evaluations

**Run all evaluations** runs each agent's cases on the real model, and stores results per prompt version. Model replies vary, so an occasional case can fail between runs.

There are 28 cases across 12 agents today:

| Check | What it proves |
|---|---|
| Contains, does not contain | Required text is present, and invented text is absent |
| JSON schema | The reply is usable by the next step |
| Gherkin parser | Scenarios are valid |
| Score limits | Weak or untested work cannot score high |
| Prompt injection | The agent ignores instructions hidden in content |

These catch breakage, but they do not measure accuracy, so a card showing 2/2 means less than it seems. Groundedness, Faithfulness, Recall, and F1 scores are planned in \`docs/PLUGIN_AND_UI_PLAN.md\`.`,
      },
    ],
  },
  {
    title: "Reference",
    pages: [
      {
        slug: "evaluations",
        title: "Evaluations",
        summary: "Each accuracy metric: formula, meaning, how to read it, and its limits.",
        body: `How Agentic QE Platform measures whether an agent is accurate. Nothing here is estimated: a number appears only when a metric really ran, and every other state says why there is no number.

## The four states of a score

| State | Meaning |
|---|---|
| A percentage | The metric ran. The card also says if it was self-graded or if its labels are not yet reviewed |
| Not measured | It has not been run, or the tool it needs (RAGAS, a judge model) is missing. The reason is shown |
| n/a | The metric does not apply to this agent. A generated test, for example, is not a claim to check against context |
| Failed or Not available | It was tried and could not run, for example the judge model refused or the endpoint has no embeddings model |

A ratio whose denominator is zero has no value. It is never shown as 0 percent or 100 percent.

## Free metrics (code only, no model tokens)

### Groundedness

Question: do the citations really exist?

Formula: groundedness = verified citations / all citations. A citation is a file, a line, and a quote. A citation is verified when the file exists inside the repository, the quote is found in it (whitespace is ignored, since models reflow code), or, with no quote, the line exists. On benchmarks the check is against the given context text instead of the disk.

How to read: 100 percent means every citation was real. It says nothing about whether the claim is right, only that the evidence exists. A reply with no citations has no value, because nothing was there to check.

Limits: a real quote can still be used for a wrong claim. Prose such as "see cart.py:27" is checked only for the file and the line.

It runs on every real agent call that cites files, costs nothing, and is stored with the agent call.

### Precision, Recall, F1

Question: did the agent find the right items, without extras?

Formulas, with TP the items found that match the answer key, FP the extras, and FN the key items missed:

- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = 2 TP / (2 TP + FP + FN)

Items match one to one: a key item can be matched once. A bug or requirement matches when the file is the same and the line is within the key's tolerance, which is usually 0 to 2 lines. A facts-in-text key (used for the business analyst) counts which labelled facts appear in the document. It cannot count extras in prose, so only Recall has a value there.

How to read: low precision means false alarms, low recall means missed items, and F1 is the balance. In the bug reviewer, a finding in a clean file is a false alarm.

Limits: the score is only as good as the labels. While labels are not reviewed by a person, cards say "labels not yet reviewed". Matching by line is strict and may miss a correct finding that cites a slightly different line.

### Mutation score

Question: do the generated tests catch real bugs?

Method: a bug is planted in a temporary copy of the repository, the generated tests run with the same runner the platform uses, and the mutant is killed when a test fails.

Formula: mutation score = killed / (killed + survived). A mutant whose text cannot be applied exactly once is "not applied" and is left out.

If no test was executed, or the tests already fail on the unchanged code, the result is INCONCLUSIVE and there is no number.

How to read: 100 percent means every planted bug was caught. A surviving mutant names the behavior no test checks.

Limits: a few hand-written mutants are a sample, not proof. The real repository is never changed.

## Model-graded metrics (RAGAS)

These use a judge model and cost tokens. They need the optional package: install requirements-evals.txt. Without it every one reads "Not measured: RAGAS is not installed".

The judge model is set with ATLAS_EVAL_MODEL. If it is unset, or the same as the agent's model, every score is labelled self-graded, because a model grading its own work is a weak check. Scores vary between runs, so read the spread over repeated runs and judge trends, not single numbers.

| Metric | Question | Needs |
|---|---|---|
| Faithfulness | Is each claim in the answer supported by the context? Claims supported / all claims | Context |
| Context recall | Did the context hold what the answer needs? Reference statements found in the context / all reference statements | Context and reference |
| Context precision | Was the context relevant, with the useful parts ranked first? | Context and reference |
| Factual correctness (F1 mode) | Does the answer agree with the reference? F1 over claims in the answer and in the reference | Reference |
| Response relevancy | Does the answer address the question? Needs an embeddings model | An embeddings model |

Response relevancy is named AnswerRelevancy in RAGAS 0.4.3. The model endpoint in use offers no embeddings model, so it reads "Not available" with that reason.

Limits: the judge can be wrong, and a reasoning model may need many tokens per score. Faithfulness can fail if the judge runs out of output tokens; the metric then reads Failed with the reason, never a guess.

## Plugin skill cases and the grader

Plugin skill cases hold sentences describing expected behavior. Where code can check a sentence it does. The rest need a grader: with ATLAS_EVAL_MODEL set, the judge reads the output and, for each sentence, answers PASS or FAIL and must quote the evidence from the output. Code then checks that the quote is in the output. A PASS without a found quote becomes FAIL. Without a judge model these cases stay "needs grader" and are neither passed nor failed.

## Benchmarks

| Benchmark | Contents |
|---|---|
| evals/benchmarks/shop | A small shop with 5 planted bugs, 2 clean files, labelled requirements, failures, and questions |
| evals/benchmarks/finance | Labels for personal-finance-mcp at a pinned commit, src/tools/tvm.py, with 5 bugs and 9 requirements found by reading the code |

Every label file has reviewed set to false. The labels were drafted by reading the code and must be checked by a person who knows the repository. Until then, cards show "labels not yet reviewed". A good score on a benchmark does not guarantee results on real code, so read it beside the live groundedness.

## Where the numbers appear

- Agents page: four tiles on each card, Groundedness, Faithfulness, Recall, and F1.
- Agent page: every metric, the trend by prompt version, the spread over repeated runs, and every case of the latest run with its question, context, answer, and reason, worst first.
- Prompts page: the tiles of each prompt version, so a new version can be compared with the one before.

Evaluations are started by an administrator, run in a hidden project, and never count against a user's token limits.

## Running them

On demand and when a prompt changes, never on a page view. Use Measure on the agent page, or POST /api/agents/{agent}/evals with benchmark, repeats, and ragas. The result reports the tokens used.`,
      },
      {
        slug: "models",
        title: "Models and limits",
        summary: "Several models on one endpoint, who may use each, and token limits that reset on a schedule.",
        body: `## One endpoint, several models

Every model uses the endpoint and key set on **Settings**. The admin manages the list under **Settings > Models**.

1. Choose **Load from proxy**. Each name the endpoint lists is added, switched off.
2. Choose **Test** beside a model. It sends a real short request and reports the result.
3. Switch the model on once its test works, and pick the default with the radio button.

A name added by hand starts switched on. A loaded name never does, because a listed name may not work. A model that is switched off cannot be used by anyone, but its ticks are kept, so switching it on again restores access. A model can be removed only when no one has it ticked.

## Who may use which

The admin ticks the models each person may use on **Users**, and picks their default from those. A person with no model ticked cannot start a run or send a chat message, and the refusal says so (AQE-ALLOW-001). Every use is checked, including the account default and an agent's model. An attempt to use a model that is not allowed is refused, and the attempt is logged against the account.

## Which model a call uses

The first match wins.

| Order | Source |
|---|---|
| 1 | The model picked for the run or chat. The picker sits on each run form and in Copilot. Leave it on Default to go on to the next row |
| 2 | The agent's model, if an admin has set one |
| 3 | The account's default |
| 4 | The system default, set on **Settings** |

Each call records the model it really used.

## Token limits

Each person can have limits on total tokens, in these periods.

| Limit | Resets |
|---|---|
| Allocation | Never. The admin raises it |
| Daily | Midnight |
| Weekly | Monday at midnight |
| Monthly | The 1st, at midnight |
| Per model | Its own daily, weekly, or monthly figure, for one model |

Periods follow the time zone set on **Settings**, which is Asia/Kolkata by default. Tokens count for the account that started each call, and a run is charged to the person who started it.

When a limit is reached, the run or chat stops at its next model call. The error (AQE-ALLOW-002) names the limit and the time it resets. Finished batches are kept. After the reset, **Retry failed stage** continues the work. Admin work, including agent evaluations, is never counted against a user.

## Seeing usage

- The header shows the tokens left today or in the allocation, whichever is tighter. It turns amber at 80 percent used.
- **Account** shows your own models, limits, and usage.
- **Usage** (admin only) shows tokens by day, user, model, and agent, for the last 7, 30, 90, or 365 days, with a CSV download.`,
      },
      {
        slug: "settings",
        title: "Environment settings",
        summary: "Settings you can change without touching code.",
        body: `## Settings

Put these in \`.env\`, or in Azure's environment variables. They keep the \`ATLAS_\` prefix so existing installs continue to work.

| Name | Default | Purpose |
|---|---|---|
| \`OPENAI_BASE_URL\`, \`OPENAI_API_KEY\`, \`DEFAULT_MODEL\` | None | Model, unless set on the Settings page |
| \`ATLAS_DATA_DIR\` | \`data\` | Runtime data |
| \`ATLAS_RUN_TOKEN_LIMIT\` | 600000 | Token budget for one run |
| \`ATLAS_MODEL_TIMEOUT\` | 180 | Seconds before one model call fails |
| \`ATLAS_MODEL_CONCURRENCY\` | 4 | Model calls at once |
| \`ATLAS_SQLITE_JOURNAL\` | WAL | Use DELETE on network storage |
| \`ATLAS_PORT\`, \`ATLAS_UI_PORT\` | 8000, 3000 | Local ports |
| \`ATLAS_ALLOWED_ORIGINS\`, \`ATLAS_ALLOWED_HOSTS\` | Local addresses | Who may call the API |
| \`ATLAS_ADMIN_USERNAME\`, \`ATLAS_ADMIN_PASSWORD\` | None | The administrator's sign-in. Nobody can sign in until both are set |
| \`ATLAS_SESSION_HOURS\` | 12 | Hours before a session ends |
| \`ATLAS_SESSION_IDLE_MINUTES\` | 480 | Minutes without activity before a session ends |
| \`ATLAS_LOG_RETENTION_DAYS\` | 30 | Days of daily log files to keep |
| \`ATLAS_MODEL_NO_CACHE\` | 1 | Asks the model proxy not to answer from its cache, so a retry is a real retry. Set 0 only if the endpoint rejects the field |`,
      },
      {
        slug: "azure",
        title: "Deploy to Azure",
        summary: "Run on App Service for about ₹1,182 a month.",
        body: `## Cost

Two Linux web apps share one Basic B1 plan in East US 2: ₹1.6189 an hour, or about ₹1,182 for a 730-hour month, from Azure's retail prices on 1 November 2026. Taxes and your model provider are extra.

## Steps

1. Run \`python scripts/package_azure.py\` to make the two ZIP files.
2. Create the plan and both apps in the Azure portal.
3. Add the settings and startup commands.
4. Upload each ZIP. The server builds its own environment on first start.
5. Add the admin login to the backend settings, and an access restriction so only the frontend can reach the backend.

The complete click-by-click guide is in \`docs/AZURE_DEPLOY.md\`.

## For several users

That setup suits one person or a small trusted team. \`docs/AZURE_SYSTEM_DESIGN.md\` has the design for several users: PostgreSQL for records, Blob Storage for files, Key Vault for secrets, and Container Apps Jobs so repository code never runs beside the app. It comes to about ₹3,905 a month for 5 users, before model costs.

Azure has not been deployed for real yet, so treat the steps as untested until you try them.`,
      },
      {
        slug: "troubleshooting",
        title: "Troubleshooting",
        summary: "Common problems and what to do.",
        body: `## Common problems

| Symptom | Do this |
|---|---|
| Model shows missing | Set it in **Settings**, then choose **Test connection** |
| Run stopped for token use | Raise \`ATLAS_RUN_TOKEN_LIMIT\`, or use a smaller repository |
| Scan says some files were not reviewed | The token budget ran out. Raise the limit and scan again |
| Test verdict is INCONCLUSIVE | No test ran. Tick install dependencies, and check that a test runner is detected |
| Run shows interrupted | The app restarted during the run. Choose **Retry failed stage** to resume from the last saved checkpoint |
| Start refused, naming a run already in progress | Only one run of each kind can be active in a project. Open the run it names, and finish or cancel it |
| Limit reached (AQE-ALLOW-002) | Wait for the reset time in the message, or ask an administrator to raise the limit |
| Model not allowed for this account | Ask an administrator to tick that model for you on the Users page |
| Private clone fails | Check the token's repository access in **Settings** |
| Port is in use | Set \`ATLAS_PORT\` and \`ATLAS_UI_PORT\` |

## Find the cause

Open **Observability**, choose the run, and select the error line for details.`,
      },
      {
        slug: "error-codes",
        title: "Error codes",
        summary: "Every error code, what it means, whether a retry can help, and what to do.",
        body: `## Codes

Each failed stage records one code. The run page shows it with the message and the action to take. Failures are grouped by code and agent on **Observability**, under **Errors**.

| Code | Meaning | Retry can help | What to do |
|---|---|---|---|
| AQE-MODEL-001 | The model reply was empty or was not valid JSON | Yes | Retry the stage. The saved reply shows the exact character that broke. |
| AQE-MODEL-002 | The model reply was cut off at the agent's token limit | No | Raise the agent's token limit on the Agents page, then retry the stage. |
| AQE-MODEL-003 | The model sent JSON with a missing or wrong field | Yes | Retry the stage. The message names the missing or wrong field. |
| AQE-MODEL-004 | The model did not reply in time. Message: The model did not reply in time. | Yes | Check the model endpoint, or raise ATLAS_MODEL_TIMEOUT, then retry the stage. |
| AQE-MODEL-005 | The model provider blocked the request under its content policy. Message starts: The model provider blocked this request | No | Remove the flagged text from the input or the repository, then retry the stage. |
| AQE-MODEL-006 | The model endpoint rejected the API key, refused the request, or cannot be reached. Messages: The model endpoint rejected the API key (HTTP {code}). The model endpoint is busy or failing (HTTP {code}). Cannot reach the model endpoint. | No, except when the endpoint is busy or failing (HTTP 429 or 5xx) or cannot be reached: then Yes | Open Settings and check the base URL, model, and API key, then retry the stage. For busy or failing endpoints the action is: Wait a moment and retry the stage. If it keeps happening, check the provider. |
| AQE-ALLOW-001 | The account has no time or tokens left, may not use the model chosen, or has no model ticked, or the run reached its token limit | No | Ask your administrator to raise the allocation or tick the model, then retry the stage. |
| AQE-ALLOW-002 | A daily, weekly, monthly, or per-model token limit is reached. The message names the limit and when it resets | No, until the reset time | Wait for the reset, or ask your administrator to raise the limit, then use Retry failed stage. A run keeps its finished batches. |
| AQE-REPO-001 | The repository address or access token did not work | No | Check the repository address and access token, then try again. |
| AQE-EVID-001 | No requirement passed evidence checks. No quote was found on disk at the stated file and line | No | Review the requirements and the repository, then retry the stage. |
| AQE-TEST-001 | Dependencies could not be installed, so the tests could not run | No | Tick install dependencies for this run, or fix the environment, then retry the stage. |
| AQE-INT-001 | An unexpected error. The message gives the exception type and a short description | No | Copy the diagnostics and report it. |

"Retry can help" means a plain retry may succeed without any change. The run page still offers Retry failed stage for every failed run, because the fix named in the action may already be done.

## Retry failed stage

A failed run shows **Retry failed stage**. It repeats the stage that failed, not the whole run. Use it after you have applied the fix named in the action. Design and generate keep the batches they finished, so only the unfinished part runs again. A retry counts against the same limits as the first attempt. An interrupted run can be retried the same way.

## Copy diagnostics

**Copy diagnostics** copies the run's error code, message, action, and technical details to the clipboard, so you can attach them to a report. Secrets are masked before the copy is made.

## Saved replies

Each failed stage keeps one diagnostic record, with a redacted stack trace. When the model's reply was the problem, the whole reply is saved with the run, with secrets masked, so you can see the exact text that broke.

## Partial results

A stage that keeps failing after its retries can end with a partial result. The run page then lists the missing requirements. A partial result is marked PARTIAL in its document, and it **cannot be approved**. Send it back, or fix the cause named in the error and run the stage again.`,
      },
    ],
  },
];

export const pages = groups.flatMap((group) => group.pages.map((page) => ({ ...page, group: group.title })));
