"use client";

import { Play } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { Badge, Button, Card, ErrorNote, inputClass } from "./ui";

// What a tile or row reads. A value exists only when the metric really ran; every other state says why not.
export function scoreText(m: any): string {
  if (m.state === "measured") return `${Math.round(m.value * 100)}%`;
  return { "n/a": "n/a", not_measured: "Not measured", failed: "Failed", unavailable: "Not available", inconclusive: "Inconclusive" }[m.state as string] ?? "Not measured";
}

function tone(m: any): string | undefined {
  if (m.state !== "measured") return undefined;
  return m.value >= 0.8 ? "emerald" : m.value >= 0.5 ? "amber" : "rose";
}

export function Tile({ m }: { m: any }) {
  const colors: Record<string, string> = { emerald: "text-emerald-600", amber: "text-amber-600", rose: "text-rose-600" };
  const note = m.state === "measured" ? [m.self_graded ? "self-graded" : "", m.labels === "not reviewed" || m.labels_reviewed === false ? "labels not yet reviewed" : ""].filter(Boolean).join(", ") : "";
  return (
    <span className="rounded-lg border border-slate-200 p-2 dark:border-slate-800" data-testid="metric-tile" title={m.reason || (m.state === "n/a" ? "This metric does not apply to this agent" : "")}>
      <span className={`block text-base font-bold ${colors[tone(m) ?? ""] ?? "text-slate-500"}`}>{scoreText(m)}</span>
      <span className="block text-[11px] text-slate-500">{m.label}</span>
      {note && <span className="block text-[10px] text-amber-600">{note}</span>}
    </span>
  );
}

export function Tiles({ tiles }: { tiles?: any[] }) {
  if (!tiles) return null;
  return <span className="mt-3 grid grid-cols-4 gap-1.5" data-testid="metric-tiles">{tiles.map((t) => <Tile key={t.metric} m={t} />)}</span>;
}

const CONTEXT_SHOWN = 1200;

