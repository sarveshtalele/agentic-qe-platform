"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useProject } from "../../../../components/ProjectShell";
import { Badge, Button, Card, Empty, ErrorNote, inputClass, PageTitle, Spinner } from "../../../../components/ui";
import { api, when } from "../../../../lib/api";

export default function DocumentsPage() {
  const { project } = useProject();
  const router = useRouter();
  const [docs, setDocs] = useState<any[] | null>(null);
  const [kind, setKind] = useState("");
  const [query, setQuery] = useState("");
  const [title, setTitle] = useState("");
  const [template, setTemplate] = useState("builtin_brd");
  const [templates, setTemplates] = useState<any[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    api(`/projects/${project.id}/documents`).then(setDocs);
    api(`/templates?project_id=${project.id}`).then(setTemplates);
  }, [project.id]);
  const create = async () => {
    try {
      const t = templates.find((x) => x.id === template);
      const doc = await api(`/projects/${project.id}/documents`, { json: { title, kind: t?.kind || "brd", template_id: template } });
      router.push(`/projects/${project.id}/documents/${doc.id}`);
    } catch (e: any) {
      setError(e.message);
    }
  };
  if (!docs) return <Spinner />;
  const kinds = [...new Set(docs.map((d) => d.kind))];
  const shown = docs.filter((d) => (!kind || d.kind === kind) && d.title.toLowerCase().includes(query.toLowerCase()));
  return (
    <>
      <PageTitle title="Documents" subtitle="Every save is a new version with its author, hash, and prompt reference." />
      <Card title="Write by hand from a template" className="mb-4">
        <div className="flex flex-wrap gap-2">
          <input aria-label="New document title" placeholder="Document title" className={`${inputClass} max-w-xs`} value={title} onChange={(e) => setTitle(e.target.value)} />
          <select aria-label="Template for new document" className={`${inputClass} max-w-xs`} value={template} onChange={(e) => setTemplate(e.target.value)}>{templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
          <Button onClick={create} disabled={!title.trim()}><Plus className="h-4 w-4" /> Create</Button>
        </div>
        <ErrorNote message={error} />
      </Card>
      {docs.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
          <input aria-label="Search documents" className={`${inputClass} max-w-xs`} placeholder="Search titles" value={query} onChange={(e) => setQuery(e.target.value)} />
          <select aria-label="Filter by kind" className={`${inputClass} max-w-[180px]`} value={kind} onChange={(e) => setKind(e.target.value)}><option value="">All kinds</option>{kinds.map((k) => <option key={k}>{k}</option>)}</select>
        </div>
      )}
      {shown.length ? (
        <Card>
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-slate-500"><tr><th className="pb-2">Title</th><th>Kind</th><th>Version</th><th>Status</th><th>Updated</th></tr></thead>
            <tbody>{shown.map((d) => <tr key={d.id} className="border-t border-slate-200 dark:border-slate-800"><td className="py-1.5"><Link className="font-semibold hover:underline" href={`/projects/${project.id}/documents/${d.id}`}>{d.title}</Link></td><td className="text-xs">{d.kind}</td><td className="text-xs">v{d.current_version}</td><td><Badge>{d.status}</Badge></td><td className="text-xs text-slate-500">{when(d.updated_at)}</td></tr>)}</tbody>
          </table>
        </Card>
      ) : <Empty title="No documents">Generate one in BA Studio, or create one above.</Empty>}
    </>
  );
}
