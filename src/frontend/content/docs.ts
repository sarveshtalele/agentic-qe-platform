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
| Observability | A record of every agent, tool, and decision |

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

The run panel shows the current stage, elapsed time, tokens, and agent calls. **Open full trace** shows every step.

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
4. Use **Download JSON** to save what the filters show.`,
      },
      {
        slug: "agents",
        title: "Agents and evaluations",
        summary: "Policy, guardrails, and quality for all 13 agents.",
        body: `## Controls

| Control | What it does |
|---|---|
| Tool policy | An agent receives only the tools listed for it |
| Disable | Stops an agent at once. It needs your name and goes to the ledger |
| Token limit | Caps output per model call. Each run also has a token budget |
| Secret guardrail | Removes secrets from input and output |
| Injection guardrail | Removes instruction-like text from briefs, sources, and repository files |

## Evaluations

**Run all evaluations** runs each agent's quality and safety cases on the real model, and stores results per prompt version. Model replies vary, so an occasional case can fail between runs.`,
      },
    ],
  },
  {
    title: "Reference",
    pages: [
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
| \`ATLAS_RUN_TOKEN_LIMIT\` | 300000 | Token budget for one run |
| \`ATLAS_MODEL_TIMEOUT\` | 180 | Seconds before one model call fails |
| \`ATLAS_MODEL_CONCURRENCY\` | 4 | Model calls at once |
| \`ATLAS_SQLITE_JOURNAL\` | WAL | Use DELETE on network storage |
| \`ATLAS_PORT\`, \`ATLAS_UI_PORT\` | 8000, 3000 | Local ports |
| \`ATLAS_ALLOWED_ORIGINS\`, \`ATLAS_ALLOWED_HOSTS\` | Local addresses | Who may call the API |`,
      },
      {
        slug: "azure",
        title: "Deploy to Azure",
        summary: "Run on App Service for about ₹1,182 a month.",
        body: `## Cost

Two Linux web apps share one Basic B1 plan in East US: ₹1.6189 an hour, or about ₹1,182 for a 730-hour month, from Azure's retail prices on 1 November 2026. Taxes and your model provider are extra.

## Steps

1. Run \`python scripts/package_azure.py\` to make the two ZIP files.
2. Create the plan and both apps in the Azure portal.
3. Add the settings and startup commands.
4. Upload each ZIP. The server builds its own environment on first start.
5. Turn on App Service Authentication for the frontend, and an access restriction for the backend.

> Both protections are required, because the app has no login of its own and can run repository code.

The complete click-by-click guide is in \`docs/AZURE_DEPLOY.md\`.`,
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
| Run shows interrupted | The app restarted during the run. Start it again |
| Private clone fails | Check the token's repository access in **Settings** |
| Port is in use | Set \`ATLAS_PORT\` and \`ATLAS_UI_PORT\` |

## Find the cause

Open **Observability**, choose the run, and select the error line for details.`,
      },
    ],
  },
];

export const pages = groups.flatMap((group) => group.pages.map((page) => ({ ...page, group: group.title })));
