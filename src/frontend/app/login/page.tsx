"use client";

import { LogIn, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, ErrorNote, Field, inputClass, ThemeToggle } from "../../components/ui";
import { api } from "../../lib/api";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [configured, setConfigured] = useState(true);
  useEffect(() => {
    api("/auth/status").then((status) => setConfigured(status.configured)).catch(() => {});
  }, []);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/auth/login", { json: { username, password } });
      setPassword("");
      window.location.href = "/"; // a full load, so every page starts from the new session
    } catch (e: any) {
      setPassword("");
      setError(e.message);
      setBusy(false);
    }
  };
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="absolute right-4 top-4"><ThemeToggle /></div>
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-[#0b1329]">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-white"><ShieldCheck className="h-5 w-5" /></span>
          <h1 className="text-lg font-bold">Agentic QE Platform</h1>
        </div>
        {!configured && <p role="alert" className="rounded-lg border border-amber-500/50 bg-amber-500/10 p-2 text-sm">Sign-in is not set up. Add <code>ATLAS_ADMIN_USERNAME</code> and <code>ATLAS_ADMIN_PASSWORD</code> to <code>.env</code>, then restart.</p>}
        <Field label="Username"><input required name="username" autoComplete="username" className={inputClass} value={username} onChange={(e) => setUsername(e.target.value)} /></Field>
        <Field label="Password"><input required type="password" name="password" autoComplete="current-password" className={inputClass} value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        <ErrorNote message={error} />
        <Button type="submit" busy={busy} disabled={!configured} className="w-full justify-center"><LogIn className="h-4 w-4" /> Sign in</Button>
      </form>
    </div>
  );
}
