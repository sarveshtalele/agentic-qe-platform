"use client";

import { Activity, BookOpen, UsersRound, Bot, CheckSquare, FileText, FolderKanban, Settings, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth, UserMenu } from "./AuthGate";
import { ThemeToggle } from "./ui";

const nav = [
  { href: "/", label: "Projects", icon: FolderKanban },
  { href: "/approvals", label: "Approvals", icon: CheckSquare },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/observability", label: "Observability", icon: Activity },
  { href: "/templates", label: "Templates", icon: FileText },
  { href: "/docs", label: "Documentation", icon: BookOpen },
  { href: "/users", label: "Users", icon: UsersRound, admin: true },
  { href: "/settings", label: "Settings", icon: Settings, admin: true },
];

/** Workspace frame for pages outside a project: brand and left navigation. */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const links = nav.filter((item) => !item.admin || user?.role === "admin");
  const [pending, setPending] = useState(0);
  useEffect(() => {
    const load = () => api("/approvals").then((items) => setPending(items.length)).catch(() => {});
    load();
    const timer = setInterval(load, 10_000);
    return () => clearInterval(timer);
  }, [pathname]);
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-[#060a17]">
        <Link href="/" className="mb-4 flex items-center gap-2.5 border-b border-slate-200 px-1 pb-3 dark:border-slate-800">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white"><ShieldCheck className="h-4 w-4" /></span>
          <span className="text-base font-bold">Agentic QE Platform</span>
        </Link>
        <nav aria-label="Workspace" className="flex-1 space-y-0.5">
          {links.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined} className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-semibold transition ${active ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-900"}`}>
                <Icon className="h-4 w-4 shrink-0" />
                <span className="flex-1">{item.label}</span>
                {item.href === "/approvals" && pending > 0 && <span data-testid="approvals-badge" className="rounded-full bg-amber-500 px-1.5 text-[11px] font-bold text-slate-950">{pending}</span>}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex items-center justify-end gap-3 border-b border-slate-200 bg-white/95 px-6 py-2.5 backdrop-blur dark:border-slate-800 dark:bg-[#060a17]/90">
          <UserMenu />
          <ThemeToggle />
        </header>
        <main className="mx-auto max-w-6xl p-6">{children}</main>
      </div>
    </div>
  );
}
