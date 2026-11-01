"use client";

import { Pencil } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useProject } from "../../../components/ProjectShell";
import { Badge, Button, Card, Empty, PageTitle, Spinner } from "../../../components/ui";
import { api, when } from "../../../lib/api";

function nextStep(data: any, base: string): { label: string; href: string } {
  if (data.pending_approvals.length) return { label: `Review: ${data.pending_approvals[0].title}`, href: `${base}/runs/${data.pending_approvals[0].run_id}` };
  if (!data.repo && !data.documents.length) return { label: "Connect a repository, or write requirements in BA Studio", href: `${base}/repository` };
  if (data.repo && !data.recent_runs.some((r: any) => r.workflow === "bug_scan")) return { label: "Scan the repository for bugs", href: `${base}/bugs` };
  if (!data.gates.every((g: any) => g.status === "approved")) return { label: "Continue the QE lifecycle", href: `${base}/qe` };
  return { label: "All gates approved. Review the release document", href: `${base}/documents` };
}

export default function OverviewPage() {
  const { project, refresh } = useProject();
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    api(`/projects/${project.id}/overview`).then(setData);
  }, [project.id]);
  if (!data) return <Spinner />;
  const base = `/projects/${project.id}`;
  const step = nextStep(data, base);
  const a = data.repo?.analysis;
  return (
    <>
      <PageTitle title={project.name} subtitle={project.description} actions={<Button variant="secondary" onClick={async () => { const name = prompt("Project name", project.name)?.trim(); if (name && name !== project.name) { await api(`/projects/${project.id}`, { method: "PATCH", json: { name } }); refresh(); } }}><Pencil className="h-4 w-4" /> Rename</Button>} />
      <Link href={step.href} className="mb-4 block rounded-xl border border-indigo-500/50 bg-indigo-500/10 p-3 text-sm font-semibold text-indigo-700 hover:bg-indigo-500/15 dark:text-indigo-300">Next: {step.label}</Link>
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Repository" actions={<Link className="text-xs text-indigo-500" href={`${base}/repository`}>Manage</Link>}>
          {data.repo ? (
            <dl className="space-y-1 text-sm">
              <div className="truncate"><b>{data.repo.kind === "git" ? "Git" : "ZIP"}:</b> {data.repo.url}</div>
              <div><b>Commit:</b> <span className="mono text-xs">{data.repo.commit_sha.slice(0, 10)}</span></div>
              <div><b>Files:</b> {a.total_files} · <b>Test files:</b> {a.test_file_count}</div>
              <div className="flex flex-wrap gap-1">{Object.keys(a.languages).map((l) => <Badge key={l} tone="indigo">{l}</Badge>)}{a.frameworks.map((f: string) => <Badge key={f}>{f}</Badge>)}</div>
            </dl>
          ) : <Empty title="No repository connected">Greenfield projects can start from BA Studio.</Empty>}
        </Card>
        <Card title="Quality gates">
          <ul className="space-y-1 text-sm">
            {data.gates.map((g: any) => (
              <li key={g.gate} className="flex items-center justify-between gap-2">
                <span>G{g.gate} {g.name}</span>
                <span className="flex items-center gap-2 text-xs text-slate-500">{g.decided_by}<Badge>{g.status}</Badge></span>
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Recent runs" actions={<Link className="text-xs text-indigo-500" href={`${base}/runs`}>All runs</Link>}>
          {data.recent_runs.length ? (
            <ul className="space-y-1 text-sm">
              {data.recent_runs.map((r: any) => (
                <li key={r.id} className="flex items-center justify-between gap-2"><Link className="truncate hover:underline" href={`${base}/runs/${r.id}`}>{r.workflow} · {when(r.started_at)}</Link><Badge>{r.status}</Badge></li>
              ))}
            </ul>
          ) : <p className="text-sm text-slate-500">No workflow has run yet.</p>}
        </Card>
        <Card title="Latest documents" actions={<Link className="text-xs text-indigo-500" href={`${base}/documents`}>All documents</Link>}>
          {data.documents.length ? (
            <ul className="space-y-1 text-sm">
              {data.documents.map((d: any) => (
                <li key={d.id} className="flex items-center justify-between gap-2"><Link className="truncate hover:underline" href={`${base}/documents/${d.id}`}>{d.title}</Link><span className="flex shrink-0 items-center gap-1 text-xs">{d.kind} v{d.current_version}<Badge>{d.status}</Badge></span></li>
              ))}
            </ul>
          ) : <p className="text-sm text-slate-500">No documents yet.</p>}
        </Card>
      </div>
    </>
  );
}
