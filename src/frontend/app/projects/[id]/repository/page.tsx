"use client";

import { RefreshCw, Unplug, UploadCloud } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useProject } from "../../../../components/ProjectShell";
import { Badge, Button, Card, ErrorNote, Field, inputClass, PageTitle, Spinner, useToast } from "../../../../components/ui";
import { api, upload, when } from "../../../../lib/api";

export default function RepositoryPage() {
  return <Suspense fallback={<Spinner />}><Repository /></Suspense>;
}

function Repository() {
  const { project, refresh } = useProject();
  const params = useSearchParams();
  const [repo, setRepo] = useState<any>(undefined);
  const [error, setError] = useState(params.get("error") || "");
  const [busy, setBusy] = useState("");
  const toast = useToast();
  const load = useCallback(() => api(`/projects/${project.id}/repo`).then(setRepo), [project.id]);
  useEffect(() => {
    load();
  }, [load]);

  const act = async (label: string, work: () => Promise<any>) => {
    setBusy(label);
    setError("");
    try {
      setRepo(await work());
      refresh();
      toast("Repository scanned");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  if (repo === undefined) return <Spinner />;
  return (
    <>
      <PageTitle title="Repository" subtitle="Clone a Git repository or upload a ZIP. All analysis comes from the real files." />
      <ErrorNote message={error} />
      <Connect project={project} busy={busy} act={act} />
      {repo && <Details repo={repo} project={project} busy={busy} act={act} setRepo={setRepo} refresh={refresh} />}
    </>
  );
}

function Connect({ project, busy, act }: any) {
  const [url, setUrl] = useState("");
  const [ref, setRef] = useState("");
  const [connections, setConnections] = useState<any[]>([]);
  const [credential, setCredential] = useState("");
  const [repos, setRepos] = useState<any[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [folder, setFolder] = useState("");
  useEffect(() => {
    api("/connections").then(setConnections);
  }, []);
  useEffect(() => {
    if (credential) api(`/connections/${credential}/repos`).then(setRepos).catch(() => setRepos([]));
    else setRepos([]);
  }, [credential]);
  return (
    <div className="mt-3 grid gap-4 md:grid-cols-3">
      <Card title="From Git">
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); act("git", () => api(`/projects/${project.id}/repo/git`, { json: { url, ref, credential_id: credential || null } })); }}>
          <Field label="Private repository access" hint="A saved token is sent only to the Git host, never stored in the clone.">
            <select aria-label="Connection" className={inputClass} value={credential} onChange={(e) => setCredential(e.target.value)}>
              <option value="">None (public repository)</option>
              {connections.map((c) => <option key={c.id} value={c.id}>{c.label} ({c.login})</option>)}
            </select>
          </Field>
          {!connections.length && <p className="text-xs text-slate-500">Add a token in <Link className="text-indigo-500 underline" href="/settings">Settings</Link> to reach private repositories.</p>}
          {repos.length > 0 && (
            <Field label="Your repositories">
              <select aria-label="Your repositories" className={inputClass} onChange={(e) => setUrl(e.target.value)} defaultValue="">
                <option value="" disabled>Pick a repository</option>
                {repos.map((r) => <option key={r.clone_url} value={r.clone_url}>{r.full_name}{r.private ? " (private)" : ""}</option>)}
              </select>
            </Field>
          )}
          <Field label="HTTPS URL or owner/repo"><input required name="git-url" className={inputClass} placeholder="https://github.com/owner/repo" value={url} onChange={(e) => setUrl(e.target.value)} /></Field>
          <Field label="Branch or tag (optional)"><input className={inputClass} value={ref} onChange={(e) => setRef(e.target.value)} /></Field>
          <Button type="submit" busy={busy === "git"}>{busy === "git" ? "Cloning and scanning" : "Clone and scan"}</Button>
        </form>
      </Card>
      <Card title="From ZIP">
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); const form = new FormData(); form.append("file", file as File); act("zip", () => upload(`/projects/${project.id}/repo/zip`, form)); }}>
          <Field label="ZIP archive" hint="No repository host needed. Traversal paths, symlinks, and zip bombs are refused."><input required type="file" name="zip-file" accept=".zip" className={inputClass} onChange={(e) => setFile(e.target.files?.[0] || null)} /></Field>
          <Button type="submit" busy={busy === "zip"}><UploadCloud className="h-4 w-4" /> Upload and scan</Button>
        </form>
      </Card>
      <Card title="From a folder on this machine">
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); act("local", () => api(`/projects/${project.id}/repo/local`, { json: { path: folder } })); }}>
          <Field label="Folder path" hint="Copied into the project. The original folder is not changed."><input required name="folder-path" className={inputClass} value={folder} onChange={(e) => setFolder(e.target.value)} /></Field>
          <Button type="submit" busy={busy === "local"}>Import and scan</Button>
        </form>
      </Card>
    </div>
  );
}

