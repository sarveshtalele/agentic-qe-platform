"use client";

import { Download, RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Badge, Button, Card, Empty, ErrorNote, inputClass, Spinner } from "./ui";
import { api, when } from "../lib/api";

const KINDS: [string, string][] = [["", "All"], ["skill", "Skills"], ["agent", "Agents"], ["tool", "Tools"], ["mcp", "MCP tools"], ["workflow", "Workflow steps"], ["approval", "Approvals"], ["guardrail", "Guardrails"], ["audit", "Audit ledger"]];
const tone: Record<string, string> = { error: "rose", warning: "amber" };

function Entry({ item, showProject }: { item: any; showProject: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="border-b border-slate-200 last:border-0 dark:border-slate-800" data-testid="log-entry" data-kind={item.kind}>
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="grid w-full grid-cols-[150px_90px_1fr] items-baseline gap-2 px-2 py-1.5 text-left text-xs hover:bg-slate-100 dark:hover:bg-slate-900">
        <span className="text-slate-500">{when(item.ts)}</span>
        <span><Badge tone={tone[item.level]}>{item.kind}</Badge></span>
        <span className="min-w-0 break-words"><b className="mono">{item.name}</b> <span className="text-slate-600 dark:text-slate-400">{item.message}</span>{showProject && item.project && <span className="text-slate-500"> · {item.project}</span>}</span>
      </button>
      {open && (
        <div className="space-y-1 px-2 pb-2 text-xs">
          {item.run_id && item.project_id && <p>Run <Link className="mono text-indigo-500 underline" href={`/projects/${item.project_id}/runs/${item.run_id}`}>{item.run_id}</Link>{item.stage ? ` · stage ${item.stage}` : ""}</p>}
          <pre className="mono max-h-72 overflow-auto rounded-lg bg-[#070d1f] p-2 text-slate-200">{JSON.stringify(item.detail, null, 2)}</pre>
        </div>
      )}
    </li>
  );
}

export function Observability({ projectId }: { projectId?: string }) {
  const [data, setData] = useState<any>(null);
  const [projects, setProjects] = useState<any[]>([]);
  const [project, setProject] = useState(projectId || "");
  const [run, setRun] = useState("");
  const [kind, setKind] = useState("");
  const [text, setText] = useState("");
  const [live, setLive] = useState(true);
  const [error, setError] = useState("");

  const params = useCallback(() => {
    const query = new URLSearchParams();
    if (project) query.set("project_id", project);
    if (run) query.set("run_id", run);
    if (kind) query.set("kind", kind);
    if (text) query.set("q", text);
    return query.toString();
  }, [project, run, kind, text]);
  const latest = useRef(0);
  const load = useCallback(() => {
    // a slow older response must not replace what the current filters asked for
    const request = ++latest.current;
    return api(`/observability?${params()}`).then((found) => {
      if (request !== latest.current) return;
      setData(found);
      setError("");
    }).catch((e) => { if (request === latest.current) setError(e.message); });
  }, [params]);

  useEffect(() => {
    const wanted = new URLSearchParams(window.location.search).get("run");
    if (wanted) setRun(wanted);
    if (!projectId) api("/projects").then(setProjects);
  }, [projectId]);
  useEffect(() => {
    load();
    if (!live) return;
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [load, live]);

  if (!data) return error ? <ErrorNote message={error} /> : <Spinner />;
  const tiles: [string, number | string][] = [["Runs", data.runs.length], ["Skills", data.counts.skill], ["Agent calls", data.counts.agent], ["Tokens", data.tokens.toLocaleString()], ["Tool calls", data.counts.tool], ["MCP tool calls", data.counts.mcp], ["Guardrails", data.counts.guardrail], ["Errors", data.errors]];
  const broken = data.integrity.filter((i: any) => !i.valid);
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-2 text-center md:grid-cols-4 xl:grid-cols-8" data-testid="observability-tiles">
        {tiles.map(([label, value]) => <div key={label} className="rounded-lg border border-slate-200 bg-white py-2 dark:border-slate-800 dark:bg-[#0b1329]"><dd className="text-base font-bold">{value}</dd><dt className="text-[11px] text-slate-500">{label}</dt></div>)}
      </dl>
      <p className={`flex items-center gap-1.5 text-sm ${broken.length ? "text-rose-500" : "text-emerald-600 dark:text-emerald-400"}`} data-testid="ledger-integrity">
        {broken.length ? <ShieldAlert className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
        {broken.length ? `Audit ledger failed verification for: ${broken.map((i: any) => i.project).join(", ")}` : `Audit ledger verified for ${data.integrity.length} ${data.integrity.length === 1 ? "project" : "projects"}`}
      </p>
      {data.counts.mcp === 0 && <p className="text-xs text-slate-500" data-testid="mcp-note">MCP tools: none recorded. This application connects to no MCP server, so its agents use only built-in tools.</p>}
      <Card>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {!projectId && (
            <select aria-label="Project" className={`${inputClass} !w-48`} value={project} onChange={(e) => { setProject(e.target.value); setRun(""); }}>
              <option value="">All projects</option>
              {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          )}
          <select aria-label="Run" className={`${inputClass} !w-64`} value={run} onChange={(e) => setRun(e.target.value)}>
            <option value="">All runs</option>
            {run && !data.runs.some((r: any) => r.id === run) && <option value={run}>{run}</option>}
            {data.runs.map((r: any) => <option key={r.id} value={r.id}>{r.workflow} · {r.status} · {when(r.started_at)}{projectId ? "" : ` · ${r.project}`}</option>)}
          </select>
          <input aria-label="Search the log" placeholder="Search names, messages, arguments" className={`${inputClass} !w-64`} value={text} onChange={(e) => setText(e.target.value)} />
          <label className="flex items-center gap-1.5 text-sm"><input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} /> Live</label>
          <Button variant="secondary" onClick={load}><RefreshCw className="h-4 w-4" /> Refresh</Button>
          <a className="ml-auto inline-flex items-center gap-1.5 text-sm text-indigo-500 underline" href={`/api/observability/export?${params()}`}><Download className="h-4 w-4" /> Download JSON</a>
        </div>
        <div role="tablist" aria-label="Log type" className="mb-3 flex flex-wrap gap-1.5">
          {KINDS.map(([id, label]) => (
            <button key={id} type="button" role="tab" aria-selected={kind === id} onClick={() => setKind(id)} className={`rounded-md border px-2 py-1 text-xs font-semibold ${kind === id ? "border-indigo-500 bg-indigo-500/10 text-indigo-600 dark:text-indigo-300" : "border-slate-300 dark:border-slate-700"}`}>
              {label}{id && ` ${data.counts[id]}`}
            </button>
          ))}
        </div>
        <ErrorNote message={error} />
        {data.items.length === 0
          ? <Empty title="Nothing recorded for these filters">Run a workflow or send a chat message, and its activity appears here.</Empty>
          : <ul className="rounded-lg border border-slate-200 dark:border-slate-800" data-testid="observability-log">{data.items.map((item: any, i: number) => <Entry key={`${item.ts}-${item.kind}-${i}`} item={item} showProject={!projectId} />)}</ul>}
        {data.total > data.items.length && <p className="mt-2 text-xs text-slate-500">Showing the newest {data.items.length} of {data.total}. Filter the log or download JSON for all of them.</p>}
      </Card>
    </div>
  );
}
