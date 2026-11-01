"use client";

import { Archive, CheckSquare, FolderGit2, FolderKanban, Bug, Pencil, Plus, Search, Trash2, Undo2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "../components/AppShell";
import { Badge, Button, Empty, ErrorNote, Field, inputClass, Spinner, useToast } from "../components/ui";
import { api, upload, when } from "../lib/api";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<any[] | null>(null);
  const [archived, setArchived] = useState(false);
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();

  const load = useCallback(() => {
    api(`/projects?archived=${archived}`).then(setProjects).catch((e) => setError(`Cannot reach the backend: ${e.message}`));
  }, [archived]);
  useEffect(load, [load]);

  const shown = (projects || []).filter((p) => `${p.name} ${p.description}`.toLowerCase().includes(query.toLowerCase()));
  const setArchivedFlag = async (p: any, value: boolean) => {
    await api(`/projects/${p.id}`, { method: "PATCH", json: { archived: value } });
    load();
  };
  const rename = async (p: any) => {
    const name = prompt("Project name", p.name)?.trim();
    if (!name || name === p.name) return;
    await api(`/projects/${p.id}`, { method: "PATCH", json: { name } });
    toast("Project renamed");
    load();
  };
  const remove = async (p: any) => {
    if (prompt(`This permanently deletes "${p.name}", its repository copy, documents, and audit ledger.\nType the project name to confirm.`) !== p.name) return;
    await api(`/projects/${p.id}`, { method: "DELETE" });
    toast("Project deleted");
    load();
  };
  const all = projects || [];
  const needing = all.filter((p) => p.pending > 0).length;
  const stats: [string, number, any, string, string][] = [
    ["Projects", all.length, FolderKanban, "/", "projects"],
    ["Need my approval", needing, CheckSquare, "/approvals", "need-approval"],
    ["Open findings", all.reduce((n, p) => n + p.findings, 0), Bug, "/findings", "findings"],
    ["Documents", all.reduce((n, p) => n + p.documents, 0), FolderGit2, "/documents", "documents"],
  ];

  return (
    <AppShell>
      {!archived && projects !== null && all.length > 0 && (
        <dl className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          {stats.map(([label, value, Icon, href, id]) => (
            <Link key={label} href={href} data-testid={`stat-${id}`} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 hover:border-indigo-500/60 dark:border-slate-800 dark:bg-[#0b1329]">
              <Icon className={`h-5 w-5 ${id === "need-approval" && value > 0 ? "text-amber-500" : "text-indigo-500"}`} />
              <span><dd className="text-xl font-bold leading-tight">{value}</dd><dt className="text-xs text-slate-500">{label}</dt></span>
            </Link>
          ))}
        </dl>
      )}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold">{archived ? "Archived projects" : "Projects"}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
            <input aria-label="Search projects" className={`${inputClass} w-56 pl-8`} placeholder="Search projects" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          <Button variant="secondary" onClick={() => setArchived(!archived)}>{archived ? "Show active" : "Show archived"}</Button>
          <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> New project</Button>
        </div>
      </div>

      <ErrorNote message={error} />
      {projects === null && !error && <Spinner />}
      {projects !== null && !shown.length && <Empty title={query ? "No project matches" : archived ? "No archived projects" : "No projects yet"}>{!query && !archived && "Create a project, then connect a repository or start writing requirements."}</Empty>}

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {shown.map((p) => (
          <article key={p.id} className="group flex flex-col rounded-xl border border-slate-200 bg-white p-4 transition hover:border-indigo-500/60 dark:border-slate-800 dark:bg-[#0b1329]" data-testid="project-card">
            <Link href={`/projects/${p.id}`} className="flex-1">
              <h2 className="truncate font-bold">{p.name}</h2>
              <p className="mt-0.5 line-clamp-2 min-h-8 text-xs text-slate-600 dark:text-slate-400">{p.description || "No description"}</p>
              <p className="mt-3 flex items-center gap-1.5 truncate text-xs text-slate-600 dark:text-slate-400">
                <FolderGit2 className="h-3.5 w-3.5 shrink-0" /> {p.repo ? p.repo.url : "No repository"}
              </p>
              {p.repo?.languages?.length > 0 && <div className="mt-1.5 flex flex-wrap gap-1">{p.repo.languages.map((l: string) => <Badge key={l} tone="indigo">{l}</Badge>)}</div>}
            </Link>
            <dl className="mt-3 grid grid-cols-4 gap-1 text-center text-xs">
              {[["Gates", `${p.gates_approved}/6`, "governance"], ["Docs", p.documents, "documents"], ["Runs", p.runs, "runs"], ["Bugs", p.findings, "bugs"]].map(([label, value, tab]) => (
                <Link key={label as string} href={`/projects/${p.id}/${tab}`} data-testid={`card-${tab}`} className="rounded-lg bg-slate-100 py-1 hover:ring-1 hover:ring-indigo-500 dark:bg-slate-900"><dd className="font-bold">{value}</dd><dt className="text-[10px] text-slate-500">{label}</dt></Link>
              ))}
            </dl>
            <footer className="mt-3 flex items-center justify-between text-[11px] text-slate-500">
              <span>{p.pending > 0 ? <Link href="/approvals"><Badge tone="amber">{`${p.pending} awaiting approval`}</Badge></Link> : `Updated ${when(p.updated_at)}`}</span>
              <span className="flex gap-1.5">
                <button aria-label={`Rename ${p.name}`} title="Rename" onClick={() => rename(p)} className="hover:text-indigo-500"><Pencil className="h-4 w-4" /></button>
                <button aria-label={archived ? `Restore ${p.name}` : `Archive ${p.name}`} title={archived ? "Restore" : "Archive"} onClick={() => setArchivedFlag(p, !archived)} className="hover:text-indigo-500">{archived ? <Undo2 className="h-4 w-4" /> : <Archive className="h-4 w-4" />}</button>
                <button aria-label={`Delete ${p.name}`} title="Delete" onClick={() => remove(p)} className="hover:text-rose-500"><Trash2 className="h-4 w-4" /></button>
              </span>
            </footer>
          </article>
        ))}
      </div>
      {creating && <NewProject onClose={() => setCreating(false)} />}
    </AppShell>
  );
}

function NewProject({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const project = await api("/projects", { json: { name, description } });
      try {
        if (url.trim()) await api(`/projects/${project.id}/repo/git`, { json: { url: url.trim() } });
        else if (file) {
          const form = new FormData();
          form.append("file", file);
          await upload(`/projects/${project.id}/repo/zip`, form);
        }
      } catch (err: any) {
        router.push(`/projects/${project.id}/repository?error=${encodeURIComponent(err.message)}`);
        return;
      }
      router.push(`/projects/${project.id}`);
    } catch (err: any) {
      setError(err.message);
      setBusy(false);
    }
  };
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true" aria-label="New project">
      <form onSubmit={submit} className="w-full max-w-lg space-y-3 rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-[#0b1329]">
        <h2 className="text-lg font-bold">New project</h2>
        <Field label="Name"><input required autoFocus maxLength={120} className={inputClass} value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="Description"><textarea className={inputClass} rows={2} value={description} onChange={(e) => setDescription(e.target.value)} /></Field>
        <Field label="Git URL (optional)" hint="Public HTTPS URL or owner/repo. For private repositories, add a connection in Settings, then use the Repository page."><input className={inputClass} placeholder="https://github.com/owner/repo" value={url} onChange={(e) => setUrl(e.target.value)} disabled={!!file} /></Field>
        <Field label="Or upload a ZIP (optional)"><input type="file" accept=".zip" className={inputClass} onChange={(e) => setFile(e.target.files?.[0] || null)} disabled={!!url} /></Field>
        <ErrorNote message={error} />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" busy={busy}>{busy && (url || file) ? "Cloning and scanning" : "Create project"}</Button>
        </div>
      </form>
    </div>
  );
}
