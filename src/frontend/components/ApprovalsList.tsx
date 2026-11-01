"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, when } from "../lib/api";
import { ApprovalCard } from "./RunPanel";
import { Empty, Spinner, useToast } from "./ui";

/** Everything waiting on a human, for one project or all of them. */
export function ApprovalsList({ projectId, onChange }: { projectId?: string; onChange?: () => void }) {
  const [items, setItems] = useState<any[] | null>(null);
  const toast = useToast();
  const load = useCallback(() => api("/approvals").then((all) => setItems(all.filter((a: any) => !projectId || a.project_id === projectId))), [projectId]);
  useEffect(() => {
    load();
    const timer = setInterval(load, 10_000);
    return () => clearInterval(timer);
  }, [load]);
  if (!items) return <Spinner />;
  if (!items.length) return <Empty title="Nothing needs your approval" />;
  const groups = Object.values(items.reduce((all: Record<string, any>, a: any) => {
    (all[a.project_id] ||= { id: a.project_id, name: a.project_name, items: [] }).items.push(a);
    return all;
  }, {})) as any[];
  return (
    <div className="space-y-5">
      {!projectId && <p className="text-sm font-semibold" data-testid="approvals-summary">{groups.length} {groups.length === 1 ? "project needs" : "projects need"} your approval, {items.length} {items.length === 1 ? "decision" : "decisions"} in total.</p>}
      {groups.map((group) => (
        <section key={group.id} className="space-y-2">
          {!projectId && <h2 className="text-sm font-bold"><Link className="hover:underline" href={`/projects/${group.id}`}>{group.name}</Link></h2>}
          {group.items.map((a: any) => (
            <div key={a.id}>
              <p className="mb-1 text-xs text-slate-500">{a.workflow} run · waiting since {when(a.created_at)} · <Link className="text-indigo-500 underline" href={`/projects/${a.project_id}/runs/${a.run_id}`}>open run</Link></p>
              <ApprovalCard approval={a} projectId={a.project_id} onDecided={() => { toast("Decision recorded"); load(); onChange?.(); }} />
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
