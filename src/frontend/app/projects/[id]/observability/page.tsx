"use client";

import { Observability } from "../../../../components/Observability";
import { useProject } from "../../../../components/ProjectShell";
import { PageTitle } from "../../../../components/ui";

export default function ProjectObservabilityPage() {
  const { project } = useProject();
  return (
    <>
      <PageTitle title="Observability" subtitle="Every skill, agent call, tool call, workflow step, approval, and guardrail in this project. Pick a run to see its full trace." />
      <Observability projectId={project.id} />
    </>
  );
}
