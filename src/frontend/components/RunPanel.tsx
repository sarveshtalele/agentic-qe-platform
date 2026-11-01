"use client";

import { CheckCircle2, Circle, FileText, Loader2, XCircle } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, getSigner, setSigner, when } from "../lib/api";
import { Badge, Button, Card, ErrorNote, Field, inputClass, useToast } from "./ui";

function ConfidenceNote({ review }: { review?: any }) {
  if (!review) return null;
  const tone = review.score === null ? "amber" : review.score >= 85 ? "emerald" : review.score >= 70 ? "amber" : "rose";
  return (
    <div className="text-sm" data-testid="confidence">
      <span className="flex flex-wrap items-center gap-2"><b>Independent confidence review</b> <Badge tone={tone}>{review.score === null ? "not run" : `${review.score} of 100`}</Badge> <Badge>{review.verdict}</Badge></span>
      {review.issues?.length > 0 && <ul className="mt-1 list-disc pl-5 text-xs text-slate-600 dark:text-slate-400">{review.issues.slice(0, 8).map((issue: string, i: number) => <li key={i}>{issue}</li>)}</ul>}
    </div>
  );
}

function LiveLog({ events, live }: { events: any[]; live: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  const [follow, setFollow] = useState(true);
  useEffect(() => {
    if (follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [events, follow]);
  const color: Record<string, string> = { error: "text-rose-400", warning: "text-amber-400", review: "text-sky-300", test: "text-emerald-300", artifact: "text-emerald-300", agent: "text-indigo-300", agent_call: "text-indigo-300", tool: "text-slate-400" };
  return (
    <div data-testid="live-log">
      <div className="mb-1 flex items-center justify-between text-xs">
        <b className="flex items-center gap-1.5">{live && <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />}{live ? "Live log" : "Run log"} ({events.length})</b>
        <label className="flex items-center gap-1 text-slate-500"><input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /> Follow</label>
      </div>
      <div ref={box} className="mono max-h-72 overflow-y-auto rounded-lg bg-[#070d1f] p-2 text-[11px] leading-relaxed text-slate-300">
        {events.map((e) => (
          <div key={e.seq} className="flex gap-2">
            <span className="shrink-0 text-slate-500">{new Date(e.ts).toLocaleTimeString()}</span>
            {e.stage && <span className="w-24 shrink-0 truncate text-slate-500">{e.stage}</span>}
            <span className={`min-w-0 break-words ${color[e.type] || ""}`}>{e.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Rectangular cards for the documents a run has made. They appear as the run creates them. */
export function RunDocuments({ projectId, runId }: { projectId: string; runId: string | null }) {
  const [docs, setDocs] = useState<any[]>([]);
  useEffect(() => {
    if (!runId) return setDocs([]);
    const load = () => api(`/projects/${projectId}/documents`).then((items) => setDocs(items.filter((d: any) => d.run_id === runId))).catch(() => {});
    load();
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [projectId, runId]);
  if (!docs.length) return null;
  return (
    <Card title={`Documents from this run (${docs.length})`}>
      <ul className="space-y-2" data-testid="current-documents">
        {docs.map((d) => (
          <li key={d.id}>
            <Link href={`/projects/${projectId}/documents/${d.id}`} data-testid="document-card" className="flex items-center gap-2.5 rounded-lg border border-slate-200 bg-slate-50 p-2.5 transition hover:border-indigo-500 dark:border-slate-700 dark:bg-slate-900">
              <FileText className="h-5 w-5 shrink-0 text-indigo-500" />
              <span className="min-w-0 flex-1"><b className="block truncate text-sm">{d.title}</b><span className="text-[11px] text-slate-500">{d.kind.replace(/_/g, " ")} · v{d.current_version} · {d.status}</span></span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function ApprovalCard({ approval, projectId, onDecided }: { approval: any; projectId: string; onDecided: () => void }) {
  const [by, setBy] = useState("");
  const [feedback, setFeedback] = useState("");
  const [openPr, setOpenPr] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => setBy(getSigner()), []);
  const payload = approval.payload || {};
  const decide = async (approved: boolean) => {
    setBusy(true);
    setError("");
    try {
      setSigner(by);
      await api(`/approvals/${approval.id}/decide`, { json: { approved, by, feedback, open_pr: openPr } });
      onDecided();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-3 rounded-xl border border-amber-500/50 bg-amber-500/5 p-4" data-testid="approval-card">
      <div className="flex items-center gap-2">
        <Badge tone="amber">Approval needed</Badge>
        <h3 className="text-sm font-bold">{approval.title}</h3>
      </div>
      <p className="text-sm text-slate-700 dark:text-slate-300">{approval.summary}</p>
      {payload.documents && (
        <ul className="flex flex-wrap gap-2 text-sm">
          {payload.documents.map((doc: string, i: number) => (
            <li key={doc}><Link className="text-indigo-500 underline" target="_blank" href={`/projects/${projectId}/documents/${doc}`}>Open {payload.titles?.[i] || "document"}</Link></li>
          ))}
        </ul>
      )}
      <ConfidenceNote review={payload.confidence || payload.verification?.confidence} />
      {payload.review && <p className="text-sm">Reviewer score <b>{payload.review.score}</b>: {payload.review.issues?.join("; ") || "no issues"}</p>}
      {payload.verification && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          Test verdict <Badge>{payload.verification.verdict}</Badge>
          {payload.verification.reason && <span className="text-xs">{payload.verification.reason}</span>}
          {payload.verification.suites?.map((s: any) => <span key={s.runner} className="mono text-xs">{s.runner}: {s.passed} passed, {s.failed} failed{s.reason ? ` (${s.reason})` : ""}</span>)}
          {!payload.verification.suites?.length && <span className="text-xs">No registered test runner found in this repository.</span>}
        </div>
      )}
      {payload.verification?.changed_assertions?.length > 0 && (
        <div className="rounded-lg border border-rose-500/50 bg-rose-500/10 p-2 text-sm" data-testid="changed-assertions">
          <b>Existing assertions changed. Check that this is intended:</b>
          <ul className="mono mt-1 text-xs">{payload.verification.changed_assertions.map((line: string, i: number) => <li key={i}>{line}</li>)}</ul>
        </div>
      )}
      {payload.diff !== undefined && <pre className="mono max-h-96 overflow-auto rounded-lg bg-[#070d1f] p-3 text-xs text-slate-200">{payload.diff.split("\n").map((line: string, i: number) => <div key={i} className={line.startsWith("+") ? "text-emerald-400" : line.startsWith("-") ? "text-rose-400" : ""}>{line || " "}</div>)}</pre>}
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Your name (signer)"><input className={inputClass} value={by} onChange={(e) => setBy(e.target.value)} placeholder="Name recorded in the audit ledger" /></Field>
        <Field label="Feedback (required to send back)"><input className={inputClass} value={feedback} onChange={(e) => setFeedback(e.target.value)} placeholder="What should change" /></Field>
      </div>
      {payload.can_open_pr && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={openPr} onChange={(e) => setOpenPr(e.target.checked)} /> Push the branch and open a pull request</label>}
      <ErrorNote message={error} />
      <div className="flex gap-2">
        <Button variant="success" busy={busy} disabled={!by.trim()} onClick={() => decide(true)}>Approve</Button>
        <Button variant="danger" busy={busy} disabled={!by.trim() || !feedback.trim()} onClick={() => decide(false)}>Send back</Button>
      </div>
    </div>
  );
}

export function RunPanel({ runId, projectId, onFinished }: { runId: string; projectId: string; onFinished?: () => void }) {
  const [run, setRun] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const lastSeq = useRef(0);
  const [now, setNow] = useState(() => Date.now());
  const toast = useToast();

  const load = useCallback(async () => {
    const data = await api(`/runs/${runId}`);
    setRun(data);
    return data;
  }, [runId]);

  useEffect(() => {
    lastSeq.current = 0;
    setEvents([]);
    let source: EventSource | null = null;
    let cancelled = false;
    const connect = () => {
      source = new EventSource(`/api/runs/${runId}/events?after=${lastSeq.current}`);
      source.addEventListener("run", (e) => {
        const item = JSON.parse((e as MessageEvent).data);
        lastSeq.current = item.seq;
        setEvents((prior) => [...prior, item]);
      });
      source.addEventListener("end", async () => {
        source?.close();
        if (cancelled) return;
        const data = await load();
        if (data.status === "running") setTimeout(connect, 1000);
        else onFinished?.();
      });
      source.onerror = () => {
        source?.close();
        if (!cancelled) setTimeout(connect, 2000);
      };
    };
    load();
    connect();
    return () => {
      cancelled = true;
      source?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  // live numbers while the run works: elapsed time every second, tokens every few seconds
  useEffect(() => {
    if (run?.status !== "running") return;
    const clock = setInterval(() => setNow(Date.now()), 1000);
    const poll = setInterval(load, 3000);
    return () => {
      clearInterval(clock);
      clearInterval(poll);
    };
  }, [run?.status, load]);

  const decided = async () => {
    toast("Decision recorded");
    await load();
    const source = new EventSource(`/api/runs/${runId}/events?after=${lastSeq.current}`);
    source.addEventListener("run", (e) => {
      const item = JSON.parse((e as MessageEvent).data);
      lastSeq.current = item.seq;
      setEvents((prior) => [...prior, item]);
    });
    source.addEventListener("end", async () => {
      source.close();
      const data = await load();
      if (data.status !== "running") onFinished?.();
    });
    source.onerror = () => source.close();
  };

  if (!run) return null;
  const open = run.approvals.filter((a: any) => a.status === "pending");
  const cancel = async () => {
    if (!confirm("Stop this run?")) return;
    try {
      await api(`/runs/${runId}/cancel`, { method: "POST" });
      await load();
    } catch (e: any) {
      toast(e.message, "error");
    }
  };
  const stages = buildStages(events, run.status);
  const toolCalls = events.filter((e) => e.type === "tool").length;
  const agentCalls = events.filter((e) => e.type === "agent").length;
  const live = run.status === "running";
  return (
    <Card
      title={<span className="flex flex-wrap items-center gap-2">Run <span className="mono text-xs font-normal">{run.id.slice(-8)}</span> <Badge>{run.workflow}</Badge> <span data-testid="run-status"><Badge>{run.status}</Badge></span>{live && <Loader2 className="h-4 w-4 animate-spin text-indigo-500" />}</span>}
      actions={(live || run.status === "waiting_approval") ? <Button variant="danger" className="!px-2 !py-1 !text-xs" onClick={cancel}>Stop run</Button> : undefined}
    >
      <div className="space-y-3">
        <dl className="grid grid-cols-2 gap-2 text-center md:grid-cols-4" data-testid="run-metrics">
          {[["Elapsed", duration(run.started_at, run.ended_at, now)], ["Tokens", (run.tokens_in + run.tokens_out).toLocaleString()], ["Agent calls", agentCalls], ["Tool calls", toolCalls]].map(([k, v]) => (
            <div key={k as string} className="rounded-lg bg-slate-100 py-1.5 dark:bg-slate-900"><dd className="text-sm font-bold">{v}</dd><dt className="text-[11px] text-slate-500">{k}</dt></div>
          ))}
        </dl>
        {stages.length > 0 && (
          <ol className="flex flex-wrap gap-1.5" data-testid="run-stages" aria-label="Stages">
            {stages.map((stage) => (
              <li key={stage.id} className={`flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-semibold ${stage.status === "running" ? "border-indigo-500 bg-indigo-500/10 text-indigo-600 dark:text-indigo-300" : stage.status === "failed" ? "border-rose-500 text-rose-500" : stage.status === "waiting" ? "border-amber-500 text-amber-600 dark:text-amber-400" : "border-emerald-500/40 text-emerald-700 dark:text-emerald-400"}`}>
                {stage.status === "running" ? <Loader2 className="h-3 w-3 animate-spin" /> : stage.status === "failed" ? <XCircle className="h-3 w-3" /> : stage.status === "waiting" ? <Circle className="h-3 w-3" /> : <CheckCircle2 className="h-3 w-3" />}
                {stage.label}
              </li>
            ))}
          </ol>
        )}
        <Link className="text-xs text-indigo-500 underline" href={`/projects/${projectId}/observability?run=${runId}`}>Open full trace</Link>
        {run.status === "failed" && <ErrorNote message={run.error} />}
        {run.status === "interrupted" && <ErrorNote message={`${run.error}. Start it again.`} />}
        {(run.state.branch || run.state.pull_request) && (
          <div className="flex flex-wrap items-center gap-3 text-sm">
            {run.state.branch && <span>Branch <span className="mono text-xs">{run.state.branch}</span></span>}
            {run.state.commit && <span>Commit <span className="mono text-xs">{run.state.commit.slice(0, 10)}</span></span>}
            {run.state.worktree && <a className="text-indigo-500 underline" href={`/api/runs/${run.id}/changes.zip`}>Download changed files</a>}
            {run.state.patch_doc && <a className="text-indigo-500 underline" href={`/api/documents/${run.state.patch_doc}/export/patch`}>Download patch</a>}
            {run.state.pull_request && <a className="text-indigo-500 underline" target="_blank" rel="noreferrer" href={run.state.pull_request.url}>Pull request #{run.state.pull_request.number}</a>}
            {run.state.pull_request && <Button variant="secondary" className="!px-2 !py-1 !text-xs" onClick={async () => { if (confirm("Squash-merge this pull request on GitHub?")) { try { await api(`/runs/${run.id}/merge-pr`, { json: { by: getSigner() || "user" } }); toast("Pull request merged"); } catch (e: any) { toast(e.message, "error"); } } }}>Merge</Button>}
          </div>
        )}
        {run.state.source_files !== undefined && <p className="text-sm" data-testid="scan-coverage">Reviewed <b>{run.state.reviewed_files?.length || 0}</b> of <b>{run.state.source_files}</b> source files{run.state.unreviewed_files?.length ? `. Not reviewed: ${run.state.unreviewed_files.join(", ")}` : ""}</p>}
        {run.state.summary?.verdict && <p className="text-sm">Result <Badge>{run.state.summary.verdict}</Badge> {run.state.summary.passed}/{run.state.summary.executed} tests passed, {run.state.summary.coverage}% requirement coverage</p>}
        {open.map((a: any) => <ApprovalCard key={a.id} approval={a} projectId={projectId} onDecided={decided} />)}
        <LiveLog events={events} live={live} />
        <div className="max-h-[28rem] space-y-1 overflow-y-auto text-xs" data-testid="run-events">
          {stages.map((stage) => (
            <details key={stage.id} open={stage.status === "running" || stage.status === "failed"} className="rounded-lg border border-slate-200 dark:border-slate-800">
              <summary className="cursor-pointer select-none px-2 py-1.5 font-semibold">{stage.label} <span className="font-normal text-slate-500">{stage.agents ? `· ${stage.agents} agent ${stage.agents === 1 ? "call" : "calls"} · ${stage.tokens.toLocaleString()} tokens` : ""}{stage.tools ? ` · ${stage.tools} tool ${stage.tools === 1 ? "call" : "calls"}` : ""}</span></summary>
              <ol className="space-y-0.5 px-2 pb-2">
                {stage.events.map((e: any) => (
                  <li key={e.seq} className="flex gap-1.5">
                    <span className={`${e.type === "tool" ? "mono text-slate-500" : e.type === "error" ? "text-rose-500" : "text-slate-700 dark:text-slate-300"} min-w-0 break-words`}>
                      {e.message}
                      {e.data?.document_id && <> · <Link className="text-indigo-500 underline" href={`/projects/${projectId}/documents/${e.data.document_id}`}>open</Link></>}
                    </span>
                  </li>
                ))}
              </ol>
            </details>
          ))}
        </div>
      </div>
    </Card>
  );
}

function duration(start: string, end: string | null, now: number): string {
  const seconds = Math.max(0, Math.round(((end ? new Date(end).getTime() : now) - new Date(start).getTime()) / 1000));
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function buildStages(events: any[], status: string) {
  const stages: any[] = [];
  const find = (id: string) => stages.find((s) => s.id === id);
  for (const e of events) {
    if (!e.stage) continue;
    let stage = find(e.stage);
    if (!stage) {
      stage = { id: e.stage, label: e.stage.replace(/_/g, " "), status: "done", events: [], tools: 0, agents: 0, tokens: 0 };
      stages.push(stage);
    }
    if (e.type === "stage_start") {
      stage.label = e.message.replace(/^Started /, "");
      stage.status = "running";
    } else if (e.type === "stage_end") stage.status = "done";
    else if (e.type === "approval_required") stage.status = "waiting";
    else if (e.type === "approved") stage.status = "done";
    else if (e.type === "error") stage.status = "failed";
    if (e.type === "tool") stage.tools += 1;
    if (e.type === "agent") {
      stage.agents += 1;
      stage.tokens += e.data?.tokens || 0;
    }
    if (!["stage_start", "stage_end"].includes(e.type)) stage.events.push(e);
  }
  if (status !== "running" && status !== "waiting_approval") for (const stage of stages) if (stage.status === "running") stage.status = status === "failed" ? "failed" : "done";
  return stages;
}

export function RunList({ projectId, workflow, activeId, onPick, refreshKey }: { projectId: string; workflow?: string[]; activeId?: string | null; onPick: (id: string) => void; refreshKey?: unknown }) {
  const [runs, setRuns] = useState<any[]>([]);
  useEffect(() => {
    const load = () => api(`/projects/${projectId}/runs`).then((items) => setRuns(items.filter((r: any) => !workflow || workflow.includes(r.workflow)))).catch(() => {});
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, refreshKey]);
  if (!runs.length) return null;
  return (
    <ul className="divide-y divide-slate-200 text-sm dark:divide-slate-800">
      {runs.slice(0, 8).map((r) => (
        <li key={r.id}>
          <button onClick={() => onPick(r.id)} className={`flex w-full items-center justify-between gap-2 px-1 py-1.5 text-left hover:bg-slate-100 dark:hover:bg-slate-900 ${activeId === r.id ? "font-semibold" : ""}`}>
            <span className="truncate">{r.workflow} · {when(r.started_at)}</span>
            <Badge>{r.status}</Badge>
          </button>
        </li>
      ))}
    </ul>
  );
}
