---
name: authoring-user-stories
description: Writes BA-style user stories with Given/When/Then acceptance criteria and a test cases table (positive, negative, exception), exportable to CSV and Jira import format. Use when the user asks for user stories, acceptance criteria, a Jira story, or a test cases table, and for greenfield apps with no code yet.
metadata:
  author: Sarvesh Talele
  version: "1.4.0"
---

# Authoring User Stories

Turns a PRD, notes, or a verbal description into approved user stories plus a traceable test case table. Primary input for greenfield runs.

## When to use
Activate when the stories stage runs (plugin command `qe-stories`), or when a user wants stories, acceptance criteria, or a test cases table for Jira.

## Workflow
1. **Gather:** Read the source document the user provided, or ask the user for the app description, roles, and goals. Never invent roles or features the user did not state.
2. **Stories:** Write each as `**US-<APP>-NNN**: As a <user/role>, I want to <functionality/action> so that <business benefit/value>.` plus Given/When/Then acceptance criteria and a P1-P3 priority.
3. **Cases:** Per story, at least 1 Positive, 2 Negative, 1 Exception. Boundary cases use `Negative (Boundary)`.
4. **Export:** Build `cases.json` and run the export step below. Fix every reported error and rerun.
5. **Review:** Show the stories and table. Gate 1 is approved by a named person after the requirements stage.

Template, column definitions and a worked example: [references/TEMPLATE.md](references/TEMPLATE.md).

## Platform code step
The platform runs the export in code (`api/documents.py`, partly built: the CSV helper exists, the validating export does not yet). It validates the input, fails with specific errors on bad input, and writes `02-requirements/user_stories.md`, `02-requirements/test_cases.csv` and `02-requirements/jira_import.csv` into the output folder, each with a metadata header. Before it runs, list the three paths and get the user's yes.

## Jira
Import `02-requirements/jira_import.csv` into Jira manually.
