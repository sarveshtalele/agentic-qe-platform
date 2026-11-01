"use client";

import { Loader2, Moon, Sun } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";

export const inputClass = "w-full rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-[#070d1f] px-3 py-2 text-sm text-slate-900 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-500";

const variants = {
  primary: "bg-indigo-600 hover:bg-indigo-500 text-white",
  secondary: "border border-slate-300 dark:border-slate-700 text-slate-800 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800",
  danger: "border border-rose-500/50 text-rose-600 dark:text-rose-400 hover:bg-rose-500/10",
  success: "bg-emerald-600 hover:bg-emerald-500 text-white",
};

export function Button({ variant = "primary", busy, children, className = "", ...props }: { variant?: keyof typeof variants; busy?: boolean } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button {...props} disabled={props.disabled || busy} className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant]} ${className}`}>
      {busy && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

export function Card({ title, actions, children, className = "" }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0b1329] p-4 ${className}`}>
      {(title || actions) && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">{title}</h2>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

const tones: Record<string, string> = {
  "NO NEW FAILURES": "amber", INCOMPLETE: "rose", approved: "emerald", completed: "emerald", PASS: "emerald", passed: "emerald", valid: "emerald", open: "amber",
  running: "indigo", waiting_approval: "amber", pending: "slate", draft: "slate", INCONCLUSIVE: "amber",
  rejected: "rose", failed: "rose", FAIL: "rose", interrupted: "rose", cancelled: "slate", critical: "rose", high: "rose", medium: "amber", low: "slate", info: "slate",
};
const toneClass: Record<string, string> = {
  emerald: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  amber: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  rose: "bg-rose-500/15 text-rose-700 dark:text-rose-400",
  indigo: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300",
  slate: "bg-slate-500/15 text-slate-700 dark:text-slate-300",
};

export function Badge({ children, tone }: { children: ReactNode; tone?: string }) {
  const resolved = tone || tones[String(children)] || "slate";
  return <span className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${toneClass[resolved]}`}>{String(children).replace("_", " ")}</span>;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 dark:border-slate-700 p-8 text-center">
      <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">{title}</p>
      {children && <div className="mt-2 text-sm text-slate-500">{children}</div>}
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <p className="flex items-center gap-2 p-4 text-sm text-slate-500">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </p>
  );
}

export function ErrorNote({ message }: { message?: string | null }) {
  if (!message) return null;
  return <p role="alert" className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-700 dark:text-rose-300">{message}</p>;
}

// document text is untrusted, and loading an outside image would tell that site who is reading
function SafeImage({ src, alt }: { src?: unknown; alt?: string }) {
  const url = typeof src === "string" ? src : "";
  if (url.startsWith("/api/documents/")) return <img src={url} alt={alt || ""} className="my-2 max-w-full rounded-lg" />; // eslint-disable-line @next/next/no-img-element
  return <span className="text-xs text-slate-500">[Image from another site not loaded: {alt || url}]</span>;
}

export function Markdown({ children }: { children: string }) {
  return (
    <div className="prose-atlas">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ img: SafeImage }}>{children}</ReactMarkdown>
    </div>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">{label}</span>
      {children}
      {hint && <span className="block text-xs text-slate-500">{hint}</span>}
    </label>
  );
}

export function PageTitle({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-bold text-slate-900 dark:text-white">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-400">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function ThemeToggle() {
  const [theme, setTheme] = useState("dark");
  useEffect(() => setTheme(document.documentElement.classList.contains("light") ? "light" : "dark"), []);
  const flip = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.classList.remove("dark", "light");
    document.documentElement.classList.add(next);
    try {
      localStorage.setItem("atlas_theme", next);
    } catch {}
  };
  return (
    <button onClick={flip} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} className="rounded-lg border border-slate-300 dark:border-slate-700 p-2 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800">
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}

const ToastContext = createContext<(message: string, tone?: "ok" | "error") => void>(() => {});
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<{ message: string; tone: string } | null>(null);
  const show = useCallback((message: string, tone: "ok" | "error" = "ok") => {
    setToast({ message, tone });
    setTimeout(() => setToast(null), 5000);
  }, []);
  return (
    <ToastContext.Provider value={show}>
      {children}
      {toast && (
        <div role="status" className={`fixed bottom-5 right-5 z-50 max-w-md rounded-lg px-4 py-3 text-sm font-medium text-white shadow-xl ${toast.tone === "error" ? "bg-rose-600" : "bg-emerald-600"}`}>
          {toast.message}
        </div>
      )}
    </ToastContext.Provider>
  );
}
