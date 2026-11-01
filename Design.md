# Design

The previous look is kept: dark navy surfaces, indigo accent, compact type, and a collapsible sidebar. What changes is navigation and accuracy.

## What changed from the previous UI

| Previous | Now | Why |
|---|---|---|
| Project dropdown with `name (PRJ-…)` in the header | Projects page, then enter a project | You asked for this; the dropdown hid context |
| One page switching views by state | Real URLs for each view and document | Links, back button, new windows |
| Green "online" dots and hardcoded model name | Status from `/api/settings/llm` | No claims the app has not checked |
| Sample buttons and default repo values | Removed | No invented input |
| Long titles such as "ISTQB Deterministic Oracles" | Plain names and one-line purpose | Clear to BAs |
| Metrics cards with fixed labels | Tables computed from stored runs | Real data only |

## Tokens

| Token | Dark | Light |
|---|---|---|
| Page | `#030712` | `slate-50` |
| Card | `#0b1329` | white |
| Sidebar and header | `#060a17` | white |
| Input | `#070d1f` | white |
| Border | `slate-800` | `slate-200` |
| Accent | `indigo-600` | `indigo-600` |
| Success, warning, danger | emerald, amber, rose | same |

Type uses the system sans stack and system mono, so nothing loads from a font host. Base size is 14px.

## Layout

| Area | Rule |
|---|---|
| Projects page | Header, search and actions, then a card grid: 3, 2, or 1 columns |
| Project shell | 240px sidebar, collapsing to 64px, plus a header with model status, and theme |
| Content | Up to 1152px wide. Work on the left, context in a 300px right column |
| Chat | Saved chats in a 250px column, conversation fills the rest |

## Navigation

```text
/                         Projects
/settings                 Model, private repo access, health
/approvals                Every decision waiting on a person
/agents                   Agent policy, evals, guardrails, usage
/observability            Log across all projects
/templates                Document templates
/docs/{page}              Documentation site with search and page navigation
/findings, /documents     Open findings and documents across projects
/projects/{id}            Overview with a "Next" step
  /repository             Git, ZIP, or folder; analysis and file viewer
  /ba                     Brief, template, sources, run
  /documents[/{doc}]      List; edit, preview, history
  /feature                Build a feature on a branch
  /bugs                   Scan, findings, fix, diagnose
  /qe                     Lifecycle stepper and run
  /governance             Gates, approvals, ledger
  /runs[/{run}]           Metrics, history, live timeline
  /observability          Log and per-run trace for this project
  /prompts                Versions, rollback, evals
  /chat                   Copilot
/chat/{id}                Copilot in its own window
```

## Components

| Component | Rule |
|---|---|
| Approval card | Amber border. Shows evidence and links. Needs a signer's name; sending back needs feedback |
| Run panel | Live metrics, stage chips, per-stage collapsible activity, Stop run. Errors appear in full |
| Workspace shell | Left navigation, brand, and one-line purpose on all non-project pages |
| Document page | Preview first, then Edit and History. Warns about unsaved changes. Gherkin validity badge |
| Diff | Green and red lines on a dark block, in both themes |
| Empty state | Dashed box saying what is missing and how to fix it |
| Destructive action | Confirmation. Project delete needs the name typed |

## Writing

Use plain words and active voice. Buttons say what they do: "Clone and scan", "Send back". Errors say what happened and what to do next. Do not use marketing terms.

## Accessibility

Controls have labels. Icon buttons have `aria-label`. Tabs use `role="tab"`. Status also appears in text, never only in color. Dialogs use `aria-modal`.
