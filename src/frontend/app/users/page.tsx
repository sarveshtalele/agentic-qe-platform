"use client";

import { Plus, Save, UserRound } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { Badge, Button, Card, Empty, ErrorNote, Field, inputClass, PageTitle, Spinner, useToast } from "../../components/ui";
import { api } from "../../lib/api";

const blank = { username: "", password: "", model: "", token_limit: "", active_from: "", active_until: "" };

function UserCard({ user, onChange }: { user: any; onChange: () => void }) {
  const [form, setForm] = useState({ password: "", model: user.model, token_limit: user.token_limit ?? "", active_from: user.active_from || "", active_until: user.active_until || "" });
  const [error, setError] = useState("");
  const toast = useToast();
  const set = (name: string, value: string) => setForm((f) => ({ ...f, [name]: value }));
  const save = async (extra: object = {}) => {
    setError("");
    try {
      const { password, ...rest } = form;
      await api(`/users/${user.id}`, { method: "PATCH", json: { ...rest, token_limit: form.token_limit === "" ? null : Number(form.token_limit), ...(password ? { password } : {}), ...extra } });
      set("password", "");
      onChange();
      toast("User saved");
    } catch (e: any) {
      setError(e.message);
    }
  };
  const share = user.token_limit ? Math.min(100, Math.round((100 * user.tokens_used) / user.token_limit)) : 0;
  return (
    <Card title={<span className="flex items-center gap-2"><UserRound className="h-4 w-4" /> {user.username}</span>} actions={<Badge tone={user.status === "Active" ? "emerald" : "rose"}>{user.status}</Badge>}>
      <div data-testid="user-card">
        <p className="mb-2 text-xs text-slate-500">{user.tokens_used.toLocaleString()} of {user.token_limit === null ? "unlimited" : user.token_limit.toLocaleString()} tokens used</p>
        {user.token_limit !== null && <div className="mb-3 h-1.5 rounded bg-slate-200 dark:bg-slate-800"><div className="h-1.5 rounded bg-indigo-500" style={{ width: `${share}%` }} /></div>}
        <div className="grid gap-2 md:grid-cols-2">
          <Field label="Model"><input aria-label={`Model for ${user.username}`} className={inputClass} placeholder="Default model" value={form.model} onChange={(e) => set("model", e.target.value)} /></Field>
          <Field label="Token allocation"><input aria-label={`Tokens for ${user.username}`} type="number" min={0} className={inputClass} placeholder="Unlimited" value={form.token_limit} onChange={(e) => set("token_limit", e.target.value)} /></Field>
          <Field label="Active from"><input type="date" className={inputClass} value={form.active_from} onChange={(e) => set("active_from", e.target.value)} /></Field>
          <Field label="Active until"><input aria-label={`Active until for ${user.username}`} type="date" className={inputClass} value={form.active_until} onChange={(e) => set("active_until", e.target.value)} /></Field>
          <Field label="New password" hint="Leave blank to keep it."><input type="password" autoComplete="new-password" className={inputClass} value={form.password} onChange={(e) => set("password", e.target.value)} /></Field>
        </div>
        <ErrorNote message={error} />
        <div className="mt-2 flex gap-2">
          <Button variant="secondary" onClick={() => save()}><Save className="h-4 w-4" /> Save</Button>
          {user.enabled ? <Button variant="danger" onClick={() => save({ enabled: false })}>Disable</Button> : <Button variant="success" onClick={() => save({ enabled: true })}>Enable</Button>}
        </div>
      </div>
    </Card>
  );
}

export default function UsersPage() {
  const [users, setUsers] = useState<any[] | null>(null);
  const [form, setForm] = useState(blank);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const load = useCallback(() => api("/users").then(setUsers).catch((e) => setError(e.message)), []);
  useEffect(() => {
    load();
  }, [load]);
  const set = (name: string, value: string) => setForm((f) => ({ ...f, [name]: value }));
  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/users", { json: { ...form, token_limit: form.token_limit === "" ? null : Number(form.token_limit), active_from: form.active_from || null, active_until: form.active_until || null } });
      setForm(blank);
      await load();
      toast("User created");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <AppShell>
      <PageTitle title="Users" subtitle="Create accounts and set each one's password, model, token allocation, and active dates. Each user sees only their own projects." />
      <Card title="New user">
        <form onSubmit={create} className="grid gap-2 md:grid-cols-3">
          <Field label="Username"><input required name="new-username" autoComplete="off" className={inputClass} value={form.username} onChange={(e) => set("username", e.target.value)} /></Field>
          <Field label="Password" hint="At least 10 characters."><input required type="password" name="new-password" autoComplete="new-password" className={inputClass} value={form.password} onChange={(e) => set("password", e.target.value)} /></Field>
          <Field label="Model" hint="Blank uses the default model."><input name="new-model" className={inputClass} value={form.model} onChange={(e) => set("model", e.target.value)} /></Field>
          <Field label="Token allocation" hint="Blank is unlimited."><input type="number" min={0} name="new-tokens" className={inputClass} value={form.token_limit} onChange={(e) => set("token_limit", e.target.value)} /></Field>
          <Field label="Active from"><input type="date" name="new-from" className={inputClass} value={form.active_from} onChange={(e) => set("active_from", e.target.value)} /></Field>
          <Field label="Active until"><input type="date" name="new-until" className={inputClass} value={form.active_until} onChange={(e) => set("active_until", e.target.value)} /></Field>
          <div className="md:col-span-3"><ErrorNote message={error} /><Button type="submit" busy={busy}><Plus className="h-4 w-4" /> Create user</Button></div>
        </form>
      </Card>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {!users ? <Spinner /> : users.length ? users.map((u) => <UserCard key={`${u.id}-${u.status}`} user={u} onChange={load} />) : <div className="lg:col-span-2"><Empty title="No users yet">Create the first one above.</Empty></div>}
      </div>
    </AppShell>
  );
}
