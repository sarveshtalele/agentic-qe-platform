"use client";

import { ApprovalsList } from "../../../../components/ApprovalsList";
import { useProject } from "../../../../components/ProjectShell";
import { PageTitle } from "../../../../components/ui";

export default function ProjectApprovalsPage() {
  const { project, refresh } = useProject();
  return (
    <>
      <PageTitle title="Approvals" subtitle="Quality gates and code changes in this project waiting for your decision." />
      <ApprovalsList projectId={project.id} onChange={refresh} />
    </>
  );
}
