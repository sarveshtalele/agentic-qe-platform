"use client";

import { useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { Badge, Card, Empty, ErrorNote, PageTitle, Spinner } from "../../components/ui";
import { api } from "../../lib/api";

/** Read-only list of the plugin skills the agents use. A skill reaches an agent as text in its message, not through a tool. */
export default function SkillsPage() {
  const [data, setData] = useState<{ skills: any[]; problems: string[] } | null>(null);
  const [open, setOpen] = useState("");
  const [detail, setDetail] = useState<any>(null);
  const [error, setError] = useState("");
  useEffect(() => { api("/skills").then(setData).catch((e) => setError(e.message)); }, []);
  const show = async (name: string) => {
    if (open === name) return setOpen("");
    setOpen(name);
    setDetail(null);
    try { setDetail(await api(`/skills/${name}`)); } catch (e: any) { setError(e.message); }
  };
  return (
    <AppShell>
      <PageTitle title="Skills" subtitle="The agentic-qe plugin skills, loaded and checked by Microsoft Agent Framework. Each is sent to its agent as text in the message." />
      <ErrorNote message={error} />
      {!data ? (!error && <Spinner />) : (
        <div className="space-y-3" data-testid="skill-list">
          {data.problems.map((p) => <p key={p} role="alert" className="text-xs text-rose-500">{p}</p>)}
          {!data.skills.length && <Empty title="No skills loaded" />}
          {data.skills.map((s) => (
            <Card key={s.name} title={<span data-testid="skill-name">{s.name}</span>} actions={<button className="text-xs text-indigo-500 underline" onClick={() => show(s.name)}>{open === s.name ? "Hide text" : "Show text"}</button>}>
              <div data-testid="skill-card" className="space-y-1.5 text-sm">
                <p>{s.description}</p>
                <p className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                  <Badge>{`v${s.version || "?"}`}</Badge>
                  {s.agents.length ? s.agents.map((a: string) => <Badge key={a} tone="indigo">{a}</Badge>) : <Badge tone="amber">no agent</Badge>}
                  <span>{s.chars.toLocaleString()} characters</span>
                </p>
                <p className="mono text-xs text-slate-500" data-testid="skill-references">References: {s.references.length ? s.references.join(", ") : "none"}</p>
                {open === s.name && (detail ? <pre className="mono max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-100 p-3 text-xs dark:bg-slate-900">{detail.body}</pre> : <Spinner />)}
              </div>
            </Card>
          ))}
        </div>
      )}
    </AppShell>
  );
}
