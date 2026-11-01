"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { Badge, Empty, ErrorNote, PageTitle, Spinner } from "../../components/ui";
import { api, when } from "../../lib/api";

export default function AllDocumentsPage() {
  const [items, setItems] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api("/documents").then(setItems).catch((e) => setError(e.message));
  }, []);
  return (
    <AppShell>
      <PageTitle title="Documents" subtitle="Documents across all projects. Select one to open it in its project." />
      <ErrorNote message={error} />
      {!items ? !error && <Spinner /> : !items.length ? <Empty title="No documents yet">Generate one in a project&apos;s BA Studio.</Empty> : (
        <ul className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-[#0b1329]" data-testid="all-documents">
          {items.map((d) => (
            <li key={d.id}><Link href={`/projects/${d.project_id}/documents/${d.id}`} className="flex flex-wrap items-center gap-2 p-3 text-sm hover:bg-slate-50 dark:hover:bg-slate-900">
              <b className="min-w-0 flex-1">{d.title}</b><Badge>{d.kind} v{d.current_version}</Badge><Badge>{d.status}</Badge><span className="text-xs text-slate-500">{d.project} · {when(d.updated_at)}</span>
            </Link></li>
          ))}
        </ul>
      )}
    </AppShell>
  );
}
