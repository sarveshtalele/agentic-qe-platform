"use client";

import { Play } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useProject } from "../../../../components/ProjectShell";
import { RunList, RunPanel } from "../../../../components/RunPanel";
import { Badge, Button, Card, ErrorNote, PageTitle } from "../../../../components/ui";
import { api } from "../../../../lib/api";

const STAGES = [["Intake", "G0", "intake"], ["Discovery", "", "discovery"], ["Requirements", "G1", "requirements"], ["Test plan", "G2", "test_plan"], ["Test design", "G3", "test_cases"], ["Generate", "G4", "test_code"], ["Execute and heal", "", ""], ["Traceability", "", "traceability"], ["Release", "G5", "release"]];

export default function QEPage() {
  const { project, gates, refresh } = useProject();
  const [runId, setRunId] = useState<string | null>(null);
  const [install, setInstall] = useState(false);
  const [docs, setDocs] = useState<any[]>([]);
  const [error, setError] = useState("");
  const load = useCallback(() => api(`/projects/${project.id}/documents`).then(setDocs), [project.id]);
  useEffect(() => {
    load();
    api(`/projects/${project.id}/runs`).then((runs) => {
      const active = runs.find((r: any) => r.workflow === "qe" && ["running", "waiting_approval"].includes(r.status));
      if (active) setRunId(active.id);
    });
  }, [load, project.id]);
  const start = async () => {
    setError("");
    try {
      setRunId((await api(`/projects/${project.id}/runs`, { json: { workflow: "qe", input: { install_deps: install } } })).id);
    } catch (e: any) {
      setError(e.message);
    }
  };
  return (
    <>
      <PageTitle title="QE Studio" subtitle="The full test lifecycle with a human approval at each gate. Zero executed tests is INCONCLUSIVE, never PASS." />
      <Card className="mb-4">
        <ol className="flex flex-wrap gap-2">
          {STAGES.map(([name, gate, kind]) => {
            const doc = docs.find((d) => d.kind === kind);
            const record = gates.find((g) => `G${g.gate}` === gate);
            const body = <span className="block rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs dark:border-slate-800"><b>{name}</b> {gate && <Badge>{record?.status || "pending"}</Badge>}{doc && <span className="ml-1 text-indigo-500">v{doc.current_version}</span>}</span>;
            return <li key={name}>{doc ? <Link href={`/projects/${project.id}/documents/${doc.id}`}>{body}</Link> : body}</li>;
          })}
        </ol>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button onClick={start}><Play className="h-4 w-4" /> Start QE lifecycle</Button>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={install} onChange={(e) => setInstall(e.target.checked)} /> Install repository dependencies before running tests <span className="text-amber-500">(runs its install scripts)</span></label>
        </div>
        <ErrorNote message={error} />
      </Card>
      <div className="grid gap-4 lg:grid-cols-[1fr_300px] [&>*]:min-w-0">
        <div>{runId ? <RunPanel runId={runId} projectId={project.id} onFinished={() => { load(); refresh(); }} /> : <p className="text-sm text-slate-500">No QE run selected.</p>}</div>
        <Card title="Past runs"><RunList projectId={project.id} workflow={["qe"]} activeId={runId} onPick={setRunId} refreshKey={runId} /></Card>
      </div>
    </>
  );
}