function Details({ repo, project, busy, act, setRepo, refresh }: any) {
  const a = repo.analysis;
  const [tree, setTree] = useState<string[]>([]);
  const [path, setPath] = useState("");
  const [content, setContent] = useState("");
  const [filter, setFilter] = useState("");
  useEffect(() => {
    api(`/projects/${project.id}/repo/tree`).then((d) => setTree(d.files));
  }, [project.id, repo.commit_sha, repo.scanned_at]);
  const open = async (p: string) => {
    setPath(p);
    setContent(await api(`/projects/${project.id}/repo/file?path=${encodeURIComponent(p)}`));
  };
  const disconnect = async () => {
    if (!confirm("Remove the local copy of this repository from the project? The remote repository is not affected.")) return;
    await api(`/projects/${project.id}/repo`, { method: "DELETE" });
    setRepo(null);
    refresh();
  };
  const total = Object.values(a.lines_of_code as Record<string, number>).reduce((x, y) => x + y, 0) || 1;
  return (
    <div className="mt-4 space-y-4" data-testid="repo-details">
      <Card title={<span className="truncate">{repo.url}</span>} actions={
        <div className="flex gap-2">
          {repo.kind === "git" && <Button variant="secondary" busy={busy === "sync"} onClick={() => act("sync", () => api(`/projects/${project.id}/repo/resync`, { method: "POST" }))}><RefreshCw className="h-4 w-4" /> Re-sync</Button>}
          <Button variant="danger" onClick={disconnect}><Unplug className="h-4 w-4" /> Disconnect</Button>
        </div>
      }>
        <p className="text-xs text-slate-500">Commit <span className="mono">{repo.commit_sha.slice(0, 10)}</span> · scanned {when(repo.scanned_at)} · <Badge tone="indigo">{a.mode}</Badge></p>
        <dl className="mt-3 grid grid-cols-2 gap-2 text-center md:grid-cols-5">
          {[["Files", a.total_files], ["Source files", a.source_files], ["Test files", a.test_file_count], ["Routes", a.routes.length], ["CI workflows", a.ci.length]].map(([k, v]) => (
            <div key={k as string} className="rounded-lg bg-slate-100 p-2 dark:bg-slate-900"><dd className="text-lg font-bold">{v}</dd><dt className="text-xs text-slate-500">{k}</dt></div>
          ))}
        </dl>
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Languages (lines of code)">
          <ul className="space-y-1.5 text-xs">
            {Object.entries(a.lines_of_code as Record<string, number>).map(([lang, lines]) => (
              <li key={lang}><div className="flex justify-between"><span>{lang}</span><span>{lines.toLocaleString()}</span></div><div className="h-1.5 rounded bg-slate-200 dark:bg-slate-800"><div className="h-1.5 rounded bg-indigo-500" style={{ width: `${(100 * lines) / total}%` }} /></div></li>
            ))}
          </ul>
        </Card>
        <Card title="Stack">
          <p className="text-sm"><b>Frameworks:</b> {a.frameworks.join(", ") || "none detected"}</p>
          <p className="text-sm"><b>Test runners:</b> {a.test_runners.join(", ") || "none detected"}</p>
          <p className="mt-2 text-sm font-semibold">Entry points</p>
          <ul className="mono max-h-28 overflow-y-auto text-xs">{a.entrypoints.map((e: string) => <li key={e}>{e}</li>)}</ul>
        </Card>
      </div>
      {a.routes.length > 0 && (
        <Card title="HTTP routes">
          <div className="max-h-56 overflow-auto"><table className="w-full text-left text-xs"><thead><tr><th>Method</th><th>Path</th><th>Location</th></tr></thead><tbody>
            {a.routes.map((r: any, i: number) => <tr key={i} className="border-t border-slate-200 dark:border-slate-800"><td className="py-0.5 font-semibold">{r.method}</td><td className="mono">{r.path}</td><td className="mono text-slate-500">{r.file}:{r.line}</td></tr>)}
          </tbody></table></div>
        </Card>
      )}
      <Card title={`Files (${tree.length})`}>
        <div className="grid gap-3 md:grid-cols-[280px_1fr] [&>*]:min-w-0">
          <div>
            <input aria-label="Filter files" className={`${inputClass} mb-2`} placeholder="Filter files" value={filter} onChange={(e) => setFilter(e.target.value)} />
            <ul className="mono max-h-96 overflow-y-auto text-xs">
              {tree.filter((f) => f.toLowerCase().includes(filter.toLowerCase())).slice(0, 500).map((f) => <li key={f}><button onClick={() => open(f)} className={`block w-full truncate px-1 text-left hover:bg-slate-100 dark:hover:bg-slate-900 ${path === f ? "text-indigo-500" : ""}`} title={f}>{f}</button></li>)}
            </ul>
          </div>
          <pre className="mono max-h-[28rem] min-h-40 overflow-auto rounded-lg bg-slate-100 p-3 text-xs dark:bg-[#070d1f]">{path ? content : "Select a file to read it."}</pre>
        </div>
      </Card>
      {repo.log.length > 0 && (
        <Card title="Recent commits"><ul className="space-y-0.5 text-xs">{repo.log.map((c: any) => <li key={c.sha}><span className="mono text-slate-500">{c.sha}</span> {c.subject} <span className="text-slate-500">({c.author}, {c.date})</span></li>)}</ul></Card>
      )}
    </div>
  );
}
