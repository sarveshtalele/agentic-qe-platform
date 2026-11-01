"use client";

import { Menu, Search, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo, useState } from "react";
import { groups, pages } from "../../content/docs";
import { ThemeToggle } from "../../components/ui";

function Sidebar({ current, onPick }: { current: string; onPick?: () => void }) {
  return (
    <nav aria-label="Documentation" className="space-y-5 text-sm">
      {groups.map((group) => (
        <div key={group.title}>
          <p className="mb-1.5 text-xs font-bold uppercase tracking-wide text-slate-500">{group.title}</p>
          <ul className="space-y-0.5 border-l border-slate-200 dark:border-slate-800">
            {group.pages.map((page) => (
              <li key={page.slug}>
                <Link href={`/docs/${page.slug}`} onClick={onPick} aria-current={current === page.slug ? "page" : undefined}
                  className={`-ml-px block border-l-2 py-1 pl-3 ${current === page.slug ? "border-indigo-500 font-semibold text-indigo-600 dark:text-indigo-300" : "border-transparent text-slate-600 hover:border-slate-400 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"}`}>
                  {page.title}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const current = pathname.split("/")[2] || "introduction";
  const [query, setQuery] = useState("");
  const [menu, setMenu] = useState(false);
  const found = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return [];
    return pages.filter((p) => `${p.title} ${p.summary} ${p.body}`.toLowerCase().includes(needle)).slice(0, 8);
  }, [query]);
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur dark:border-slate-800 dark:bg-[#060a17]/95">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-2.5">
          <button aria-label="Open documentation menu" aria-expanded={menu} onClick={() => setMenu(!menu)} className="lg:hidden"><Menu className="h-5 w-5" /></button>
          <Link href="/docs/introduction" className="flex shrink-0 items-center gap-2 font-bold">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600 text-white"><ShieldCheck className="h-4 w-4" /></span>
            <span className="hidden sm:inline">Agentic QE Platform</span>
            <span className="text-sm font-normal text-slate-500">Docs</span>
          </Link>
          <div className="relative ml-auto w-full max-w-xs">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
            <input aria-label="Search documentation" placeholder="Search documentation" value={query} onChange={(e) => setQuery(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-slate-50 py-1.5 pl-8 pr-2 text-sm outline-none focus:border-indigo-500 dark:border-slate-700 dark:bg-[#070d1f]" />
            {query.trim() && (
              <ul data-testid="docs-search-results" className="absolute inset-x-0 top-full mt-1 rounded-lg border border-slate-200 bg-white p-1 text-sm shadow-lg dark:border-slate-700 dark:bg-[#0b1329]">
                {found.length ? found.map((p) => (
                  <li key={p.slug}><Link href={`/docs/${p.slug}`} onClick={() => setQuery("")} className="block rounded px-2 py-1.5 hover:bg-slate-100 dark:hover:bg-slate-800"><b>{p.title}</b><span className="block truncate text-xs text-slate-500">{p.group} · {p.summary}</span></Link></li>
                )) : <li className="px-2 py-1.5 text-slate-500">No pages found</li>}
              </ul>
            )}
          </div>
          <Link href="/" className="shrink-0 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-500">Open app</Link>
          <ThemeToggle />
        </div>
        {menu && <div className="max-h-[70vh] overflow-y-auto border-t border-slate-200 p-4 lg:hidden dark:border-slate-800"><Sidebar current={current} onPick={() => setMenu(false)} /></div>}
      </header>
      <div className="mx-auto flex max-w-7xl gap-8 px-4">
        <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-56 shrink-0 overflow-y-auto py-6 lg:block"><Sidebar current={current} /></aside>
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </div>
  );
}
