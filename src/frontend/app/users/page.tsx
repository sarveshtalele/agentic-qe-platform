"use client";

import { Plus, Save, UserRound } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { Badge, Button, Card, Empty, ErrorNote, Field, inputClass, PageTitle, Spinner, useToast } from "../../components/ui";
import { api } from "../../lib/api";

const blank = { username: "", password: "", role: "developer", token_limit: "", active_from: "", active_until: "" };
const ROLES = [["developer", "Developer"], ["qe_lead", "QE lead"], ["ba", "BA"], ["viewer", "Viewer (read only)"]] as const;
const PERIODS = [["day", "Daily"], ["week", "Weekly"], ["month", "Monthly"]] as const;
type Limits = Record<string, string>;
const toNumber = (text: string) => (text === "" ? null : Number(text));

function UsageBar({ label, used, limit }: { label: string; used: number; limit: number | null }) {
  const share = limit ? Math.min(100, Math.round((100 * used) / limit)) : 0;
  return (
    <div className="text-xs" data-testid={`usage-${label.toLowerCase()}`}>
      <p className="mb-0.5 text-slate-500">{label}: {used.toLocaleString()} of {limit === null ? "unlimited" : limit.toLocaleString()} tokens</p>
      {limit !== null && <div className="h-1.5 rounded bg-slate-200 dark:bg-slate-800"><div className={`h-1.5 rounded ${share >= 100 ? "bg-rose-500" : share >= 80 ? "bg-amber-500" : "bg-indigo-500"}`} style={{ width: `${share}%` }} /></div>}
    </div>
  );
}

function LimitInputs({ values, onChange, name }: { values: Limits; onChange: (period: string, value: string) => void; name: string }) {
  return (
    <div className="flex flex-wrap gap-2">
      {PERIODS.map(([period, label]) => (
        <label key={period} className="text-xs text-slate-500">{label}<input aria-label={`${label} limit for ${name}`} type="number" min={0} className={`${inputClass} !w-28`} placeholder="No limit" value={values[period] ?? ""} onChange={(e) => onChange(period, e.target.value)} /></label>
      ))}
    </div>
  );
}

/** Tick the models a user may use, pick their default, and optionally limit a model. A user with none ticked cannot run anything. */
function ModelTicks({ all, ticked, setTicked, def, setDef, perModel, setPerModel, who }: { all: any[]; ticked: string[]; setTicked: (v: string[]) => void; def: string; setDef: (v: string) => void; perModel?: Record<string, Limits>; setPerModel?: (v: Record<string, Limits>) => void; who: string }) {
  if (!all.length) return <p className="text-xs text-slate-500">No models yet. Add one under Settings, then tick it here.</p>;
  const toggle = (name: string, on: boolean) => {
    const next = on ? [...ticked, name] : ticked.filter((n) => n !== name);
    setTicked(next);
    if (!next.includes(def)) setDef(next[0] || "");
  };
  return (
    <fieldset className="space-y-1.5" data-testid="model-ticks">
      <legend className="text-xs font-semibold text-slate-700 dark:text-slate-300">Allowed models {ticked.length === 0 && <span className="font-normal text-rose-500">(none ticked: this user cannot run anything)</span>}</legend>
      {all.map((m) => (
        <div key={m.name} className="space-y-1">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <label className="flex items-center gap-1.5"><input type="checkbox" aria-label={`Allow ${m.name}`} checked={ticked.includes(m.name)} onChange={(e) => toggle(m.name, e.target.checked)} />{m.label || m.name}{!m.enabled && <Badge tone="slate">off</Badge>}</label>
            {ticked.includes(m.name) && <label className="flex items-center gap-1 text-xs text-slate-500"><input type="radio" name={`default-${who}`} aria-label={`Default ${m.name} for ${who}`} checked={def === m.name} onChange={() => setDef(m.name)} />default</label>}
          </div>
          {perModel && setPerModel && ticked.includes(m.name) && (
            <div className="ml-6"><p className="text-[11px] text-slate-500">Limit on {m.name} alone</p><LimitInputs name={`${who} on ${m.name}`} values={perModel[m.name] || {}} onChange={(period, value) => setPerModel({ ...perModel, [m.name]: { ...(perModel[m.name] || {}), [period]: value } })} /></div>
          )}
        </div>
      ))}
    </fieldset>
  );
}

