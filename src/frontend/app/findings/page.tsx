"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { Badge, Empty, ErrorNote, PageTitle, Spinner } from "../../components/ui";
import { api } from "../../lib/api";

const tone: Record<string, string> = { critical: "rose", high: "rose", medium: "amber" };

export default function AllFindingsPage() {
  const [items, setItems] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api("/findings").then(setItems).catch((e) => setError(e.message));
  }, []);
  return (
    <AppShell>
      <PageTitle title="Open findings" subtitle="Open bugs and security findings across all projects. Select one to open its project's Bug Scan." />
      <ErrorNote message={error} />
      {!items ? !error && <Spinner /> : !items.length ? <Empty title="No open findings">Run a scan from a project&apos;s Bug Scan tab.</Empty> : (
        <ul className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-[#0b1329]" data-testid="all-findings">
          {items.map((f) => (
            <li key={f.id}><Link href={`/projects/${f.project_id}/bugs`} className="flex flex-wrap items-center gap-2 p-3 text-sm hover:bg-slate-50 dark:hover:bg-slate-900">
              <Badge tone={tone[f.severity]}>{f.severity}</Badge><b className="min-w-0 flex-1">{f.title}</b><span className="mono text-xs text-slate-500">{f.file}:{f.line}</span><span className="text-xs text-slate-500">{f.project}</span>
            </Link></li>
          ))}
        </ul>
      )}
    </AppShell>
  );
}
