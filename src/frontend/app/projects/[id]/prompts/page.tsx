"use client";

import { Check, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, ErrorNote, inputClass, PageTitle, Spinner, useToast } from "../../../../components/ui";
import { VersionScores } from "../../../../components/EvalScores";
import { api, when } from "../../../../lib/api";

export default function PromptsPage() {
  const [evalAgents, setEvalAgents] = useState<string[]>([]);
  const [evalRuns, setEvalRuns] = useState<any[]>([]);
  const [evaluating, setEvaluating] = useState(false);
  const [all, setAll] = useState<any[] | null>(null);
  const [agent, setAgent] = useState("");
  const [history, setHistory] = useState<any[]>([]);
  const [body, setBody] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const toast = useToast();
  const loadAll = useCallback(() => api("/prompts").then(setAll), []);
  useEffect(() => {
    loadAll();
    api("/evals").then(setEvalAgents);
  }, [loadAll]);
  const open = async (name: string) => {
    setAgent(name);
    const items = await api(`/prompts/${name}`);
    setHistory(items);
    setBody(items.find((p: any) => p.active)?.body || "");
    setEvalRuns(await api(`/evals/${name}`));
  };
  if (!all) return <Spinner />;
  const agents = [...new Set(all.map((p) => p.agent))];
  const active = history.find((p) => p.active);
  const save = async () => {
    setError("");
    try {
      await api(`/prompts/${agent}`, { json: { body, note } });
      setNote("");
      await open(agent);
      loadAll();
      toast("New prompt version is now active");
    } catch (e: any) {
      setError(e.message);
    }
  };
  return (
    <>
      <PageTitle title="Prompts" subtitle="Prompts are versioned and shared by all projects. Each saved document records the prompt version that wrote it." />
      <div className="grid gap-4 md:grid-cols-[230px_1fr] [&>*]:min-w-0">
        <Card>
          <ul className="space-y-0.5 text-sm">{agents.map((name) => {
            const latest = all.find((p) => p.agent === name && p.active);
            return <li key={name}><button onClick={() => open(name)} className={`flex w-full items-center justify-between rounded px-2 py-1 text-left hover:bg-slate-100 dark:hover:bg-slate-900 ${agent === name ? "bg-indigo-600/15 font-semibold" : ""}`}><span className="truncate">{name.replace(/_/g, " ")}</span><span className="text-xs text-slate-500">v{latest?.version}</span></button></li>;
          })}</ul>
        </Card>
        {agent ? (
          <div className="space-y-4">
            <Card title={<span>{agent.replace(/_/g, " ")} <span className="mono text-xs font-normal text-slate-500">active v{active?.version}</span></span>}>
              <textarea aria-label="Prompt body" className={`${inputClass} mono min-h-64 text-[13px]`} value={body} onChange={(e) => setBody(e.target.value)} />
              <div className="mt-2 flex flex-wrap gap-2">
                <input aria-label="Reason for change" className={`${inputClass} max-w-md`} placeholder="Reason for this change (required)" value={note} onChange={(e) => setNote(e.target.value)} />
                <Button onClick={save} disabled={!note.trim() || body === active?.body}><Save className="h-4 w-4" /> Save new version</Button>
              </div>
              <ErrorNote message={error} />
            </Card>
            {evalAgents.includes(agent) && (
              <Card title="Evaluations" actions={<Button variant="secondary" busy={evaluating} onClick={async () => { setEvaluating(true); setError(""); try { await api(`/agents/${agent}/evals`, { method: "POST" }); setEvalRuns(await api(`/evals/${agent}`)); } catch (e: any) { setError(e.message); } finally { setEvaluating(false); } }}>Run with the real model</Button>}>
                {evalRuns.length ? <ul className="space-y-1 text-sm">{evalRuns.map((r) => <li key={r.id} className="flex items-center justify-between gap-2"><span className="mono truncate text-xs">{r.prompt_ref}</span><span className="flex shrink-0 items-center gap-2 text-xs">{when(r.created_at)} <Badge tone={r.passed === r.total ? "emerald" : "rose"}>{`${r.passed}/${r.total} passed`}</Badge></span></li>)}</ul> : <p className="text-sm text-slate-500">Not evaluated yet.</p>}
              </Card>
            )}
            {evalAgents.includes(agent) && <Card title="Scores by version"><VersionScores agent={agent} versions={history} /><p className="mt-2 text-[11px] text-slate-500">Measure a new version on the agent page before relying on these numbers. A version never measured reads Not measured.</p></Card>}
            <Card title="History">
              <ul className="divide-y divide-slate-200 text-sm dark:divide-slate-800">{history.map((p) => (
                <li key={p.version} className="flex items-center justify-between gap-2 py-1.5">
                  <span className="min-w-0"><b>v{p.version}</b> <span className="text-xs text-slate-500">{p.author_name} · {when(p.created_at)} · {p.note}</span></span>
                  {p.active ? <Badge tone="emerald">active</Badge> : <Button variant="secondary" className="!px-2 !py-1 !text-xs" onClick={async () => { await api(`/prompts/${agent}/activate/${p.version}`, { method: "POST" }); await open(agent); loadAll(); toast(`Rolled back to v${p.version}`); }}><Check className="h-3 w-3" /> Activate</Button>}
                </li>
              ))}</ul>
            </Card>
          </div>
        ) : <p className="text-sm text-slate-500">Choose an agent to view its prompt.</p>}
      </div>
    </>
  );
}