function UserCard({ user, all, onChange }: { user: any; all: any[]; onChange: () => void }) {
  const [form, setForm] = useState({ password: "", role: user.account_role as string, token_limit: user.token_limit ?? "", active_from: user.active_from || "", active_until: user.active_until || "" });
  const [ticked, setTicked] = useState<string[]>(user.models);
  const [def, setDef] = useState<string>(user.model);
  const [limits, setLimits] = useState<Limits>(Object.fromEntries(PERIODS.map(([p]) => [p, user.limits[p] ?? ""])));
  const [perModel, setPerModel] = useState<Record<string, Limits>>(() => {
    const out: Record<string, Limits> = {};
    for (const item of user.model_limits) out[item.model] = { ...(out[item.model] || {}), [item.period]: String(item.tokens) };
    return out;
  });
  const [error, setError] = useState("");
  const toast = useToast();
  const set = (name: string, value: string) => setForm((f) => ({ ...f, [name]: value }));
  const save = async (extra: object = {}) => {
    setError("");
    try {
      const { password, ...rest } = form;
      const model_limits = ticked.flatMap((model) => PERIODS.flatMap(([period]) => (perModel[model]?.[period] ? [{ model, period, tokens: Number(perModel[model][period]) }] : [])));
      await api(`/users/${user.id}`, { method: "PATCH", json: { ...rest, models: ticked, model: def, limits: Object.fromEntries(PERIODS.map(([p]) => [p, toNumber(limits[p])])), model_limits, token_limit: form.token_limit === "" ? null : Number(form.token_limit), ...(password ? { password } : {}), ...extra } });
      set("password", "");
      onChange();
      toast("User saved");
    } catch (e: any) {
      setError(e.message);
    }
  };
  return (
    <Card title={<span className="flex items-center gap-2"><UserRound className="h-4 w-4" /> {user.username}</span>} actions={<Badge tone={user.status === "Active" ? "emerald" : "rose"}>{user.status}</Badge>}>
      <div data-testid="user-card">
        <div className="mb-3 space-y-2">
          <UsageBar label="Allocation" used={user.tokens_used} limit={user.token_limit} />
          {PERIODS.map(([period, label]) => <UsageBar key={period} label={label === "Daily" ? "Today" : label === "Weekly" ? "This week" : "This month"} used={user.usage[period].used} limit={user.usage[period].limit} />)}
        </div>
        <div className="space-y-3">
          <ModelTicks all={all} ticked={ticked} setTicked={setTicked} def={def} setDef={setDef} perModel={perModel} setPerModel={setPerModel} who={user.username} />
          <div>
            <p className="mb-1 text-xs font-semibold text-slate-700 dark:text-slate-300">Token limits across all models</p>
            <LimitInputs name={user.username} values={limits} onChange={(period, value) => setLimits((l) => ({ ...l, [period]: value }))} />
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            <Field label="Role" hint="A viewer can read but never start, edit, or approve."><select aria-label={`Role for ${user.username}`} className={inputClass} value={form.role} onChange={(e) => set("role", e.target.value)}>{ROLES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
            <Field label="Token allocation"><input aria-label={`Tokens for ${user.username}`} type="number" min={0} className={inputClass} placeholder="Unlimited" value={form.token_limit} onChange={(e) => set("token_limit", e.target.value)} /></Field>
            <Field label="Active from"><input type="date" className={inputClass} value={form.active_from} onChange={(e) => set("active_from", e.target.value)} /></Field>
            <Field label="Active until"><input aria-label={`Active until for ${user.username}`} type="date" className={inputClass} value={form.active_until} onChange={(e) => set("active_until", e.target.value)} /></Field>
            <Field label="New password" hint="Leave blank to keep it."><input type="password" autoComplete="new-password" className={inputClass} value={form.password} onChange={(e) => set("password", e.target.value)} /></Field>
          </div>
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
  const [all, setAll] = useState<any[]>([]);
  const [ticked, setTicked] = useState<string[]>([]);
  const [def, setDef] = useState("");
  const [form, setForm] = useState(blank);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const load = useCallback(() => api("/users").then(setUsers).catch((e) => setError(e.message)), []);
  useEffect(() => {
    load();
    api("/models").then(setAll).catch((e) => setError(e.message));
  }, [load]);
  const set = (name: string, value: string) => setForm((f) => ({ ...f, [name]: value }));
  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/users", { json: { ...form, models: ticked, model: def, token_limit: form.token_limit === "" ? null : Number(form.token_limit), active_from: form.active_from || null, active_until: form.active_until || null } });
      setForm(blank);
      setTicked([]);
      setDef("");
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
      <PageTitle title="Users" subtitle="Create accounts and tick the models each may use, and set token limits, allocation, and active dates. Each user sees only their own projects." />
      <Card title="New user">
        <form onSubmit={create} className="grid gap-2 md:grid-cols-3">
          <Field label="Username"><input required name="new-username" autoComplete="off" className={inputClass} value={form.username} onChange={(e) => set("username", e.target.value)} /></Field>
          <Field label="Password" hint="At least 10 characters."><input required type="password" name="new-password" autoComplete="new-password" className={inputClass} value={form.password} onChange={(e) => set("password", e.target.value)} /></Field>
          <Field label="Role"><select name="new-role" className={inputClass} value={form.role} onChange={(e) => set("role", e.target.value)}>{ROLES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
          <Field label="Token allocation" hint="Blank is unlimited."><input type="number" min={0} name="new-tokens" className={inputClass} value={form.token_limit} onChange={(e) => set("token_limit", e.target.value)} /></Field>
          <Field label="Active from"><input type="date" name="new-from" className={inputClass} value={form.active_from} onChange={(e) => set("active_from", e.target.value)} /></Field>
          <Field label="Active until"><input type="date" name="new-until" className={inputClass} value={form.active_until} onChange={(e) => set("active_until", e.target.value)} /></Field>
          <div className="md:col-span-3"><ModelTicks all={all} ticked={ticked} setTicked={setTicked} def={def} setDef={setDef} who="new user" /></div>
          <div className="md:col-span-3"><ErrorNote message={error} /><Button type="submit" busy={busy}><Plus className="h-4 w-4" /> Create user</Button></div>
        </form>
      </Card>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {!users ? <Spinner /> : users.length ? users.map((u) => <UserCard key={`${u.id}-${u.status}`} user={u} all={all} onChange={load} />) : <div className="lg:col-span-2"><Empty title="No users yet">Create the first one above.</Empty></div>}
      </div>
    </AppShell>
  );
}
