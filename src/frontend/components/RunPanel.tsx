"use client";

import { CheckCircle2, Circle, ClipboardCopy, FileText, Loader2, RotateCcw, XCircle } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, when } from "../lib/api";
import { useAuth } from "./AuthGate";
import { Badge, Button, Card, ErrorNote, Field, inputClass, useToast } from "./ui";

const verdictTone = (v: string) => (v === "APPROVED" ? "emerald" : v === "REVISE" ? "amber" : v === "REJECT" ? "rose" : "slate");

/** One row per case, as code judged it: the total is the sum of the scores and the verdict follows the rule, whatever the reviewer wrote. */
function CaseTable({ records }: { records: any[] }) {
  return (
    <div className="max-h-96 overflow-auto rounded-lg border border-slate-200 dark:border-slate-700" data-testid="case-table">
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-slate-100 dark:bg-slate-800"><tr><th className="p-1.5">Case</th><th className="p-1.5">Total</th><th className="p-1.5">Verdict</th><th className="p-1.5">Evidence</th><th className="p-1.5">Low</th><th className="p-1.5">Flaws, with file, line and fix</th></tr></thead>
        <tbody>
          {records.map((r: any) => (
            <tr key={r.tc_id} className="border-t border-slate-200 align-top dark:border-slate-700" data-testid="case-row" data-verdict={r.verdict}>
              <td className="mono p-1.5">{r.tc_id}{r.round === 2 && <span className="ml-1 text-[10px] text-slate-500">revised once</span>}</td>
              <td className="p-1.5">{r.total === null || r.total === undefined ? "not run" : <>{r.total}{r.capped && <span className="ml-1 text-[10px] text-rose-500">capped from {r.total_before}</span>}</>}</td>
              <td className="p-1.5"><Badge tone={verdictTone(r.verdict)}>{r.verdict}</Badge></td>
              <td className="p-1.5">{r.evidence}</td>
              <td className="p-1.5" title={r.low_reason}>{r.low ? "low" : ""}</td>
              <td className="p-1.5">
                {(r.flaws || []).map((f: any, i: number) => <div key={i}><span className="mono">{f.file ? `${f.file}${f.line ? `:${f.line}` : ""}` : f.evidence}</span>: {f.dimension ? `${f.dimension}. ` : ""}Fix: {f.fix}</div>)}
                {(r.problems || []).map((p: string, i: number) => <div key={`p${i}`} className="text-slate-500">{p}</div>)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConfidenceNote({ review }: { review?: any }) {
  if (!review) return null;
  const tone = review.score === null ? "amber" : review.score >= 85 ? "emerald" : review.score >= 70 ? "amber" : "rose";
  const c = review.counts;
  return (
    <div className="space-y-1.5 text-sm" data-testid="confidence">
      <span className="flex flex-wrap items-center gap-2"><b>Independent confidence review</b> <Badge tone={tone}>{review.score === null ? "not run" : `${review.score} of 100`}</Badge> <Badge>{review.verdict}</Badge></span>
      {c && <p className="text-xs text-slate-600 dark:text-slate-400" data-testid="confidence-counts">{c.cases} reviewed: {c.approved} approved, {c.revise} revise, {c.reject} reject, {c.not_run} not run. {c.evidence_missing} cite evidence that is not on disk.{review.capped ? ` ${review.capped} failed tests are capped at 60.` : ""}{review.tokens?.total ? ` Review used ${review.tokens.total} tokens (${review.tokens.review} reviewing, ${review.tokens.revise} revising).` : ""}</p>}
      {review.records?.length > 0 ? <CaseTable records={review.records} /> : review.issues?.length > 0 && <ul className="mt-1 list-disc pl-5 text-xs text-slate-600 dark:text-slate-400">{review.issues.slice(0, 8).map((issue: string, i: number) => <li key={i}>{issue}</li>)}</ul>}
    </div>
  );
}

/** What happened, what to do, and the technical detail collapsed. The failure record is already redacted by the server. */
function FailureCard({ run, onRetry, busy }: { run: any; onRetry: () => void; busy: boolean }) {
  const toast = useToast();
  const f = run.failure;
  if (!f) return <ErrorNote message={run.status === "interrupted" ? `${run.error}. Retry the failed stage.` : run.error} />;
  const diagnostics = () =>
    [`Run ${run.id} (${run.workflow}) ${run.status}`, `Error ${f.id} ${f.code} at stage ${f.stage || "-"}`, f.message, `Action: ${f.action}`,
      `Agent ${f.agent || "-"} attempt ${f.attempt ?? "-"} prompt ${f.prompt_ref || "-"} model ${f.model || "-"} finish ${f.finish_reason || "-"}`,
      `Tokens ${f.tokens_in ?? "-"}/${f.tokens_out ?? "-"} in ${f.duration_ms ?? "-"} ms`,
      f.parse_pos != null ? `Parser position ${f.parse_pos}: ${JSON.stringify(f.parse_context)}` : "",
      f.provider_status ? `Provider status ${f.provider_status} request ${f.provider_request_id || "-"}` : "", f.technical, f.stack].filter(Boolean).join("\n");
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(diagnostics());
      toast("Diagnostics copied (secrets are masked)");
    } catch {
      toast("Copy failed. Open the technical detail and copy it by hand.", "error");
    }
  };
  return (
    <div role="alert" className="space-y-2 rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-sm" data-testid="failure-card">
      <div className="flex flex-wrap items-center gap-2"><b>What happened</b> <Badge tone="rose">{f.code}</Badge>{f.stage && <span className="text-xs text-slate-500">in {f.stage}</span>}</div>
      <p>{f.message}</p>
      <p><b>What to do:</b> {f.action}</p>
      <details className="text-xs">
        <summary className="cursor-pointer select-none font-semibold">Technical detail (error {f.id})</summary>
        <pre className="mono mt-1 max-h-64 overflow-auto whitespace-pre-wrap rounded bg-[#070d1f] p-2 text-slate-300">{diagnostics()}</pre>
      </details>
      <div className="flex gap-2">
        <Button variant="primary" busy={busy} onClick={onRetry}><RotateCcw className="mr-1 inline h-3.5 w-3.5" />Retry failed stage</Button>
        <Button variant="secondary" onClick={copy}><ClipboardCopy className="mr-1 inline h-3.5 w-3.5" />Copy diagnostics</Button>
      </div>
    </div>
  );
}

function LiveLog({ events, live }: { events: any[]; live: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  const [follow, setFollow] = useState(true);
  useEffect(() => {
    if (follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [events, follow]);
  const color: Record<string, string> = { error: "text-rose-400", warning: "text-amber-400", review: "text-sky-300", test: "text-emerald-300", artifact: "text-emerald-300", agent: "text-indigo-300", agent_call: "text-indigo-300", skill: "text-fuchsia-300", tool: "text-slate-400" };
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
  const { user } = useAuth();
  const [feedback, setFeedback] = useState("");
  const [openPr, setOpenPr] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [project, setProject] = useState<any>(null);
  useEffect(() => { api(`/projects/${projectId}`).then(setProject).catch(() => {}); }, [projectId]);
  const payload = approval.payload || {};
  const rejects = (payload.confidence?.records || []).filter((r: any) => r.verdict === "REJECT");
  // The server is the real check; this only hides what it would refuse
  const allowed = !project || (approval.gate === null || approval.gate === undefined ? project.can_write : project.can_sign.includes(approval.gate));
  const decide = async (approved: boolean) => {
    setBusy(true);
    setError("");
    try {
      await api(`/approvals/${approval.id}/decide`, { json: { approved, feedback, open_pr: openPr } });
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
      {payload.partial && <div role="alert" className="rounded-lg border border-rose-500/50 bg-rose-500/10 p-2 text-sm" data-testid="partial-result"><b>Partial result, not complete.</b> Missing: {payload.partial.missing.join(", ")}. It cannot be approved. Send it back, or fix the cause ({payload.partial.codes.join(", ")}) and run the stage again.</div>}
      {payload.documents && (
        <ul className="flex flex-wrap gap-2 text-sm">
          {payload.documents.map((doc: string, i: number) => (
            <li key={doc}><Link className="text-indigo-500 underline" target="_blank" href={`/projects/${projectId}/documents/${doc}`}>Open {payload.titles?.[i] || "document"}</Link></li>
          ))}
        </ul>
      )}
      <ConfidenceNote review={payload.confidence || payload.verification?.confidence} />
      {payload.case_limit && <p className="text-sm" data-testid="case-limit">{payload.case_limit.message}{payload.case_limit.left_out_count ? `: ${payload.case_limit.left_out.join(", ")}` : ""}</p>}
      {payload.estimate && <p className="text-xs text-slate-600 dark:text-slate-400" data-testid="token-estimate">Tokens used so far {payload.estimate.used_so_far}. Next: {payload.estimate.next_step}. {payload.estimate.estimated_tokens === null ? payload.estimate.basis : `Estimate about ${payload.estimate.estimated_tokens} tokens (${payload.estimate.expected_calls} calls at ${payload.estimate.average_tokens_per_call}). ${payload.estimate.basis}.`}</p>}
      {payload.emit_unresolved?.length > 0 && <div role="alert" className="rounded-lg border border-amber-500/50 p-2 text-sm" data-testid="emit-unresolved"><b>{payload.emit_unresolved.length} tests still fail the static checks:</b>{payload.emit_unresolved.map((u: any) => <div key={u.path} className="mono text-xs">{u.path}: {u.findings[0]}</div>)}</div>}
      {payload.execution_summary && <p className="text-sm" data-testid="execution-summary">{payload.execution_summary.text} <span className="text-xs">({payload.execution_summary.source === "agent" ? "written by the qa-execution-engineer and checked against the JUnit counts" : "written by code"})</span></p>}
      {payload.defect_records?.length > 0 && (
        <table className="w-full text-left text-xs" data-testid="defect-records">
          <thead><tr><th>Test</th><th>Class</th><th>Cause</th><th>Fix</th></tr></thead>
          <tbody>{payload.defect_records.map((r: any) => <tr key={r.test}><td className="mono">{r.test}</td><td>{r.classification}</td><td>{r.cause}</td><td>{r.fix}</td></tr>)}</tbody>
        </table>
      )}
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
        <Field label="Signing as"><p className="py-2 text-sm font-semibold" data-testid="signing-as">{user.username}</p></Field>
        <Field label={rejects.length ? `Reason (required: ${rejects.length} item${rejects.length > 1 ? "s are" : " is"} REJECT, and it is written to the ledger if you approve)` : "Feedback (required to send back)"}><input className={inputClass} data-testid="reject-reason" value={feedback} onChange={(e) => setFeedback(e.target.value)} placeholder={rejects.length ? "Why these can be accepted" : "What should change"} /></Field>
      </div>
      {payload.can_open_pr && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={openPr} onChange={(e) => setOpenPr(e.target.checked)} /> Push the branch and open a pull request</label>}
      <ErrorNote message={error} />
      {!allowed && <p className="text-xs text-slate-500" data-testid="cannot-sign">Your role cannot {approval.gate == null ? "approve here" : `sign gate G${approval.gate}`}. Ask the project owner or an administrator.</p>}
      <div className="flex gap-2">
        <Button variant="success" busy={busy} disabled={!!payload.partial || !allowed || (rejects.length > 0 && !feedback.trim())} onClick={() => decide(true)}>Approve</Button>
        <Button variant="danger" busy={busy} disabled={!feedback.trim() || !allowed} onClick={() => decide(false)}>Send back</Button>
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

  const follow = async () => {
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
  const decided = async () => {
    toast("Decision recorded");
    await follow();
  };
  const [retrying, setRetrying] = useState(false);
  const retry = async () => {
    setRetrying(true);
    try {
      await api(`/runs/${runId}/retry`, { method: "POST" });
      toast("Retrying from the failed stage");
      await follow();
    } catch (e: any) {
      toast(e.message, "error");
    } finally {
      setRetrying(false);
    }
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
        {(run.status === "failed" || run.status === "interrupted") && <FailureCard run={run} onRetry={retry} busy={retrying} />}
        {(run.state.branch || run.state.pull_request) && (
          <div className="flex flex-wrap items-center gap-3 text-sm">
            {run.state.branch && <span>Branch <span className="mono text-xs">{run.state.branch}</span></span>}
            {run.state.commit && <span>Commit <span className="mono text-xs">{run.state.commit.slice(0, 10)}</span></span>}
            {run.state.worktree && <a className="text-indigo-500 underline" href={`/api/runs/${run.id}/changes.zip`}>Download changed files</a>}
            {run.state.patch_doc && <a className="text-indigo-500 underline" href={`/api/documents/${run.state.patch_doc}/export/patch`}>Download patch</a>}
            {run.state.pull_request && <a className="text-indigo-500 underline" target="_blank" rel="noreferrer" href={run.state.pull_request.url}>Pull request #{run.state.pull_request.number}</a>}
            {run.state.pull_request && <Button variant="secondary" className="!px-2 !py-1 !text-xs" onClick={async () => { if (confirm("Squash-merge this pull request on GitHub?")) { try { await api(`/runs/${run.id}/merge-pr`, { method: "POST" }); toast("Pull request merged"); } catch (e: any) { toast(e.message, "error"); } } }}>Merge</Button>}
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
