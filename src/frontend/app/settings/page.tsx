"use client";

import { Download, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button, Card, ErrorNote, Field, inputClass, PageTitle, useToast } from "../../components/ui";
import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthGate";
import { api } from "../../lib/api";

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
        {health && <Card title="System health"><ul className="flex flex-wrap gap-3 text-sm">{[["Git", health.git], ["Node.js", health.node], ["npx", health.npx], ["Ruff", health.ruff], ["Model", health.llm]].map(([name, ok]) => <li key={name as string} className="flex items-center gap-1.5"><span className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-500" : "bg-rose-500"}`} />{name} {ok ? "ready" : "missing"}</li>)}</ul></Card>}
        <Card title="Model provider">
          <div className="space-y-3">
            <Field label="OpenAI-compatible base URL" hint="OpenAI, Azure OpenAI, LiteLLM, Ollama, or any compatible endpoint."><input name="base-url" className={inputClass} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1" /></Field>
            <Field label="Model"><input name="model" className={inputClass} value={model} onChange={(e) => setModel(e.target.value)} /></Field>
            <Field label="API key" hint={llm?.has_api_key ? `A key ending ${llm.api_key_hint} is set. Leave blank to keep it. Keys are encrypted at rest.` : "Keys are encrypted at rest."}><input name="api-key" type="password" autoComplete="off" className={inputClass} value={apiKey} onChange={(e) => setApiKey(e.target.value)} /></Field>
            <div className="flex gap-2"><Button onClick={save}>Save</Button><Button variant="secondary" busy={testing} onClick={test}>Test connection</Button></div>
            {result && (result.ok ? <p className="text-sm text-emerald-600 dark:text-emerald-400" data-testid="llm-ok">Connected to {result.model} in {result.latency_ms} ms. Reply: {result.reply}</p> : <ErrorNote message={result.error} />)}
          </div>
        </Card>
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
