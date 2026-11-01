"use client";

import { ShieldAlert, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useProject } from "../../../../components/ProjectShell";
import { useAuth } from "../../../../components/AuthGate";
import { Badge, Button, Card, ErrorNote, Field, inputClass, PageTitle, Spinner } from "../../../../components/ui";
import { api, when } from "../../../../lib/api";

export default function GovernancePage() {
  const { project, gates, refresh } = useProject();
  const [gate, setGate] = useState(0);
  const { user } = useAuth();
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [ledger, setLedger] = useState<any>(null);
  const [pending, setPending] = useState<any[]>([]);
  const load = useCallback(() => {
    api(`/projects/${project.id}/ledger`).then(setLedger);
    api(`/projects/${project.id}/approvals`).then(setPending);
  }, [project.id]);
  useEffect(() => {
    load();
  }, [load]);
  const canSign = (project.can_sign || []).includes(gate); // the server is the real check
  const decide = async (approved: boolean) => {
    setError("");
    try {
      await api(`/projects/${project.id}/gates/${gate}/decision`, { json: { approved, reason } });
      setReason("");
      refresh();
      load();
    } catch (e: any) {
      setError(e.message);
    }
  };
  if (!ledger) return <Spinner />;
  const check = ledger.verification;
  return (
    <>
      <PageTitle title="Governance" subtitle="Signed gate decisions and a hash-chained audit ledger." />
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Quality gates">
          <table className="w-full text-left text-sm">
            <tbody>{gates.map((g) => (
              <tr key={g.gate} className="border-t border-slate-200 first:border-0 dark:border-slate-800">
                <td className="py-1.5"><b>G{g.gate} {g.name}</b><br /><span className="text-xs text-slate-500">{g.description}</span></td>
                <td className="text-xs">{g.decided_by_name}{g.decided_at && <><br />{when(g.decided_at)}</>}{g.reason && <><br />{g.reason}</>}</td>
                <td><Badge>{g.status}</Badge>{g.signature_valid === false && <Badge tone="rose">bad signature</Badge>}</td>
              </tr>
            ))}</tbody>
          </table>
        </Card>
        <Card title={`Awaiting approval (${pending.length})`}>
          {pending.length ? <ul className="space-y-2 text-sm">{pending.map((a) => <li key={a.id}><Link className="font-semibold text-indigo-500 underline" href={`/projects/${project.id}/runs/${a.run_id}`}>{a.title}</Link><p className="text-xs text-slate-500">{a.summary}</p></li>)}</ul> : <p className="text-sm text-slate-500">Nothing is waiting.</p>}
        </Card>
      </div>
      <Card className="mt-4" title="Record a gate decision">
        <p className="mb-2 text-xs text-slate-500">For decisions made outside a run, such as revoking an approval. Rejecting a gate clears later approvals.</p>
        <div className="grid gap-2 md:grid-cols-[160px_1fr_1fr_auto]">
          <Field label="Gate"><select className={inputClass} value={gate} onChange={(e) => setGate(Number(e.target.value))}>{gates.map((g) => <option key={g.gate} value={g.gate}>G{g.gate} {g.name}</option>)}</select></Field>
          <Field label="Signing as"><p className="py-2 text-sm font-semibold" data-testid="signing-as">{user.username}</p></Field>
          <Field label="Reason"><input className={inputClass} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
          <div className="flex items-end gap-2"><Button variant="success" disabled={!canSign} onClick={() => decide(true)}>Approve</Button><Button variant="danger" disabled={!reason.trim() || !canSign} onClick={() => decide(false)}>Reject</Button></div>
        </div>
        {!canSign && <p className="mt-2 text-xs text-slate-500" data-testid="cannot-sign">Your role cannot sign gate G{gate}. Ask the project owner or an administrator.</p>}
        <ErrorNote message={error} />
      </Card>
      <Card className="mt-4" title={<span className="flex items-center gap-2">Audit ledger {check.valid ? <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400" data-testid="ledger-valid"><ShieldCheck className="h-4 w-4" /> Chain valid, {check.entries} entries</span> : <span className="flex items-center gap-1 text-rose-500"><ShieldAlert className="h-4 w-4" /> Tampering detected at entry {check.broken_at}</span>}</span>}>
        <div className="max-h-[32rem] overflow-auto">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-white text-slate-500 dark:bg-[#0b1329]"><tr><th className="py-1">#</th><th>Time</th><th>Actor</th><th>Action</th><th>Target</th><th>Hash</th></tr></thead>
            <tbody>{ledger.entries.map((e: any) => <tr key={e.seq} className="border-t border-slate-200 dark:border-slate-800"><td className="py-1">{e.seq}</td><td className="whitespace-nowrap">{when(e.ts)}</td><td>{e.actor_name}</td><td>{e.action}</td><td className="mono max-w-52 truncate" title={e.target}>{e.target}</td><td className="mono text-slate-500" title={e.hash}>{e.hash.slice(0, 10)}</td></tr>)}</tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
