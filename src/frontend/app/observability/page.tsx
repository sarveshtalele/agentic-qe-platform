"use client";

import { AppShell } from "../../components/AppShell";
import { Observability } from "../../components/Observability";
import { PageTitle } from "../../components/ui";

export default function ObservabilityPage() {
  return (
    <AppShell>
      <PageTitle title="Observability" subtitle="Every skill, agent call, tool call, workflow step, approval, and guardrail, across all projects. All entries come from stored records." />
      <Observability />
    </AppShell>
  );
}
