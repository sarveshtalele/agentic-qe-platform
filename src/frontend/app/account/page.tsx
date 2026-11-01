"use client";

import { useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { Badge, Button, Card, ErrorNote, Field, inputClass, PageTitle, Spinner, useToast } from "../../components/ui";
import { api } from "../../lib/api";

const PERIODS = [["day", "Today"], ["week", "This week"], ["month", "This month"]] as const;
const ROLE: Record<string, string> = { admin: "Administrator", qe_lead: "QE lead", ba: "BA", developer: "Developer", viewer: "Viewer (read only)" };

function Bar({ label, used, limit }: { label: string; used: number; limit: number | null }) {
  const share = limit ? Math.min(100, Math.round((100 * used) / limit)) : 0;
  return (
    <div className="text-xs">
      <p className="mb-0.5 text-slate-500">{label}: {used.toLocaleString()} of {limit === null ? "unlimited" : limit.toLocaleString()} tokens</p>
      {limit !== null && <div className="h-1.5 rounded bg-slate-200 dark:bg-slate-800"><div className={`h-1.5 rounded ${share >= 100 ? "bg-rose-500" : share >= 80 ? "bg-amber-500" : "bg-indigo-500"}`} style={{ width: `${share}%` }} /></div>}
    </div>
  );
}

/** Your own role, models, limits, and usage, and a way to change your password. */
export default function AccountPage() {
  const [me, setMe] = useState<any>(null);
  const [form, setForm] = useState({ current: "", next: "", again: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  useEffect(() => { api("/auth/me").then(setMe).catch((e) => setError(e.message)); }, []);
  if (!me) return <AppShell><PageTitle title="Account" /><ErrorNote message={error} />{!error && <Spinner />}</AppShell>;
  const admin = me.role === "admin";
  const change = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    if (form.next !== form.again) return setError("The new password and its repeat are not the same");
    setBusy(true);
    try {
      await api("/account/password", { json: { current_password: form.current, new_password: form.next } });
      setForm({ current: "", next: "", again: "" });
      toast("Password changed. Other sessions were signed out");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <AppShell>
      <PageTitle title="Account" subtitle={`${me.username} · ${ROLE[me.account_role] || me.account_role}`} />
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Password">
          {admin ? <p className="text-sm text-slate-600 dark:text-slate-400" data-testid="admin-password-note">The administrator password lives in the environment (ATLAS_ADMIN_PASSWORD). Change it there and restart the server.</p> : (
            <form onSubmit={change} className="space-y-2">
              <Field label="Current password"><input required type="password" name="current-password" autoComplete="current-password" className={inputClass} value={form.current} onChange={(e) => setForm({ ...form, current: e.target.value })} /></Field>
              <Field label="New password" hint="At least 10 characters."><input required type="password" name="new-password" autoComplete="new-password" className={inputClass} value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })} /></Field>
              <Field label="New password again"><input required type="password" name="repeat-password" autoComplete="new-password" className={inputClass} value={form.again} onChange={(e) => setForm({ ...form, again: e.target.value })} /></Field>
              <ErrorNote message={error} />
              <Button type="submit" busy={busy}>Change password</Button>
              <p className="text-xs text-slate-500">Your other sessions are signed out. This one stays.</p>
            </form>
          )}
        </Card>
        {!admin && (
          <Card title="Models, limits, and usage">
            <div className="space-y-3" data-testid="account-usage">
              <div className="flex flex-wrap items-center gap-1.5 text-sm">{me.models.length ? me.models.map((m: string) => <Badge key={m} tone={m === me.model ? "indigo" : undefined}>{m}{m === me.model ? " (default)" : ""}</Badge>) : <span className="text-slate-500">No models allowed. Ask your administrator.</span>}</div>
              <Bar label="Allocation" used={me.tokens_used} limit={me.token_limit} />
              {PERIODS.map(([period, label]) => <Bar key={period} label={label} used={me.usage[period].used} limit={me.usage[period].limit} />)}
              {me.model_limits.map((i: any) => <p key={`${i.model}-${i.period}`} className="text-xs text-slate-500">{i.model}: {i.tokens.toLocaleString()} tokens per {i.period}</p>)}
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
