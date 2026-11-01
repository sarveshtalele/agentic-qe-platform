"use client";

import { Play, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { Badge, Button, Card, Empty, ErrorNote, Field, inputClass, PageTitle, Spinner, useToast } from "../../components/ui";
import { api, getSigner, setSigner, when } from "../../lib/api";

const riskTone: Record<string, string> = { low: "emerald", medium: "amber", high: "rose" };

function Detail({ agentKey, onChange }: { agentKey: string; onChange: () => void }) {
  const [item, setItem] = useState<any>(null);
  const [by, setBy] = useState("");
  const [reason, setReason] = useState("");
  const [limit, setLimit] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();
  const load = useCallback(async () => {
    const data = await api(`/agents/${agentKey}`);
    setItem(data);
    setLimit(String(data.token_limit));
  }, [agentKey]);
  useEffect(() => {
    load();
    setBy(getSigner());
  }, [load]);
  if (!item) return <Spinner />;
  const save = async (enabled: boolean) => {
    setError("");
    try {
      setSigner(by);
      await api(`/agents/${agentKey}/settings`, { method: "PUT", json: { enabled, max_tokens: Number(limit) || null, by, reason } });
      setReason("");
      await load();
      onChange();
      toast("Agent settings saved");
    } catch (e: any) {
      setError(e.message);
    }
  };
  const evaluate = async () => {
    setRunning(true);
    setError("");
    try {
      await api(`/agents/${agentKey}/evals`, { method: "POST" });
      await load();
      onChange();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  };
  const latest = item.evals[0];
  return (
    <div className="space-y-4" data-testid="agent-detail">
      <Card title={item.name} actions={<Badge tone={item.enabled ? "emerald" : "rose"}>{item.enabled ? "enabled" : "disabled"}</Badge>}>
        <p className="text-sm text-slate-600 dark:text-slate-400">{item.purpose}</p>
        <dl className="mt-3 space-y-1 text-xs">
          <div><b>Prompt:</b> <span className="mono">{item.prompt_ref}</span></div>
          <div><b>Workflow tools:</b> <span className="mono">{item.workflow_tools.join(", ") || "none, works only from the text it is given"}</span></div>
          <div><b>Chat tools:</b> <span className="mono">{item.in_chat ? item.chat_tools.join(", ") : "not offered in chat"}</span></div>
          <div><b>Can change code:</b> {item.can_change_code ? "yes, on a branch, after human review" : "no"}</div>
          {item.settings_by && <div><b>Last changed by:</b> {item.settings_by}{item.settings_reason ? `: ${item.settings_reason}` : ""}</div>}
        </dl>
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          <Field label="Your name"><input className={inputClass} value={by} onChange={(e) => setBy(e.target.value)} /></Field>
          <Field label="Reason"><input className={inputClass} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
          <Field label="Tokens per model call"><input type="number" min={500} max={64000} className={inputClass} value={limit} onChange={(e) => setLimit(e.target.value)} /></Field>
        </div>
        <ErrorNote message={error} />
        <div className="mt-2 flex gap-2">
          <Button variant="secondary" disabled={!by.trim()} onClick={() => save(item.enabled)}>Save limit</Button>
          {item.enabled ? <Button variant="danger" disabled={!by.trim() || !reason.trim()} onClick={() => save(false)}>Disable agent</Button> : <Button variant="success" disabled={!by.trim()} onClick={() => save(true)}>Enable agent</Button>}
        </div>
      </Card>
      <Card title="Evaluations" actions={item.has_evals && <Button variant="secondary" busy={running} disabled={!item.enabled} onClick={evaluate}><Play className="h-4 w-4" /> Run on the real model</Button>}>
        {latest ? (
          <>
            <p className="mb-2 text-xs text-slate-500">Latest on <span className="mono">{latest.prompt_ref}</span>, {when(latest.created_at)}</p>
            <ul className="space-y-1 text-sm">{latest.results.map((r: any) => (
              <li key={r.name}>
                <Badge tone={r.passed ? "emerald" : "rose"}>{r.passed ? "pass" : "fail"}</Badge> <Badge>{r.category}</Badge> {r.name.replace(/_/g, " ")}
                {!r.passed && <p className="mono ml-1 text-xs text-rose-500">{r.failed_checks.join("; ")}</p>}
              </li>
            ))}</ul>
          </>
        ) : <p className="text-sm text-slate-500">Not evaluated yet.</p>}
      </Card>
      <Card title={`Recent model calls (${item.calls_recent.length})`}>
        {item.calls_recent.length ? (
          <div className="max-h-64 overflow-auto"><table className="w-full text-left text-xs"><thead className="text-slate-500"><tr><th className="py-1">When</th><th>Source</th><th>Tokens</th><th>ms</th><th>Tools</th><th>Status</th></tr></thead>
            <tbody>{item.calls_recent.map((c: any) => <tr key={c.id} className="border-t border-slate-200 dark:border-slate-800" title={c.error}><td className="py-1">{when(c.created_at)}</td><td>{c.source}</td><td>{c.tokens_in + c.tokens_out}</td><td>{c.latency_ms}</td><td>{c.tool_calls}</td><td><Badge tone={c.status === "ok" ? "emerald" : "rose"}>{c.status}</Badge></td></tr>)}</tbody></table></div>
        ) : <p className="text-sm text-slate-500">No calls recorded.</p>}
      </Card>
      {item.events_recent.length > 0 && (
        <Card title="Guardrail events">
          <ul className="space-y-1 text-xs">{item.events_recent.map((e: any) => <li key={e.id}><Badge tone="amber">{e.action}</Badge> <b>{e.kind.replace(/_/g, " ")}</b> {e.detail} <span className="text-slate-500">{when(e.created_at)}</span></li>)}</ul>
        </Card>
      )}
    </div>
  );
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<any[] | null>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [selected, setSelected] = useState("");
  const [running, setRunning] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    api("/agents").then(setAgents).catch((e) => setError(e.message));
    api("/agents/guardrail-events").then(setEvents);
    setRefresh((n) => n + 1);
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  const runAll = async () => {
    setRunning(true);
    setError("");
    try {
      await api("/agents/evals/run-all", { method: "POST" });
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  };
  if (!agents) return <AppShell><ErrorNote message={error} />{!error && <Spinner />}</AppShell>;
  const evaluated = agents.filter((a) => a.eval);
  const stats = [
    ["Agents", agents.length], ["Enabled", agents.filter((a) => a.enabled).length],
    ["Evaluation cases passed", evaluated.length ? `${evaluated.reduce((n, a) => n + a.eval.passed, 0)}/${evaluated.reduce((n, a) => n + a.eval.total, 0)}` : "Not run"],
    ["Model calls", agents.reduce((n, a) => n + a.calls, 0)], ["Tokens", agents.reduce((n, a) => n + a.tokens, 0).toLocaleString()], ["Guardrail events", agents.reduce((n, a) => n + a.guardrail_events, 0)],
  ];
  return (
    <AppShell>
      <PageTitle title="Agents" subtitle="Policy, evaluations, guardrails, and live usage for every agent. All figures come from recorded calls." actions={<Button busy={running} onClick={runAll}><Play className="h-4 w-4" /> {running ? "Running evaluations" : "Run all evaluations"}</Button>} />
      <ErrorNote message={error} />
      <dl className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-6" data-testid="agent-stats">
        {stats.map(([k, v]) => <div key={k as string} className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-[#0b1329]"><dd className="text-lg font-bold">{v}</dd><dt className="text-[11px] text-slate-500">{k}</dt></div>)}
      </dl>
      <div className={`grid gap-4 ${selected ? "lg:grid-cols-[1fr_420px]" : ""}`}>
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs" data-testid="agents-table">
              <thead className="text-slate-500"><tr><th className="pb-2">Agent</th><th>Risk</th><th>Status</th><th>Prompt</th><th>Evals</th><th>Calls</th><th>Tokens</th><th>Avg ms</th><th>Errors</th><th>Guardrails</th></tr></thead>
              <tbody>{agents.map((a) => (
                <tr key={a.key} className={`border-t border-slate-200 dark:border-slate-800 ${selected === a.key ? "bg-indigo-600/10" : ""}`}>
                  <td className="py-1.5"><button className="text-left font-semibold hover:underline" onClick={() => setSelected(a.key)}>{a.name}</button></td>
                  <td><Badge tone={riskTone[a.risk]}>{a.risk}</Badge></td>
                  <td><Badge tone={a.enabled ? "emerald" : "rose"}>{a.enabled ? "enabled" : "disabled"}</Badge></td>
                  <td className="mono">{a.prompt_ref.split(":")[0].split("@")[1]}</td>
                  <td>{a.eval ? <Badge tone={a.eval.passed === a.eval.total ? (a.eval.current ? "emerald" : "amber") : "rose"}>{`${a.eval.passed}/${a.eval.total}${a.eval.current ? "" : " old prompt"}`}</Badge> : <span className="text-slate-500">Not run</span>}</td>
                  <td>{a.calls}</td><td>{a.tokens.toLocaleString()}</td><td>{a.avg_latency_ms ?? "-"}</td><td>{a.errors}</td><td>{a.guardrail_events}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Card>
        {selected && <Detail key={`${selected}-${refresh}`} agentKey={selected} onChange={load} />}
      </div>
      <div className="mt-4">
        <Card title={<span className="flex items-center gap-1.5"><ShieldAlert className="h-4 w-4 text-amber-500" /> Recent guardrail events</span>}>
          {events.length ? <ul className="max-h-64 space-y-1 overflow-y-auto text-xs">{events.map((e) => <li key={e.id}><Badge tone="amber">{e.action}</Badge> <b>{e.agent}</b> {e.kind.replace(/_/g, " ")}: {e.detail} <span className="text-slate-500">{when(e.created_at)}</span></li>)}</ul> : <Empty title="No guardrail events recorded" />}
        </Card>
      </div>
    </AppShell>
  );
}
