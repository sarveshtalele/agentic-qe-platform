"use client";

import { Activity, Bot, Bug, CheckSquare, ChevronLeft, ChevronRight, Code2, FileText, Files, FolderGit2, History, Home, Lock, ScrollText, Settings, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth, UserMenu } from "./AuthGate";
import { ErrorNote, Spinner, ThemeToggle } from "./ui";

const nav = [
  { href: "", label: "Overview", icon: Home },
  { href: "/repository", label: "Repository", icon: FolderGit2 },
  { href: "/ba", label: "BA Studio", icon: FileText },
  { href: "/documents", label: "Documents", icon: Files },
  { href: "/feature", label: "Feature Builder", icon: Code2 },
  { href: "/bugs", label: "Bug Scan", icon: Bug },
  { href: "/qe", label: "QE Studio", icon: ShieldCheck },
  { href: "/approvals", label: "Approvals", icon: CheckSquare },
  { href: "/governance", label: "Governance", icon: Lock },
  { href: "/runs", label: "Runs & Metrics", icon: History },
  { href: "/observability", label: "Observability", icon: Activity },
  { href: "/prompts", label: "Prompts", icon: ScrollText },
  { href: "/chat", label: "Copilot", icon: Bot },
];

const ProjectContext = createContext<{ project: any; gates: any[]; refresh: () => void }>({ project: null, gates: [], refresh: () => {} });
export const useProject = () => useContext(ProjectContext);

export function ProjectShell({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { id } = useParams<{ id: string }>();
  const pathname = usePathname();
  const [project, setProject] = useState<any>(null);
  const [gates, setGates] = useState<any[]>([]);
  const [llm, setLlm] = useState<any>(null);
  const [error, setError] = useState("");
  const [collapsed, setCollapsed] = useState(false);

  const refresh = useCallback(() => {
    Promise.all([api(`/projects/${id}`), api(`/projects/${id}/gates`)])
      .then(([p, g]) => {
        setProject(p);
        setGates(g);
      })
      .catch((e) => setError(e.message));
  }, [id]);

  useEffect(() => {
    refresh();
    api("/settings/llm").then(setLlm).catch(() => setLlm(null));
  }, [refresh, pathname]);

  const base = `/projects/${id}`;
  return (
    <div className="flex min-h-screen">
      <aside className={`sticky top-0 flex h-screen shrink-0 flex-col border-r border-slate-200 bg-white p-3 transition-all dark:border-slate-800 dark:bg-[#060a17] ${collapsed ? "w-16" : "w-60"}`}>
        <div className="mb-3 flex items-center justify-between border-b border-slate-200 pb-3 dark:border-slate-800">
          {!collapsed && (
            <Link href="/" className="flex items-center gap-1 text-xs font-semibold text-slate-600 hover:text-indigo-500 dark:text-slate-400">
              <ChevronLeft className="h-3.5 w-3.5" /> All projects
            </Link>
          )}
          <button onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} className="rounded-md border border-slate-200 p-1 text-slate-500 hover:bg-slate-100 dark:border-slate-800 dark:hover:bg-slate-800">
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>
        {!collapsed && <p className="mb-2 truncate px-2 text-sm font-bold text-slate-900 dark:text-white" title={project?.name}>{project?.name || " "}</p>}
        <nav className="flex-1 space-y-0.5 overflow-y-auto">
          {nav.map((item) => {
            const href = base + item.href;
            const active = item.href ? pathname.startsWith(href) : pathname === base;
            const Icon = item.icon;
            return (
              <Link key={item.label} href={href} title={item.label} aria-current={active ? "page" : undefined}
                className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-semibold transition ${active ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-900"} ${collapsed ? "justify-center" : ""}`}>
                <Icon className="h-4 w-4 shrink-0" />
                {!collapsed && <span className="flex-1">{item.label}</span>}
                {!collapsed && item.href === "/approvals" && project?.pending > 0 && <span className="rounded-full bg-amber-500 px-1.5 text-[11px] font-bold text-slate-950">{project.pending}</span>}
              </Link>
            );
          })}
        </nav>
        <div className="space-y-1 border-t border-slate-200 pt-2 dark:border-slate-800">
          <Link href="/templates" title="Templates" className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-semibold text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-900 ${collapsed ? "justify-center" : ""}`}>
            <FileText className="h-4 w-4 shrink-0" /> {!collapsed && "Templates"}
          </Link>
          {user?.role === "admin" && (
          <Link href="/settings" title="Settings" className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-semibold text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-900 ${collapsed ? "justify-center" : ""}`}>
            <Settings className="h-4 w-4 shrink-0" /> {!collapsed && "Settings"}
          </Link>
          )}
        </div>
      </aside>
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex flex-wrap items-center justify-end gap-3 border-b border-slate-200 bg-white/95 px-5 py-2 backdrop-blur dark:border-slate-800 dark:bg-[#060a17]/90">
          <div className="flex items-center gap-2">
            <Link href="/settings" className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-2.5 py-1.5 text-[11px] font-semibold dark:border-slate-700">
              <span className={`h-1.5 w-1.5 rounded-full ${llm?.configured ? "bg-emerald-500" : "bg-rose-500"}`} />
              <span className="mono">{llm?.configured ? llm.model : "No model configured"}</span>
            </Link>
            <UserMenu />
            <ThemeToggle />
          </div>
        </header>
        <main className="mx-auto max-w-6xl p-5">
          <ErrorNote message={error} />
          {project ? <ProjectContext.Provider value={{ project, gates, refresh }}>{children}</ProjectContext.Provider> : !error && <Spinner />}
        </main>
      </div>
    </div>
  );
}
