"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { pages } from "../../../content/docs";
import { Empty } from "../../../components/ui";

const slugify = (text: string) => text.toLowerCase().replace(/`/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const textOf = (node: ReactNode): string => (typeof node === "string" ? node : Array.isArray(node) ? node.map(textOf).join("") : "");

export default function DocPageView() {
  const { slug } = useParams<{ slug: string }>();
  const index = pages.findIndex((p) => p.slug === slug);
  if (index < 0) return <div className="py-10"><Empty title="Page not found"><Link className="text-indigo-500 underline" href="/docs/introduction">Go to the introduction</Link></Empty></div>;
  const page = pages[index];
  const previous = pages[index - 1];
  const next = pages[index + 1];
  const headings = [...page.body.matchAll(/^## (.+)$/gm)].map((m) => m[1]);
  return (
    <div className="flex gap-8">
      <article className="min-w-0 flex-1 py-6">
        <p className="mb-2 text-xs text-slate-500" aria-label="Breadcrumb">Docs <span aria-hidden>/</span> {page.group} <span aria-hidden>/</span> <span className="text-slate-700 dark:text-slate-300">{page.title}</span></p>
        <h1 className="text-3xl font-bold tracking-tight">{page.title}</h1>
        <p className="mt-2 text-base text-slate-600 dark:text-slate-400">{page.summary}</p>
        <div className="docs-body prose-atlas mt-6">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
            h2: ({ children }) => <h2 id={slugify(textOf(children))}>{children}</h2>,
            a: ({ href, children }) => (href?.startsWith("/") ? <Link href={href}>{children}</Link> : <a href={href} target="_blank" rel="noreferrer">{children}</a>),
          }}>{page.body}</ReactMarkdown>
        </div>
        <nav aria-label="Previous and next pages" className="mt-10 grid gap-3 border-t border-slate-200 pt-5 sm:grid-cols-2 dark:border-slate-800">
          {previous ? <Link href={`/docs/${previous.slug}`} className="rounded-lg border border-slate-200 p-3 text-sm hover:border-indigo-500 dark:border-slate-800"><span className="flex items-center gap-1 text-xs text-slate-500"><ChevronLeft className="h-3 w-3" /> Previous</span><b>{previous.title}</b></Link> : <span />}
          {next && <Link href={`/docs/${next.slug}`} className="rounded-lg border border-slate-200 p-3 text-right text-sm hover:border-indigo-500 dark:border-slate-800"><span className="flex items-center justify-end gap-1 text-xs text-slate-500">Next <ChevronRight className="h-3 w-3" /></span><b>{next.title}</b></Link>}
        </nav>
      </article>
      <aside className="sticky top-14 hidden h-fit w-48 shrink-0 py-6 text-sm xl:block">
        <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">On this page</p>
        <ul className="space-y-1.5" data-testid="docs-toc">{headings.map((h) => <li key={h}><a className="text-slate-600 hover:text-indigo-500 dark:text-slate-400" href={`#${slugify(h)}`}>{h.replace(/`/g, "")}</a></li>)}</ul>
      </aside>
    </div>
  );
}
