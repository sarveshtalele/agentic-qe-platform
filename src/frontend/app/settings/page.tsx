"use client";

import { Download, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button, Card, ErrorNote, Field, inputClass, PageTitle, useToast } from "../../components/ui";
import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthGate";
import { api, when } from "../../lib/api";

/** The models on the one endpoint. A listed name may not work, so loaded names start off and each has a Test that sends a real short completion. */
function ModelList() {
  const [items, setItems] = useState<any[] | null>(null);
  const [name, setName] = useState("");
  const [zone, setZone] = useState("");
  const [results, setResults] = useState<Record<string, any>>({});
  const [testing, setTesting] = useState("");
  const [checking, setChecking] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();
  const load = useCallback(() => api("/models").then(setItems).catch((e) => setError(e.message)), []);
  useEffect(() => {
    load();
    api("/settings/timezone").then((z) => setZone(z.timezone));
  }, [load]);
  const guard = async (work: () => Promise<unknown>) => {
    setError("");
    try {
      await work();
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  };
  const patch = (model: string, json: object) => guard(() => api("/models", { method: "PATCH", json: { name: model, ...json } }));
  const test = async (model: string) => {
    setTesting(model);
    setResults((r) => ({ ...r, [model]: undefined }));
    try {
      const outcome = await api("/settings/llm/test", { json: { model } });
      setResults((r) => ({ ...r, [model]: outcome }));
    } catch (e: any) {
      setResults((r) => ({ ...r, [model]: { ok: false, error: e.message } }));
    }
    setTesting("");
  };
  const checkTools = async (model: string) => {
    setChecking(model);
    await guard(async () => { await api("/models/tool-check", { json: { name: model } }); });
    setChecking("");
  };
  const loadFromProxy = async () => {
    setLoading(true);
    await guard(async () => {
      const found = await api("/models/load", { method: "POST" });
      toast(`${found.listed} models listed, ${found.added.length} new. They are switched off until you test and enable them.`);
    });
    setLoading(false);
  };
  return (
    <Card title="Models" actions={<Button variant="secondary" busy={loading} onClick={loadFromProxy}>Load from proxy</Button>}>
      <div className="space-y-3" data-testid="model-list">
        <p className="text-xs text-slate-500">All models use the URL and key above. Switch a model on only after its test works. Each user may use only the models ticked for them on the Users page.</p>
        {items === null ? null : items.length === 0 ? <p className="text-sm text-slate-500" data-testid="models-empty">No models yet. Add one by name, or load the names your proxy offers.</p> : (
          <ul className="divide-y divide-slate-200 text-sm dark:divide-slate-800">
            {items.map((m) => (
              <li key={m.name} className="space-y-1 py-2">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="mono min-w-0 flex-1 truncate text-xs font-semibold">{m.name}</span>
                  <label className="flex items-center gap-1 text-xs"><input type="checkbox" aria-label={`Enable ${m.name}`} checked={m.enabled} onChange={(e) => patch(m.name, { enabled: e.target.checked })} />On</label>
                  <label className="flex items-center gap-1 text-xs"><input type="radio" name="default-model" aria-label={`Default ${m.name}`} checked={m.is_default} disabled={!m.enabled} onChange={() => patch(m.name, { is_default: true })} />Default</label>
                  <Button variant="secondary" className="!px-2 !py-1 !text-xs" busy={testing === m.name} onClick={() => test(m.name)}>Test</Button>
                  <Button variant="secondary" className="!px-2 !py-1 !text-xs" busy={checking === m.name} onClick={() => checkTools(m.name)}>Check tools</Button>
                  <button aria-label={`Remove ${m.name}`} onClick={() => guard(() => api(`/models?name=${encodeURIComponent(m.name)}`, { method: "DELETE" }))} className="text-slate-400 hover:text-rose-500"><Trash2 className="h-4 w-4" /></button>
                </div>
                <p className="text-xs" data-testid={`tool-status-${m.name}`}>
                  Tools: {m.tools_status === "passed" ? <b className="text-emerald-600 dark:text-emerald-400">passed</b> : m.tools_status === "failed" ? <b className="text-rose-500">failed</b> : <span className="text-slate-500">not checked</span>}
                  {m.tools_status && <span className="text-slate-500"> ({m.tools_reason}) checked {when(m.tools_checked_at)}, max_tokens {m.tools_max_tokens}</span>}
                </p>
                {results[m.name] && (results[m.name].ok ? <p className="text-xs text-emerald-600 dark:text-emerald-400">Works: replied in {results[m.name].latency_ms} ms, {results[m.name].tokens} tokens. Reply: {results[m.name].reply}</p> : <p role="alert" className="text-xs text-rose-500">{results[m.name].error}</p>)}
              </li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Add a model by name"><input name="add-model" className={inputClass} value={name} onChange={(e) => setName(e.target.value)} placeholder="deepseek-v4-flash-global" /></Field>
          <Button disabled={!name.trim()} onClick={() => guard(async () => { await api("/models", { json: { name } }); setName(""); })}><Plus className="h-4 w-4" /> Add</Button>
        </div>
        <ErrorNote message={error} />
        <div className="flex flex-wrap items-end gap-2 border-t border-slate-200 pt-3 dark:border-slate-800">
          <Field label="Time zone for token limits" hint="Days reset at midnight, weeks on Monday, months on the 1st, in this zone."><input name="timezone" className={inputClass} value={zone} onChange={(e) => setZone(e.target.value)} /></Field>
          <Button variant="secondary" onClick={() => guard(async () => { await api("/settings/timezone", { method: "PUT", json: { timezone: zone } }); toast("Time zone saved"); })}>Save zone</Button>
        </div>
      </div>
    </Card>
  );
}

const GATES = ["G0 Intake", "G1 Requirements", "G2 Plan", "G3 Design", "G4 Generate", "G5 Release"];

/** Which roles may sign each gate. A gate with nothing ticked can be signed by anyone who can write. The admin can always sign. */
function GateRoles() {
  const [map, setMap] = useState<Record<string, string[]> | null>(null);
  const [roles, setRoles] = useState<string[]>([]);
  const [error, setError] = useState("");
  const toast = useToast();
  useEffect(() => { api("/settings/gate-roles").then((r) => { setMap(r.roles); setRoles(r.assignable); }).catch((e) => setError(e.message)); }, []);
  if (!map) return <Card title="Who may sign each gate"><ErrorNote message={error} /></Card>;
  const toggle = (gate: number, role: string, on: boolean) => setMap((m) => ({ ...m, [gate]: on ? [...(m?.[gate] || []), role] : (m?.[gate] || []).filter((r) => r !== role) }));
  const save = async () => {
    setError("");
    try { const r = await api("/settings/gate-roles", { method: "PUT", json: { roles: map } }); setMap(r.roles); toast("Gate roles saved"); } catch (e: any) { setError(e.message); }
  };
  return (
    <Card title="Who may sign each gate" actions={<Button variant="secondary" onClick={save}>Save</Button>}>
      <p className="mb-2 text-xs text-slate-500">Tick the roles allowed to sign a gate. With none ticked, anyone who can write in the project may sign it. A project member needs the role on their account and in the project.</p>
      <table className="w-full text-left text-sm" data-testid="gate-roles">
        <thead><tr><th>Gate</th>{roles.map((r) => <th key={r} className="text-xs">{r.replace("_", " ")}</th>)}</tr></thead>
        <tbody>{GATES.map((name, gate) => <tr key={gate}><td>{name}</td>{roles.map((r) => <td key={r}><input type="checkbox" aria-label={`${r} may sign ${name}`} checked={(map[gate] || []).includes(r)} onChange={(e) => toggle(gate, r, e.target.checked)} /></td>)}</tr>)}</tbody>
      </table>
      <ErrorNote message={error} />
    </Card>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const [logDay, setLogDay] = useState("");
  const [llm, setLlm] = useState<any>(null);
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [result, setResult] = useState<any>(null);
  const [testing, setTesting] = useState(false);
  const [connections, setConnections] = useState<any[]>([]);
  const [token, setToken] = useState("");
  const [label, setLabel] = useState("");
  const [error, setError] = useState("");
  const [health, setHealth] = useState<any>(null);
  const toast = useToast();
  const loadConnections = useCallback(() => api("/connections").then(setConnections), []);
  useEffect(() => {
    setLogDay(new Date().toLocaleDateString("en-CA")); // YYYY-MM-DD, set after mount so server and browser render alike
    api("/settings/llm").then((data) => {
      setLlm(data);
      setBaseUrl(data.base_url);
      setModel(data.model);
    });
    loadConnections();
    api("/health").then(setHealth);
  }, [loadConnections]);
  const save = async () => {
    setLlm(await api("/settings/llm", { method: "PUT", json: { base_url: baseUrl, model, api_key: apiKey || null } }));
    setApiKey("");
    toast("Model settings saved");
  };
  const test = async () => {
    setTesting(true);
    setResult(await api("/settings/llm/test", { json: { base_url: baseUrl, model, api_key: apiKey || null } }));
    setTesting(false);
  };
  const connect = async () => {
    setError("");
    try {
      const created = await api("/connections/github", { json: { token, label } });
      setToken("");
      setLabel("");
      loadConnections();
      toast(`Connected as ${created.login}`);
    } catch (e: any) {
      setError(e.message);
    }
  };
  return (
    <AppShell>
      <PageTitle title="Settings" />
      <div className="space-y-4">
        {health && <Card title="System health"><ul className="flex flex-wrap gap-3 text-sm">{[["Git", health.git], ["Node.js", health.node], ["npx", health.npx], ["Ruff", health.ruff], ["Model", health.llm], ["Skills", health.skills && health.skills.loaded > 0 && health.skills.problems === 0]].map(([name, ok]) => <li key={name as string} className="flex items-center gap-1.5"><span className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-500" : "bg-rose-500"}`} />{name} {ok ? "ready" : "missing"}</li>)}</ul>{health.skills && <p className="mt-2 text-xs text-slate-500" data-testid="health-skills">{health.skills.loaded} skills loaded{health.skills.problems ? `, ${health.skills.problems} could not be loaded (see the server log)` : ""}. Tool check on enabled models: {health.tool_checks.passed} passed, {health.tool_checks.failed} failed, {health.tool_checks.not_checked} not checked.</p>}</Card>}
        <Card title="Model provider">
          <div className="space-y-3">
            <Field label="OpenAI-compatible base URL" hint="OpenAI, Azure OpenAI, LiteLLM, Ollama, or any compatible endpoint."><input name="base-url" className={inputClass} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1" /></Field>
            <Field label="Fallback model" hint="Used only when no default is set in the Models list below."><input name="model" className={inputClass} value={model} onChange={(e) => setModel(e.target.value)} /></Field>
            <Field label="API key" hint={llm?.has_api_key ? `A key ending ${llm.api_key_hint} is set. Leave blank to keep it. Keys are encrypted at rest.` : "Keys are encrypted at rest."}><input name="api-key" type="password" autoComplete="off" className={inputClass} value={apiKey} onChange={(e) => setApiKey(e.target.value)} /></Field>
            <div className="flex gap-2"><Button onClick={save}>Save</Button><Button variant="secondary" busy={testing} onClick={test}>Test connection</Button></div>
            {result && (result.ok ? <p className="text-sm text-emerald-600 dark:text-emerald-400" data-testid="llm-ok">Connected to {result.model} in {result.latency_ms} ms. Reply: {result.reply}</p> : <ErrorNote message={result.error} />)}
          </div>
        </Card>
        {user?.role === "admin" && <ModelList />}
        {user?.role === "admin" && <GateRoles />}
        {user?.role === "admin" && (
          <Card title="Application log">
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Day"><input type="date" aria-label="Log day" className={inputClass} value={logDay} onChange={(e) => setLogDay(e.target.value)} /></Field>
              {logDay && <a className="inline-flex items-center gap-1.5 text-sm text-indigo-500 underline" href={`/api/logs?date=${logDay}`}><Download className="h-4 w-4" /> Download log for {logDay}</a>}
            </div>
            <p className="mt-2 text-xs text-slate-500">One JSON line per event that day. Passwords, keys, and request bodies are not written to it.</p>
          </Card>
        )}
        <Card title="Private repository access">
          <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">Create a GitHub fine-grained personal access token with read access to the repository contents, plus write access to contents and pull requests if you want Agentic QE Platform to open pull requests. It is checked against GitHub, encrypted at rest, and never placed in URLs or clone config.</p>
          <div className="space-y-3">
            <Field label="Label"><input className={inputClass} value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Work GitHub" /></Field>
            <Field label="GitHub token"><input type="password" autoComplete="off" className={inputClass} value={token} onChange={(e) => setToken(e.target.value)} /></Field>
            <ErrorNote message={error} />
            <Button onClick={connect} disabled={token.length < 8}>Validate and save</Button>
          </div>
          {connections.length > 0 && (
            <ul className="mt-3 divide-y divide-slate-200 text-sm dark:divide-slate-800">{connections.map((c) => (
              <li key={c.id} className="flex items-center justify-between py-1.5"><span>{c.label} <span className="text-xs text-slate-500">({c.login})</span></span><button aria-label={`Remove ${c.label}`} onClick={() => api(`/connections/${c.id}`, { method: "DELETE" }).then(loadConnections)} className="text-slate-400 hover:text-rose-500"><Trash2 className="h-4 w-4" /></button></li>
            ))}</ul>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
