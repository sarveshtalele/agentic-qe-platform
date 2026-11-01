"use client";

import { Radar, Stethoscope, Wrench, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useProject } from "../../../../components/ProjectShell";
import { RunDocuments, RunList, RunPanel } from "../../../../components/RunPanel";
import { Badge, Button, Card, Empty, ErrorNote, Field, inputClass, PageTitle } from "../../../../components/ui";
import { api } from "../../../../lib/api";

export default function BugsPage() {
  const { project, refresh } = useProject();
  const [findings, setFindings] = useState<any[]>([]);
  const [severity, setSeverity] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [trace, setTrace] = useState("");
  const [error, setError] = useState("");
  const load = useCallback(() => api(`/projects/${project.id}/findings`).then(setFindings), [project.id]);
  useEffect(() => {
    load();
  }, [load]);
  if (!project.repo) return <Empty title="Bug Scan needs code"><Link className="text-indigo-500 underline" href={`/projects/${project.id}/repository`}>Connect a repository or upload a ZIP</Link></Empty>;
  const start = async (workflow: string, input: object) => {
    setError("");
    try {
      setRunId((await api(`/projects/${project.id}/runs`, { json: { workflow, input } })).id);
    } catch (e: any) {
      setError(e.message);
    }
  };
  const dismiss = async (id: string) => {
    await api(`/findings/${id}`, { method: "PATCH", json: { status: "dismissed" } });
    load();
  };
  const counts = findings.reduce((all, f) => ({ ...all, [f.severity]: (all[f.severity] || 0) + 1 }), {} as Record<string, number>);
  const shown = findings.filter((f) => !severity || f.severity === severity);
  return (
    <>
      <PageTitle title="Bug Scan" subtitle="Static scanners and an agent review of every source file in the project sandbox. An agent finding is kept only if its quote exists in the file." actions={
        <div className="flex items-center gap-2">
          <Button onClick={() => start("bug_scan", {})}><Radar className="h-4 w-4" /> Scan repository</Button>
          {findings.length > 0 && <Button variant="secondary" onClick={() => start("change", { kind: "bugfix", fix_all: true })} title="Fixes up to 15 of the most severe open findings on one branch"><Wrench className="h-4 w-4" /> Fix all</Button>}
        </div>
      } />
      <ErrorNote message={error} />
      <div className="grid gap-4 lg:grid-cols-[1fr_300px] [&>*]:min-w-0">
        <div className="space-y-4">
          {runId && <RunPanel runId={runId} projectId={project.id} onFinished={() => { load(); refresh(); }} />}
          <Card title={`Open findings (${findings.length})`} actions={
            <div className="flex gap-1">
              {["critical", "high", "medium", "low"].map((s) => counts[s] ? <button key={s} onClick={() => setSeverity(severity === s ? "" : s)} className={severity === s ? "ring-2 ring-indigo-500 rounded" : ""}><Badge>{`${s} ${counts[s]}`}</Badge></button> : null)}
            </div>
          }>
            {shown.length ? (
              <ul className="divide-y divide-slate-200 dark:divide-slate-800" data-testid="findings">
                {shown.map((f) => (
                  <li key={f.id} className="py-2.5">
                    <div className="flex flex-wrap items-center gap-2"><Badge tone={{ critical: "rose", high: "rose", medium: "amber", low: "slate", info: "slate" }[f.severity as string]}>{f.severity}</Badge><span className="text-sm font-semibold">{f.title}</span><span className="mono text-[11px] text-slate-500">{f.source} {f.rule}</span></div>
                    <p className="mono mt-1 text-xs text-slate-500">{f.file}:{f.line}</p>
                    {f.evidence && <pre className="mono mt-1 overflow-x-auto rounded bg-slate-100 p-1.5 text-xs dark:bg-[#070d1f]">{f.evidence}</pre>}
                    {f.explanation && <p className="mt-1 text-sm text-slate-700 dark:text-slate-300">{f.explanation}</p>}
                    <div className="mt-1.5 flex gap-2">
                      <Button variant="secondary" className="!px-2 !py-1 !text-xs" onClick={() => start("change", { kind: "bugfix", finding_id: f.id, title: `Fix ${f.title}`.slice(0, 60) })}><Wrench className="h-3 w-3" /> Fix on a branch</Button>
                      <Button variant="secondary" className="!px-2 !py-1 !text-xs" onClick={() => dismiss(f.id)}><X className="h-3 w-3" /> Dismiss</Button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-slate-500">No open findings. Run a scan to look for some.</p>}
          </Card>
        </div>
        <div className="space-y-4">
          <Card title="Diagnose an error">
            <Field label="Paste a stack trace or failing test output"><textarea name="traceback" rows={6} className={`${inputClass} mono text-xs`} value={trace} onChange={(e) => setTrace(e.target.value)} /></Field>
            <Button variant="secondary" className="mt-2" disabled={!trace.trim()} onClick={() => start("change", { kind: "diagnose", title: "Diagnose error", spec: `Diagnose and fix this failure:\n${trace}` })}><Stethoscope className="h-4 w-4" /> Diagnose and fix</Button>
          </Card>
          <RunDocuments projectId={project.id} runId={runId} />
          <Card title="Past runs"><RunList projectId={project.id} workflow={["bug_scan", "change"]} activeId={runId} onPick={setRunId} refreshKey={runId} /></Card>
        </div>
      </div>
    </>
  );
}
