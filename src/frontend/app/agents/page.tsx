"use client";

import { Play, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthGate";
import { Badge, Button, Card, Empty, ErrorNote, PageTitle, Spinner } from "../../components/ui";
import { api, when } from "../../lib/api";

const riskTone: Record<string, string> = { low: "emerald", medium: "amber", high: "rose" };

export default function AgentsPage() {
  const { user } = useAuth();
  const admin = user?.role === "admin";
  const [agents, setAgents] = useState<any[] | null>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    api("/agents").then(setAgents).catch((e) => setError(e.message));
    if (admin) api("/agents/guardrail-events").then(setEvents);
  }, [admin]);
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
      <PageTitle title="Agents" subtitle="Policy, evaluations, guardrails, and live usage for every agent. All figures come from recorded calls." actions={admin ? <Button busy={running} onClick={runAll}><Play className="h-4 w-4" /> {running ? "Running evaluations" : "Run all evaluations"}</Button> : undefined} />
      <ErrorNote message={error} />
      <dl className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-6" data-testid="agent-stats">
        {stats.map(([k, v]) => <div key={k as string} className="rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-[#0b1329]"><dd className="text-lg font-bold">{v}</dd><dt className="text-[11px] text-slate-500">{k}</dt></div>)}
      </dl>
      <p className="mb-3 text-xs text-slate-500" data-testid="risk-legend"><b>Risk</b> shows what an agent could affect, not how it is behaving. <b>Low</b> handles text only. <b>Medium</b> reads code or acts on project data. <b>High</b> can change code, always on a separate branch with a person&apos;s review.</p>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3" data-testid="agent-cards">
        {agents.map((a) => (
          <Link key={a.key} href={`/agents/${a.key}`} data-testid="agent-card" className="flex flex-col rounded-xl border border-slate-200 bg-white p-4 transition hover:border-indigo-500 dark:border-slate-800 dark:bg-[#0b1329]">
            <span className="flex items-center justify-between gap-2"><b className="text-sm">{a.name}</b><Badge tone={riskTone[a.risk]}>{`${a.risk} risk`}</Badge></span>
            <span className="mt-1 min-h-8 text-xs text-slate-600 dark:text-slate-400">{a.purpose}</span>
            <span className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px]">
              <Badge tone={a.enabled ? "emerald" : "rose"}>{a.enabled ? "enabled" : "disabled"}</Badge>
              <Badge>{a.prompt_ref.split(":")[0].split("@")[1]}</Badge>
              {a.eval ? <Badge tone={a.eval.passed === a.eval.total ? (a.eval.current ? "emerald" : "amber") : "rose"}>{`evals ${a.eval.passed}/${a.eval.total}${a.eval.current ? "" : " old prompt"}`}</Badge> : <Badge>evals not run</Badge>}
            </span>
            <span className="mt-2 text-[11px] text-slate-500">{a.calls} calls · {a.tokens.toLocaleString()} tokens · {a.errors} errors</span>
          </Link>
        ))}
      </div>
      <div className="mt-4">
        <Card title={<span className="flex items-center gap-1.5"><ShieldAlert className="h-4 w-4 text-amber-500" /> Recent guardrail events</span>}>
          {events.length ? <ul className="max-h-64 space-y-1 overflow-y-auto text-xs">{events.map((e) => <li key={e.id}><Badge tone="amber">{e.action}</Badge> <b>{e.agent}</b> {e.kind.replace(/_/g, " ")}: {e.detail} <span className="text-slate-500">{when(e.created_at)}</span></li>)}</ul> : <Empty title="No guardrail events recorded" />}
        </Card>
      </div>
    </AppShell>
  );
}
