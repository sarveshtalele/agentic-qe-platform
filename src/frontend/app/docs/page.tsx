"use client";

import { AppShell } from "../../components/AppShell";
import { Markdown, PageTitle } from "../../components/ui";

const sections: [string, string, string][] = [
  ["start", "Getting started", `1. Open **Settings** and check that **Model** shows ready. Set the base URL, model, and API key there, or in \`.env\`.
2. On **Projects**, choose **New project**. Add a Git URL or ZIP now, or later on the Repository page.
3. Open the project. The **Next** line on Overview tells you the next useful step.`],
  ["repo", "Connect code", `| Source | How |
|---|---|
| Public Git | Paste an HTTPS URL or \`owner/repo\` on the Repository page |
| Private GitHub | In **Settings**, add a fine-grained token. Then pick the connection and repository on the Repository page |
| ZIP | Upload on the Repository page. No Git host needed |
| Local folder | Enter the path. The folder is copied and the original is not changed |

For private repositories, the token needs read access to contents. To open pull requests from Agentic QE Platform, it also needs write access to contents and pull requests. Tokens are encrypted and never placed in URLs.`],
  ["ba", "Write requirements in BA Studio", `1. Write a brief, and upload any source documents (.md, .txt, .pdf, .docx, .xlsx, .pptx).
2. Choose a template, or upload your own as Markdown or Word. Generated documents keep every heading.
3. Choose **Generate document**. An independent reviewer scores the draft, and Gherkin scenarios are produced and validated.
4. Approve at the gate, or send it back with feedback.`],
  ["docs", "Edit, version, and download documents", `Open a document from **Documents**.

- **Preview** shows it formatted. **Edit** changes the source. **History** lists every version, with diffs and restore.
- **Ask reviewer** scores the current version. **Refine with agent** saves a new version from your instructions.
- Download as **.md** or **.docx**. Gherkin also downloads as **.feature**. Test cases also download as **.csv** and Jira **.csv**.
- Invalid Gherkin cannot be saved. Saving an approved document returns it to draft.`],
  ["feature", "Build a feature", `On **Feature Builder**, describe the change. The agent edits a separate branch and the real tests run. You review the diff and test verdict, then approve or send back. Nothing reaches your main checkout. After approval you can download the changed files or a patch, or open a pull request if a token is connected.`],
  ["bugs", "Scan for bugs", `On **Bug Scan**, choose **Scan repository**. Ruff, secret, code, and manifest scanners run with an agent review of the riskiest files. An agent finding is kept only if the code it quotes exists in the file. Use **Fix on a branch** on a finding, or paste a stack trace under **Diagnose an error**.`],
  ["qe", "Run the QE lifecycle", `**QE Studio** runs the full test lifecycle and shows it live: current stage, elapsed time, tokens, agents, and tools.

| Gate | You approve |
|---|---|
| G0 Intake | Scope and mode |
| G1 Requirements | Requirements with verified evidence |
| G2 Plan | Risk-ranked plan |
| G3 Design | Test cases and oracles |
| G4 Generate | Generated tests. Approving allows them to run on this machine |
| G5 Release | Executed evidence and verdict |

Zero executed tests gives **INCONCLUSIVE**, never PASS. Real application defects stay as failing tests. Tick **Install repository dependencies** if the repository needs them; that runs its install scripts on your machine.`],
  ["approvals", "Approvals", `**Approvals** in the left navigation lists every decision waiting for you, across projects. Each decision records your name in the audit ledger. Sending back needs feedback, and the stage reruns with it. Gates run in order, and rejecting one clears later approvals.`],
  ["chat", "Copilot", `Open **Copilot** in a project, or use **Open in new window**. Pick an agent per chat. Chats are saved and can be renamed or deleted. Project memory is shared by all chats.

Ask about documents and code, or try \`/scan\`, \`/fix <finding id>\`, \`/gates\`, \`/verify\`, \`/feature <text>\`, \`/docs <query>\`. Agents can start workflows, but only people approve gates.`],
  ["agents", "Agents, guardrails, and evaluations", `**Agents** lists all 13 agents with their risk tier, allowed tools, prompt version, evaluation score, calls, tokens, latency, errors, and guardrail events. Every number comes from recorded calls.

| Control | What it does |
|---|---|
| Tool policy | An agent receives only the tools listed for it. Only the feature engineer and defect diagnostician can edit code, and only on a branch |
| Disable | Stops an agent at once for all projects. The change needs your name and goes to the audit ledger |
| Token limit | Caps output per model call. Each run also has an overall token budget |
| Secret guardrail | Removes secrets from input and output |
| Injection guardrail | Removes instruction-like text from briefs, sources, and repository files before the model sees it, and records it |
| Evaluations | **Run all evaluations** runs each agent's quality and safety cases on the real model. Results are stored per prompt version |`],
  ["gov", "Governance and prompts", `**Governance** shows signed gate decisions and the hash-chained audit ledger, which flags tampering. **Prompts** shows each agent's prompt versions. Editing creates a new version, older ones can be reactivated, and every document records the prompt version that wrote it. **Run with the real model** scores a prompt against its evaluation cases.`],
  ["trouble", "Troubleshooting", `| Symptom | Do this |
|---|---|
| Model shows missing | Set it in **Settings**, then **Test connection** |
| Run stopped for token use | Raise \`ATLAS_RUN_TOKEN_LIMIT\`, or scope the repository smaller |
| Test verdict INCONCLUSIVE | No test ran. Tick install dependencies, and check that a test runner is detected |
| Run shows interrupted | The app restarted during the run. Start it again |
| Private clone fails | Check the token's repository access in **Settings** |`],
  ["observability", "Observability and debugging", `**Observability** in the left menu shows all projects. Each project has its own page too, and every run links to its full trace.

| Log type | What it records |
|---|---|
| Skills | The agentic-qe skill each workflow stage carries out |
| Agents | Tokens, duration, prompt version, status, and source of every model call |
| Tools | Tool name, redacted arguments, duration, and result status |
| MCP tools | MCP server tools. There are none until an MCP server is connected |
| Workflow steps | Stage starts and ends, test results, warnings, and errors |
| Approvals | Who was asked and what they decided |
| Guardrails | Redacted secrets and removed prompt injections |
| Audit ledger | Hash-chained record of each state change |

To debug a run, choose it in the **Run** list, then open any line for its details. **Download JSON** saves what the filters show.`],
  ["azure", "Deploying to Azure", `Agentic QE Platform runs as two Linux web apps on one Basic B1 App Service plan, about ₹1,182 a month in East US at Azure retail prices checked on 1 November 2026.

1. Run \`python scripts/package_azure.py\` to make the backend and frontend ZIPs in \`dist/\`.
2. Create the plan and both apps in the Azure portal, then add the settings and startup commands.
3. Upload each ZIP, then turn on App Service Authentication for the frontend and an access restriction for the backend. Both are required before anyone uses it.

The full click-by-click steps are in \`docs/AZURE_DEPLOY.md\`.`],
];

export default function DocsPage() {
  return (
    <AppShell>
      <PageTitle title="Documentation" subtitle="How to use Agentic QE Platform, from first project to release sign-off." />
      <div className="grid gap-6 md:grid-cols-[200px_1fr]">
        <nav aria-label="Documentation sections" className="sticky top-16 self-start">
          <ul className="space-y-1 text-sm">{sections.map(([id, title]) => <li key={id}><a className="text-slate-600 hover:text-indigo-500 dark:text-slate-400" href={`#${id}`}>{title}</a></li>)}</ul>
        </nav>
        <div className="space-y-4">
          {sections.map(([id, title, body]) => (
            <section key={id} id={id} className="scroll-mt-16 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-[#0b1329]">
              <h2 className="mb-2 text-base font-bold">{title}</h2>
              <Markdown>{body}</Markdown>
            </section>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
