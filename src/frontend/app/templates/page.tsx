"use client";

import { Trash2, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Card, ErrorNote, Markdown, PageTitle, useToast } from "../../components/ui";
import { AppShell } from "../../components/AppShell";
import { api, upload } from "../../lib/api";

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<any[]>([]);
  const [open, setOpen] = useState<any>(null);
  const [error, setError] = useState("");
  const toast = useToast();
  const load = useCallback(() => api("/templates").then(setTemplates), []);
  useEffect(() => {
    load();
  }, [load]);
  const add = async (file?: File) => {
    if (!file) return;
    setError("");
    const form = new FormData();
    form.append("file", file);
    form.append("name", file.name.replace(/\.\w+$/, ""));
    try {
      const created = await upload("/templates/upload", form);
      setOpen(created);
      load();
      toast(`Added with ${created.headings.length} sections`);
    } catch (e: any) {
      setError(e.message);
    }
  };
  return (
    <AppShell>
      <PageTitle title="Templates" subtitle="Generated documents keep every heading of the chosen template. Upload your organization's format as Markdown or Word." actions={
        <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500"><Upload className="h-4 w-4" /> Upload template<input type="file" name="template-file" accept=".md,.txt,.docx" className="hidden" onChange={(e) => add(e.target.files?.[0])} /></label>
      } />
      <ErrorNote message={error} />
      <div className="grid gap-4 md:grid-cols-[280px_1fr]">
        <Card>
          <ul className="space-y-1 text-sm">{templates.map((t) => (
            <li key={t.id} className="flex items-center justify-between gap-1">
              <button className="min-w-0 flex-1 truncate text-left hover:underline" onClick={() => setOpen(t)}>{t.name}</button>
              {t.builtin ? <Badge>built-in</Badge> : <button aria-label={`Delete ${t.name}`} onClick={() => api(`/templates/${t.id}`, { method: "DELETE" }).then(load)} className="text-slate-400 hover:text-rose-500"><Trash2 className="h-4 w-4" /></button>}
            </li>
          ))}</ul>
        </Card>
        <Card>{open ? <Markdown>{open.body}</Markdown> : <p className="text-sm text-slate-500">Select a template to preview it.</p>}</Card>
      </div>
    </AppShell>
  );
}
