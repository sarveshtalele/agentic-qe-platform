"use client";

import { ArrowLeft, Play } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { useAuth } from "../../../components/AuthGate";
import { Badge, Button, Card, ErrorNote, Field, inputClass, PageTitle, Spinner, useToast } from "../../../components/ui";
import { api, when } from "../../../lib/api";

const RISK_MEANING: Record<string, string> = {
  low: "Low: reads and writes text only. It cannot reach code by itself.",
  medium: "Medium: reads the repository's code, or can act on project data in chat.",
  high: "Impact: changes code. Its edits land on a separate branch and need a person's review.",
};

// what contains an agent that changes code, so the badge reads as a description of its job and not a warning
const CHANGE_CONTROLS: [string, string][] = [
  ["No tools in workflows", "It can only return proposed edits as text."],
  ["Guarded edits", "Code refuses path escapes, secrets, overwrites, deletions, out-of-scope files, and edits that break syntax."],
  ["Separate branch", "Your main code is never touched."],
  ["Real tests and a confidence review", "Run before anyone is asked to decide."],
  ["Named human approval", "Nothing is committed without it, and agents cannot approve."],
  ["Disable switch and token limits", "The admin can stop it at once."],
];

function Detail({ agentKey }: { agentKey: string }) {
  const { user } = useAuth();
  const admin = user?.role === "admin";
  const onChange = () => {};
  const [item, setItem] = useState<any>(null);
  const [reason, setReason] = useState("");
  const [limit, setLimit] = useState("");
  const [model, setModel] = useState("");
  const [choices, setChoices] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();
  const load = useCallback(async () => {
    const data = await api(`/agents/${agentKey}`);
    setItem(data);
    setLimit(String(data.token_limit));
    setModel(data.model || "");
  }, [agentKey]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (user?.role === "admin") api("/models").then((all: any[]) => setChoices(all.filter((m) => m.enabled).map((m) => m.name))).catch(() => setChoices([]));
  }, [user?.role]);
  if (!item) return <Spinner />;
  const save = async (enabled: boolean) => {
    setError("");
    try {
      await api(`/agents/${agentKey}/settings`, { method: "PUT", json: { enabled, max_tokens: Number(limit) || null, reason, model } });
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
      <Card title="Details" actions={<Badge tone={item.enabled ? "emerald" : "rose"}>{item.enabled ? "enabled" : "disabled"}</Badge>}>
        <table className="w-full text-left text-sm" data-testid="agent-details-table"><tbody className="[&_th]:w-48 [&_th]:py-1.5 [&_th]:pr-3 [&_th]:align-top [&_th]:font-semibold [&_tr]:border-t [&_tr]:border-slate-200 dark:[&_tr]:border-slate-800">
          <tr><th>Purpose</th><td>{item.purpose}</td></tr>
          <tr><th>Risk</th><td>{RISK_MEANING[item.risk]}</td></tr>
          {item.risk === "high" && <tr data-testid="impact-controls"><th>Controls on code changes</th><td><ul className="space-y-1 text-xs">{CHANGE_CONTROLS.map(([name, effect]) => <li key={name}><b>{name}.</b> {effect}</li>)}</ul></td></tr>}
          <tr><th>Status</th><td>{item.enabled ? "Enabled" : "Disabled"}</td></tr>
          <tr><th>Prompt version</th><td className="mono text-xs">{item.prompt_ref}</td></tr>
          <tr><th>Workflow tools</th><td className="mono text-xs">{item.workflow_tools.join(", ") || "None. It works only from the text it is given"}</td></tr>
          <tr><th>Chat tools</th><td className="mono text-xs">{item.in_chat ? item.chat_tools.join(", ") : "Not offered in chat"}</td></tr>
          <tr><th>Can change code</th><td>{item.can_change_code ? "Yes, on a branch, after human review" : "No"}</td></tr>
          <tr><th>Tokens per model call</th><td>{item.token_limit.toLocaleString()}</td></tr>
          <tr><th>Evaluations</th><td>{item.eval ? `${item.eval.passed} of ${item.eval.total} passed` : "Not run"}</td></tr>
          <tr><th>Model calls</th><td>{item.calls}</td></tr>
          <tr><th>Tokens used</th><td>{item.tokens.toLocaleString()}</td></tr>
          <tr><th>Average response</th><td>{item.avg_latency_ms === null || item.avg_latency_ms === undefined ? "No calls yet" : `${item.avg_latency_ms} ms`}</td></tr>
          <tr><th>Errors</th><td>{item.errors}</td></tr>
          <tr><th>Guardrail events</th><td>{item.guardrail_events}</td></tr>
          {item.settings_by && <tr><th>Last changed by</th><td>{item.settings_by_name}{item.settings_reason ? `: ${item.settings_reason}` : ""}</td></tr>}
        </tbody></table>
      </Card>
      {admin && <Card title="Controls">
        <div className="mt-3 grid gap-2 md:grid-cols-4">
          <Field label="Signing as"><p className="py-2 text-sm font-semibold" data-testid="signing-as">{user.username}</p></Field>
          <Field label="Reason"><input className={inputClass} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
          <Field label="Tokens per model call"><input type="number" min={500} max={64000} className={inputClass} value={limit} onChange={(e) => setLimit(e.target.value)} /></Field>
          <Field label="Model"><select className={inputClass} value={model} onChange={(e) => setModel(e.target.value)} data-testid="agent-model"><option value="">Each user&apos;s default</option>{[...new Set([...choices, ...(model ? [model] : [])])].map((m) => <option key={m} value={m}>{m}</option>)}</select></Field>
        </div>
        <ErrorNote message={error} />
        <div className="mt-2 flex gap-2">
          <Button variant="secondary" onClick={() => save(item.enabled)}>Save limit</Button>
          {item.enabled ? <Button variant="danger" disabled={!reason.trim()} onClick={() => save(false)}>Disable agent</Button> : <Button variant="success" onClick={() => save(true)}>Enable agent</Button>}
        </div>
      </Card>}
      <Card title="Evaluations" actions={admin && item.has_evals && <Button variant="secondary" busy={running} disabled={!item.enabled} onClick={evaluate}><Play className="h-4 w-4" /> Run on the real model</Button>}>
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

export default function AgentPage() {
  const { key } = useParams<{ key: string }>();
  const [name, setName] = useState("");
  useEffect(() => {
    api(`/agents/${key}`).then((item) => setName(item.name)).catch(() => {});
  }, [key]);
  return (
    <AppShell>
      <Link href="/agents" className="mb-2 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-indigo-500"><ArrowLeft className="h-3 w-3" /> Agents</Link>
      <PageTitle title={name || "Agent"} subtitle="Policy, evaluations, and recorded use for this agent." />
      <Detail agentKey={key} />
    </AppShell>
  );
}