export function AgentScores({ agentKey, admin, enabled }: { agentKey: string; admin: boolean; enabled: boolean }) {
  const [data, setData] = useState<any>(null);
  const [setup, setSetup] = useState<any>(null);
  const [benchmark, setBenchmark] = useState("");
  const [repeats, setRepeats] = useState(1);
  const [ragas, setRagas] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => api(`/agents/${agentKey}/metrics`).then(setData).catch((e) => setError(e.message)), [agentKey]);
  useEffect(() => {
    load();
    api("/evals/cards").then(setSetup).catch(() => {});
  }, [load]);
  const run = async () => {
    setRunning(true);
    setError("");
    try {
      setResult(await api(`/agents/${agentKey}/evals`, { json: { benchmark, repeats, ragas } }));
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  };
  if (!data) return <Card title="Scores"><ErrorNote message={error} />{!error && <p className="text-sm text-slate-500">Loading</p>}</Card>;
  return (
    <Card title="Scores" actions={admin && <Button variant="secondary" busy={running} disabled={!enabled} onClick={run}><Play className="h-4 w-4" /> Measure</Button>}>
      <div data-testid="agent-scores">
        {data.recall_basis && <p className="mb-2 text-xs text-slate-500">Recall and F1 are measured against: {data.recall_basis}. Agent-specific: {data.agent_measure}.</p>}
        {admin && (
          <div className="mb-3 flex flex-wrap items-end gap-3 text-xs">
            <label>Benchmark<select aria-label="Benchmark" className={`${inputClass} mt-1`} value={benchmark} onChange={(e) => setBenchmark(e.target.value)}><option value="">Agent cases only</option>{(setup?.benchmarks ?? []).map((b: string) => <option key={b} value={b}>{b}</option>)}</select></label>
            <label>Repeats<select aria-label="Repeats" className={`${inputClass} mt-1`} value={repeats} onChange={(e) => setRepeats(Number(e.target.value))}>{[1, 2, 3, 5].map((n) => <option key={n} value={n}>{n}</option>)}</select></label>
            <label className="flex items-center gap-1.5"><input type="checkbox" checked={ragas} onChange={(e) => setRagas(e.target.checked)} /> Include model-graded metrics (uses tokens)</label>
            {setup && <span className="text-slate-500">{setup.ragas.installed ? `RAGAS installed. Judge: ${setup.ragas.judge_model || "none set, so scores are self-graded"}` : setup.ragas.reason}</span>}
          </div>
        )}
        <ErrorNote message={error} />
        {result && <p className="mb-2 text-xs text-slate-500" data-testid="eval-tokens">Last measurement used {result.tokens_total.toLocaleString()} tokens in {result.repeats} run(s){result.labels_reviewed === false ? ". Labels not yet reviewed" : ""}.</p>}
        <table className="w-full text-left text-xs" data-testid="metric-table"><thead className="text-slate-500"><tr><th className="py-1">Metric</th><th>Value</th><th>Items</th><th>Judge</th><th>Notes</th></tr></thead><tbody>
          {data.metrics.map((m: any) => (
            <tr key={m.metric} className="border-t border-slate-200 dark:border-slate-800">
              <td className="py-1">{m.label}</td><td className="font-semibold">{scoreText(m)}</td><td>{m.state === "measured" ? m.n : ""}</td><td>{m.judge_model || ""}</td>
              <td className="text-slate-500">{[m.self_graded ? "self-graded" : "", m.labels_reviewed === false ? "labels not yet reviewed" : "", m.state !== "measured" ? m.reason ?? "" : ""].filter(Boolean).join("; ")}</td>
            </tr>
          ))}
        </tbody></table>
        {data.live.replies > 0 && <p className="mt-2 text-xs text-slate-500" data-testid="live-groundedness">Live groundedness on real runs: {Math.round(data.live.mean * 100)}% over {data.live.citations} citations in {data.live.replies} replies.</p>}
        {data.trend.length > 0 && (
          <div className="mt-3" data-testid="metric-trend">
            <h4 className="text-xs font-semibold">By prompt version</h4>
            <table className="w-full text-left text-xs"><tbody>{data.trend.map((t: any) => (
              <tr key={t.metric} className="border-t border-slate-200 dark:border-slate-800"><td className="py-1">{t.metric.replace(/_/g, " ")}</td><td>{t.points.map((p: any) => <span key={p.prompt_ref} className="mr-3"><span className="mono">{p.prompt_ref.split(":")[0].split("@")[1]}</span> {Math.round(p.mean * 100)}%{p.runs > 1 ? ` (${Math.round(p.min * 100)} to ${Math.round(p.max * 100)}, ${p.runs} runs)` : ""}</span>)}</td></tr>
            ))}</tbody></table>
          </div>
        )}
        {Object.keys(data.spread).length > 0 && <p className="mt-2 text-xs text-slate-500" data-testid="metric-spread">Spread over repeated runs: {Object.entries<any>(data.spread).filter(([, s]) => s.runs > 1).map(([k, s]) => `${k.replace(/_/g, " ")} ${Math.round(s.min * 100)}% to ${Math.round(s.max * 100)}%`).join(", ") || "run more than once to see it"}</p>}
        <div className="mt-3" data-testid="score-cases">
          <h4 className="text-xs font-semibold">Cases of the latest run, worst first</h4>
          {data.cases.length ? data.cases.map((c: any) => (
            <details key={c.name} className="border-t border-slate-200 py-1 text-xs dark:border-slate-800">
              <summary className="cursor-pointer">{c.passed === null ? <Badge tone="amber">needs grader</Badge> : <Badge tone={c.passed ? "emerald" : "rose"}>{c.passed ? "pass" : "fail"}</Badge>} {c.name.replace(/_/g, " ")} {c.reason && <span className="text-rose-500">{c.reason.slice(0, 140)}</span>}</summary>
              {c.question && <p className="mt-1"><b>Question</b> <span className="mono whitespace-pre-wrap">{c.question}</span></p>}
              {c.context && <p className="mt-1"><b>Context</b> <span className="mono whitespace-pre-wrap">{c.context.slice(0, CONTEXT_SHOWN)}{c.context.length > CONTEXT_SHOWN ? " ..." : ""}</span></p>}
              {c.answer && <p className="mt-1"><b>Answer</b> <span className="mono whitespace-pre-wrap">{c.answer}</span></p>}
              {c.reason && <p className="mt-1"><b>Reason</b> {c.reason}</p>}
              {c.grades && <ul className="mt-1">{c.grades.map((g: any, i: number) => <li key={i}><Badge tone={g.verdict === "PASS" ? "emerald" : "rose"}>{g.verdict}</Badge> {g.expectation} {g.evidence && <span className="mono text-slate-500">&quot;{g.evidence}&quot;</span>} {g.verdict !== "PASS" && g.reason}</li>)}</ul>}
            </details>
          )) : <p className="text-xs text-slate-500">No run yet.</p>}
        </div>
      </div>
    </Card>
  );
}

// Scores of each prompt version beside the active one, for the Prompts page.
export function VersionScores({ agent, versions }: { agent: string; versions: any[] }) {
  const [scores, setScores] = useState<any>(null);
  useEffect(() => {
    api(`/prompts/${agent}/scores`).then(setScores).catch(() => setScores({}));
  }, [agent, versions]);
  if (!scores) return null;
  const cols: [string, string][] = [["groundedness", "Groundedness"], ["faithfulness", "Faithfulness"], ["recall", "Recall"], ["f1", "F1"]];
  const cell = (ref: string, metric: string) => (scores[ref]?.[metric] ? `${Math.round(scores[ref][metric].value * 100)}%` : "Not measured");
  return (
    <table className="w-full text-left text-xs" data-testid="prompt-scores"><thead className="text-slate-500"><tr><th className="py-1">Version</th>{cols.map(([, l]) => <th key={l}>{l}</th>)}</tr></thead><tbody>
      {versions.slice(0, 6).map((p) => {
        const ref = `${agent}@v${p.version}:${p.sha256.slice(0, 12)}`;
        return <tr key={p.version} className="border-t border-slate-200 dark:border-slate-800"><td className="py-1">v{p.version} {p.active && <Badge tone="emerald">active</Badge>}</td>{cols.map(([m]) => <td key={m}>{cell(ref, m)}</td>)}</tr>;
      })}
    </tbody></table>
  );
}
