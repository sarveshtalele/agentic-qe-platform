"use client";

import { ApprovalsList } from "../../components/ApprovalsList";
import { AppShell } from "../../components/AppShell";
import { PageTitle } from "../../components/ui";

export default function ApprovalsPage() {
  return (
    <AppShell>
      <PageTitle title="Approvals" subtitle="Quality gates and code changes waiting for a named human decision." />
      <ApprovalsList />
    </AppShell>
  );
}
