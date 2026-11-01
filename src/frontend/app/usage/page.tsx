"use client";

import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { Card, Empty, ErrorNote, PageTitle, Spinner, inputClass } from "../../components/ui";
import { api } from "../../lib/api";

type Row = { name: string; tokens: number };

/** Bars scaled to the largest value in the list. Every figure is a sum of recorded model calls. */
function Bars({ title, rows }: { title: string; rows: Row[] }) {
  const top = Math.max(1, ...rows.map((r) => r.tokens));
  return (
    <Card title={title}>
      {rows.length === 0 ? <p className="text-sm text-slate-500">Nothing recorded.</p> : (
        <ul className="space-y-1.5 text-xs" data-testid={`usage-${title.toLowerCase().replace(/\W+/g, "-")}`}>
          {rows.map((r) => (
            <li key={r.name}>
              <div className="flex justify-between gap-2"><span className="mono truncate">{r.name}</span><span>{r.tokens.toLocaleString()}</span></div>
              <div className="h-1.5 rounded bg-slate-200 dark:bg-slate-800"><div className="h-1.5 rounded bg-indigo-500" style={{ width: `${Math.max(2, Math.round((100 * r.tokens) / top))}%` }} /></div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default function UsagePage() {
  const [days, setDays] = useState(30);
  const [report, setReport] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setReport(null);
    api(`/usage?days=${days}`).then(setReport).catch((e) => setError(e.message));
  }, [days]);
  return (
    <AppShell>
      <PageTitle title="Usage" subtitle="Tokens from recorded model calls, by user, model, agent, and day. Days follow the time zone set in Settings." actions={
        <div className="flex items-center gap-2">
          <select aria-label="Period" className={`${inputClass} !w-auto`} value={days} onChange={(e) => setDays(Number(e.target.value))}>{[7, 30, 90, 365].map((d) => <option key={d} value={d}>Last {d} days</option>)}</select>
          <a className="inline-flex items-center gap-1.5 text-sm text-indigo-500 underline" href={`/api/usage?format=csv&days=${days}`}><Download className="h-4 w-4" /> CSV</a>
        </div>
      } />
      <ErrorNote message={error} />
      {!report ? (error ? null : <Spinner />) : report.calls === 0 ? <Empty title="No model calls in this period">Usage appears here after a run or chat uses a model.</Empty> : (
        <div className="space-y-4">
          <p className="text-sm" data-testid="usage-total"><b>{report.tokens.toLocaleString()}</b> tokens in <b>{report.calls.toLocaleString()}</b> calls · time zone {report.timezone}</p>
          <div className="grid gap-4 md:grid-cols-2">
            <Bars title="By user" rows={report.by_user} />
            <Bars title="By model" rows={report.by_model} />
            <Bars title="By agent" rows={report.by_agent} />
            <Bars title="By day" rows={report.by_day} />
          </div>
        </div>
      )}
    </AppShell>
  );
}
