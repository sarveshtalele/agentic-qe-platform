"use client";

import { ArrowLeft, Check, Download, RotateCcw, Save, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useProject } from "../../../../../components/ProjectShell";
import { useAuth } from "../../../../../components/AuthGate";
import { DocumentEditor } from "../../../../../components/DocumentEditor";
import { Badge, Button, Card, ErrorNote, inputClass, Spinner, useToast } from "../../../../../components/ui";
import { api, when } from "../../../../../lib/api";

export default function DocumentPage() {
  const { project } = useProject();
  const { docId } = useParams<{ docId: string }>();
  const router = useRouter();
  const toast = useToast();
  const { user } = useAuth();
  const [doc, setDoc] = useState<any>(null);
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState("");
  const [tab, setTab] = useState<"document" | "source" | "history">("document");
  const [versions, setVersions] = useState<any[]>([]);
  const [viewing, setViewing] = useState<any>(null);
  const [diff, setDiff] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [working, setWorking] = useState("");
  const [reviewResult, setReviewResult] = useState<any>(null);
  const [refineText, setRefineText] = useState("");

  const load = useCallback(async () => {
    const [d, v] = await Promise.all([api(`/documents/${docId}`), api(`/documents/${docId}/versions`)]);
    setDoc(d);
    setDraft(d.content);
    setVersions(v);
  }, [docId]);
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load]);
  const dirty = doc && draft !== doc.content;
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty) e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  if (!doc) return error ? <ErrorNote message={error} /> : <Spinner />;
  const save = async () => {
    setBusy(true);
    setError("");
    try {
      await api(`/documents/${docId}`, { method: "PUT", json: { content: draft, note: note || "Edited" } });
      setNote("");
      await load();
      toast("Saved as a new version");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const approve = async () => {
    await api(`/documents/${docId}/approve`, { method: "POST" });
    await load();
    toast("Document approved");
  };
  const restore = async (version: number) => {
    await api(`/documents/${docId}/restore/${version}`, { method: "POST" });
    setViewing(null);
    setDiff("");
    await load();
    setTab("document");
    toast(`Restored v${version} as a new version`);
  };
  const remove = async () => {
    if (!confirm(`Delete "${doc.title}" and all ${doc.current_version} versions? The ledger keeps a record of the deletion.`)) return;
    await api(`/documents/${docId}`, { method: "DELETE" });
    router.push(`/projects/${project.id}/documents`);
  };
  const isGherkin = doc.kind === "gherkin";
  const formats = isGherkin ? ["feature", "md", "docx"] : doc.kind === "patch" ? ["patch"] : doc.kind === "test_cases" ? ["md", "docx", "csv", "jira"] : ["md", "docx"];
  const agentEditable = ["brd", "prd", "stories", "gherkin"].includes(doc.kind);
  const review = async () => {
    setWorking("review");
    setError("");
    try {
      setReviewResult(await api(`/documents/${docId}/review`, { method: "POST" }));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setWorking("");
    }
  };
  const refine = async () => {
    setWorking("refine");
    setError("");
    try {
      await api(`/documents/${docId}/refine`, { json: { instructions: refineText } });
      setRefineText("");
      await load();
      toast("Agent saved a new version");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setWorking("");
    }
  };
  return (
    <>
      <Link href={`/projects/${project.id}/documents`} className="mb-2 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-indigo-500"><ArrowLeft className="h-3 w-3" /> Documents</Link>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold">{doc.title}</h1>
          <p className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <Badge tone="indigo">{doc.kind}</Badge> <span data-testid="doc-version">v{doc.version}</span> <Badge>{doc.status}</Badge> by {doc.author_name}
            {doc.prompt_ref && <span className="mono">{doc.prompt_ref}</span>}
            <span className="mono" title={doc.sha256}>sha256 {doc.sha256.slice(0, 12)}</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {formats.map((f) => <a key={f} href={`/api/documents/${docId}/export/${f}`} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"><Download className="h-4 w-4" /> .{f}</a>)}
          {doc.status !== "approved" && <Button variant="success" onClick={approve}><Check className="h-4 w-4" /> Approve</Button>}
          <Button variant="danger" aria-label="Delete document" onClick={remove}><Trash2 className="h-4 w-4" /></Button>
        </div>
      </div>
      {isGherkin && doc.gherkin && <p className="mb-2 text-xs" data-testid="gherkin-status">{doc.gherkin.valid ? <Badge tone="emerald">{`Valid Gherkin: ${doc.gherkin.scenarios} scenarios, ${doc.gherkin.steps} steps`}</Badge> : <Badge tone="rose">Invalid Gherkin</Badge>}</p>}
      <div role="tablist" className="mb-3 flex gap-1 border-b border-slate-200 dark:border-slate-800">
        {(["document", "source", "history"] as const).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`border-b-2 px-3 py-1.5 text-sm font-semibold capitalize ${tab === t ? "border-indigo-500 text-indigo-500" : "border-transparent text-slate-500"}`}>{t}{t === "history" ? ` (${versions.length})` : ""}</button>
        ))}
      </div>
      <ErrorNote message={error} />
      {agentEditable && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Button variant="secondary" busy={working === "review"} onClick={review}>Ask reviewer</Button>
          <input aria-label="Refine instructions" className={`${inputClass} max-w-md`} placeholder="Tell the agent what to change" value={refineText} onChange={(e) => setRefineText(e.target.value)} />
          <Button variant="secondary" busy={working === "refine"} disabled={!refineText.trim() || !!dirty} title={dirty ? "Save your edits first" : undefined} onClick={refine}>Refine with agent</Button>
        </div>
      )}
      {reviewResult && <div className="mb-3"><Card title={<span>Review of v{reviewResult.version}: score {reviewResult.score} <Badge>{reviewResult.verdict}</Badge></span>}><ul className="list-disc space-y-0.5 pl-5 text-sm">{reviewResult.issues.map((i: string, n: number) => <li key={n}>{i}</li>)}</ul></Card></div>}
      {tab === "document" && (
        <Card>
          {doc.kind === "patch"
            ? <pre className="mono overflow-auto text-xs">{draft}</pre>
            : <DocumentEditor documentId={docId} value={draft} gherkin={isGherkin} onChange={setDraft} onError={setError} />}
        </Card>
      )}
      {tab === "source" && (
        <div className="grid gap-4 lg:grid-cols-2 [&>*]:min-w-0">
          <textarea aria-label="Document content" name="doc-content" spellCheck={false} className={`${inputClass} mono min-h-[65vh] text-[13px] leading-relaxed`} value={draft} onChange={(e) => setDraft(e.target.value)} />
          <div className="max-h-[75vh] overflow-auto" data-testid="source-preview"><Card>{doc.kind === "patch" ? <pre className="mono overflow-auto text-xs">{draft}</pre> : <DocumentEditor documentId={docId} value={draft} gherkin={isGherkin} readOnly />}</Card></div>
        </div>
      )}
      {tab !== "history" && (
        <div className="sticky bottom-0 z-10 mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white/95 p-2 backdrop-blur dark:border-slate-800 dark:bg-[#0b1329]/95" data-testid="save-bar">
          <span className="text-xs text-slate-500" data-testid="signing-as">Signing as {user.username}</span>
          <input aria-label="Change note" className={`${inputClass} max-w-md`} placeholder="What changed" value={note} onChange={(e) => setNote(e.target.value)} />
          <Button onClick={save} busy={busy} disabled={!dirty}><Save className="h-4 w-4" /> Save version</Button>
          {dirty ? <><Button variant="secondary" onClick={() => setDraft(doc.content)}>Discard changes</Button><span className="text-xs text-amber-500">Unsaved changes</span></> : <span className="text-xs text-slate-500">Select any text or table cell to edit it</span>}
        </div>
      )}
      {tab === "history" && (
        <div className="grid gap-4 md:grid-cols-[360px_1fr] [&>*]:min-w-0">
          <Card>
            <ul className="divide-y divide-slate-200 text-sm dark:divide-slate-800">
              {versions.map((v, i) => (
                <li key={v.version} className="py-2">
                  <div className="flex items-center justify-between"><b>v{v.version}</b><span className="text-xs text-slate-500">{when(v.created_at)}</span></div>
                  <p className="truncate text-xs text-slate-500" title={v.note}>{v.author_name} · {v.note}</p>
                  <div className="mt-1 flex gap-3 text-xs">
                    <button className="text-indigo-500" onClick={async () => { setViewing(await api(`/documents/${docId}?version=${v.version}`)); setDiff(""); }}>View</button>
                    {i < versions.length - 1 && <button className="text-indigo-500" onClick={async () => { setDiff(await api(`/documents/${docId}/diff?a=${versions[i + 1].version}&b=${v.version}`)); setViewing(null); }}>Diff with v{versions[i + 1].version}</button>}
                    {i > 0 && <button className="inline-flex items-center gap-0.5 text-indigo-500" onClick={() => restore(v.version)}><RotateCcw className="h-3 w-3" /> Restore</button>}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
          <Card>
            {diff ? <pre className="mono overflow-auto text-xs">{diff.split("\n").map((l, i) => <div key={i} className={l.startsWith("+") ? "text-emerald-500" : l.startsWith("-") ? "text-rose-500" : ""}>{l || " "}</div>)}</pre>
              : viewing ? <pre className="mono overflow-auto whitespace-pre-wrap text-xs">{viewing.content}</pre>
              : <p className="text-sm text-slate-500">Pick a version to view it or compare it.</p>}
          </Card>
        </div>
      )}
    </>
  );
}
