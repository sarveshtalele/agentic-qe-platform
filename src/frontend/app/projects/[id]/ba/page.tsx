"use client";

import { Play, Upload } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useProject } from "../../../../components/ProjectShell";
import { RunList, RunPanel } from "../../../../components/RunPanel";
import { Badge, Button, Card, ErrorNote, Field, inputClass, PageTitle, useToast } from "../../../../components/ui";
import { api, upload } from "../../../../lib/api";

export default function BAPage() {
  const { project, refresh } = useProject();
  const [templates, setTemplates] = useState<any[]>([]);
  const [templateId, setTemplateId] = useState("builtin_brd");
  const [sources, setSources] = useState<any[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [brief, setBrief] = useState("");
  const [title, setTitle] = useState("");
  const [runId, setRunId] = useState<string | null>(null);
  const [docs, setDocs] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();

  const loadTemplates = useCallback(() => api(`/templates?project_id=${project.id}`).then(setTemplates), [project.id]);
  const loadSources = useCallback(() => api(`/projects/${project.id}/sources`).then(setSources), [project.id]);
  const loadDocs = useCallback(() => api(`/projects/${project.id}/documents`).then((items) => setDocs(items.filter((d: any) => ["brd", "prd", "stories", "gherkin"].includes(d.kind)))), [project.id]);
  useEffect(() => {
    loadTemplates();
    loadSources();
    loadDocs();
  }, [loadTemplates, loadSources, loadDocs]);

  // documents appear while a run works, before its first approval
  useEffect(() => {
    if (!runId) return;
    loadDocs();
    const timer = setInterval(loadDocs, 3000);
    return () => clearInterval(timer);
  }, [runId, loadDocs]);

  const current = docs.filter((d) => runId && d.run_id === runId);
  const recent = docs.filter((d) => d.run_id !== runId || !runId).slice(0, 8);
  const docLink = (d: any) => (
    <li key={d.id} className="flex items-center justify-between gap-2"><Link className="truncate text-indigo-600 hover:underline dark:text-indigo-300" href={`/projects/${project.id}/documents/${d.id}`}>{d.title}</Link><span className="flex shrink-0 items-center gap-1 text-xs"><Badge>{d.kind}</Badge>v{d.current_version}<Badge>{d.status}</Badge></span></li>
  );
  const template = templates.find((t) => t.id === templateId);
  const start = async () => {
    setBusy(true);
    setError("");
    try {
      const run = await api(`/projects/${project.id}/runs`, { json: { workflow: "ba", input: { brief, title: title || template?.name, template_id: templateId, source_ids: selected } } });
      setRunId(run.id);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const addSource = async (file?: File) => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    try {
      const source = await upload(`/projects/${project.id}/sources`, form);
      setSelected((s) => [...new Set([...s, source.id])]);
      loadSources();
      toast(source.duplicate ? "Already uploaded. Selected it." : `Extracted ${source.chars} characters`);
    } catch (e: any) {
      setError(e.message);
    }
  };
  const addTemplate = async (file?: File) => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("name", file.name.replace(/\.\w+$/, ""));
    form.append("project_id", project.id);
    try {
      const created = await upload("/templates/upload", form);
      await loadTemplates();
      setTemplateId(created.id);
      toast(`Template added with ${created.headings.length} sections`);
    } catch (e: any) {
      setError(e.message);
    }
  };
  return (
    <>
      <PageTitle title="BA Studio" subtitle="Turn a brief and source documents into a templated requirements document and validated Gherkin." />
      <div className="grid gap-4 lg:grid-cols-[1fr_320px] [&>*]:min-w-0">
        <div className="space-y-4">
          <Card title="New document">
            <div className="space-y-3">
              <Field label="Brief"><textarea name="brief" rows={6} className={inputClass} placeholder="What should be built, for whom, and why. Agents use only what you give them; unknowns become Open Questions." value={brief} onChange={(e) => setBrief(e.target.value)} /></Field>
              <div className="grid gap-3 md:grid-cols-2">
                <Field label="Document title"><input name="doc-title" className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} placeholder={template?.name} /></Field>
                <Field label="Template"><select aria-label="Template" className={inputClass} value={templateId} onChange={(e) => setTemplateId(e.target.value)}>{templates.map((t) => <option key={t.id} value={t.id}>{t.name}{t.builtin ? "" : " (yours)"}</option>)}</select></Field>
              </div>
              {template && <p className="text-xs text-slate-500">Sections: {template.headings.join(" · ")}</p>}
              <label className="flex w-fit cursor-pointer items-center gap-1.5 text-xs font-semibold text-indigo-500"><Upload className="h-3.5 w-3.5" /> Upload your own template (.md, .docx)<input type="file" name="template-file" accept=".md,.txt,.docx" className="hidden" onChange={(e) => addTemplate(e.target.files?.[0])} /></label>
              <ErrorNote message={error} />
              <Button onClick={start} busy={busy} disabled={!brief.trim() && !selected.length}><Play className="h-4 w-4" /> Generate document</Button>
            </div>
          </Card>
          {current.length > 0 && <Card title="Created in this run"><ul className="space-y-1.5 text-sm" data-testid="current-documents">{current.map(docLink)}</ul></Card>}
          {runId && <RunPanel runId={runId} projectId={project.id} onFinished={() => { loadDocs(); refresh(); }} />}
        </div>
        <div className="space-y-4">
          <Card title="Source documents">
            <label className="mb-2 inline-flex cursor-pointer items-center gap-1.5 text-xs font-semibold text-indigo-500"><Upload className="h-3.5 w-3.5" /> Upload (.md, .txt, .pdf, .docx, .xlsx, .pptx)<input type="file" name="source-file" accept=".md,.txt,.pdf,.docx,.xlsx,.pptx,.csv,.json,.yaml,.yml" className="hidden" onChange={(e) => addSource(e.target.files?.[0])} /></label>
            {sources.length ? (
              <ul className="space-y-1 text-sm">{sources.map((s) => (
                <li key={s.id}><label className="flex items-center gap-2"><input type="checkbox" checked={selected.includes(s.id)} onChange={(e) => setSelected(e.target.checked ? [...selected, s.id] : selected.filter((x) => x !== s.id))} /><span className="truncate" title={s.filename}>{s.filename}</span></label></li>
              ))}</ul>
            ) : <p className="text-xs text-slate-500">None uploaded.</p>}
          </Card>
          <Card title="Recent documents" actions={<Link className="text-xs text-indigo-500" href={`/projects/${project.id}/documents`}>All documents</Link>}>
            {recent.length ? <ul className="space-y-1.5 text-sm" data-testid="recent-documents">{recent.map(docLink)}</ul> : <p className="text-xs text-slate-500">None yet.</p>}
          </Card>
          <Card title="Past runs"><RunList projectId={project.id} workflow={["ba"]} activeId={runId} onPick={setRunId} refreshKey={runId} /></Card>
        </div>
      </div>
    </>
  );
}
