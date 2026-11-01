"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useProject } from "../../../../components/ProjectShell";
import { Badge, Card, Empty, PageTitle, Spinner } from "../../../../components/ui";
import { api, when } from "../../../../lib/api";

function Table({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  if (!rows.length) return <p className="text-sm text-slate-500">No data yet.</p>;
  return <table className="w-full text-left text-xs"><thead className="text-slate-500"><tr>{head.map((h) => <th key={h} className="py-1">{h}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={i} className="border-t border-slate-200 dark:border-slate-800">{r.map((c, j) => <td key={j} className="py-1">{c}</td>)}</tr>)}</tbody></table>;
}

export default function RunsPage() {
  const { project } = useProject();
  const [runs, setRuns] = useState<any[] | null>(null);
  const [metrics, setMetrics] = useState<any>(null);
  useEffect(() => {
    api(`/projects/${project.id}/runs`).then(setRuns);
    api(`/projects/${project.id}/metrics`).then(setMetrics);
  }, [project.id]);
  if (!runs || !metrics) return <Spinner />;
  return (
    <>
      <PageTitle title="Runs & Metrics" subtitle="Computed from this project's stored runs, events, and ledger." />
      {!runs.length && <Empty title="No runs yet">Metrics appear after a workflow has run.</Empty>}
      {runs.length > 0 && (
        <>
          <div className="mb-4 grid gap-4 md:grid-cols-3">
            <Card title="Workflows"><Table head={["Workflow", "Status", "Runs", "Tokens"]} rows={metrics.runs.map((r: any) => [r.workflow, r.status, r.count, (r.tokens_in || 0) + (r.tokens_out || 0)])} /></Card>
            <Card title="Agent calls"><Table head={["Agent", "Model calls", "Tokens", "Avg ms", "Errors"]} rows={metrics.agents.map((a: any) => [a.agent, a.calls, a.tokens, a.avg_ms, a.errors])} /></Card>
            <Card title="Tool calls"><Table head={["Tool", "Calls", "Avg ms"]} rows={metrics.tools.map((t: any) => [t.tool, t.calls, t.avg_ms])} /></Card>
          </div>
          <Card title="All runs">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-slate-500"><tr><th className="pb-1">Workflow</th><th>Status</th><th>Started</th><th>Finished</th><th>Tokens</th></tr></thead>
              <tbody>{runs.map((r) => <tr key={r.id} className="border-t border-slate-200 dark:border-slate-800"><td className="py-1.5"><Link className="font-semibold hover:underline" href={`/projects/${project.id}/runs/${r.id}`}>{r.workflow}</Link></td><td><Badge>{r.status}</Badge></td><td className="text-xs">{when(r.started_at)}</td><td className="text-xs">{when(r.ended_at)}</td><td className="text-xs">{r.tokens_in + r.tokens_out}</td></tr>)}</tbody>
            </table>
          </Card>
        </>
      )}
    </>
  );
}
