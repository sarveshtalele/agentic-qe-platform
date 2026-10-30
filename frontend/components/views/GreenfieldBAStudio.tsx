"use client";

import React, { useState } from "react";
import {
  FileText,
  Sparkles,
  Download,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  FileCheck2,
  FileDown,
  FileCode,
} from "lucide-react";

interface GreenfieldBAStudioProps {
  baPrompt: string;
  setBaPrompt: (val: string) => void;
  onGenerateBRD: () => void;
  onGeneratePRD: () => void;
  docLoading: boolean;
  activeDoc: any;
  docReview: any;
  onReviewDocument: () => void;
  onRefineDocument: () => void;
  currentProjectId: string;
}

export function GreenfieldBAStudio({
  baPrompt,
  setBaPrompt,
  onGenerateBRD,
  onGeneratePRD,
  docLoading,
  activeDoc,
  docReview,
  onReviewDocument,
  onRefineDocument,
  currentProjectId,
}: GreenfieldBAStudioProps) {
  const presets = [
    {
      name: "Calculator App",
      prompt: "Python-based high-precision calculator application to replace manual calculation processes across engineering and finance teams. Delivers command-line interface with core arithmetic functions (+, -, *, /, ^), floating point boundary precision up to 8 decimals, comprehensive error handling for division by zero and operand formatting, calculation history ledger, and 100% unit test coverage.",
    },
    {
      name: "Personal Website / Blog",
      prompt: "Modern developer portfolio and technical blog built with Astro, TypeScript, and TailwindCSS. Supports responsive dark/light themes, MDX blog post publishing with syntax highlighting, tag-based navigation, OpenGraph social previews, RSS feed generation, and sub-second First Contentful Paint with zero layout shift.",
    },
    {
      name: "Checkout Preset",
      prompt: "Autonomous checkout and order processing service: Validates order transaction payloads with unique idempotency keys, supports exponential retry (max 3 retries) on payment gateway timeouts, dual-writes all transactions to a SHA-256 tamper-evident ledger, and broadcasts real-time order status updates via SSE.",
    },
  ];

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Top Specification Synthesizer Card */}
      <div className="glass-panel p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600/10 border border-indigo-500/20 text-indigo-500 flex items-center justify-center">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-bold text-slate-900 dark:text-slate-100 text-base">
                Greenfield Requirements Studio (BRD / PRD)
              </h2>
              <p className="text-xs text-slate-600 dark:text-slate-400">
                Business Requirements Definition, Reviewer Agent Scoring & Word (.docx) Export
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-semibold text-slate-500 mr-1">Presets:</span>
            {presets.map((p) => (
              <button
                key={p.name}
                onClick={() => setBaPrompt(p.prompt)}
                className="text-[11px] px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 text-slate-700 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 transition border border-slate-200 dark:border-slate-700/60 font-medium"
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
            Raw Business Requirements Prompt:
          </label>
          <textarea
            value={baPrompt}
            onChange={(e) => setBaPrompt(e.target.value)}
            placeholder="Paste raw business requirements or feature goals..."
            rows={4}
            className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-xl p-3 text-xs text-slate-800 dark:text-slate-200 outline-none focus:ring-2 focus:ring-indigo-500 font-mono leading-relaxed"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 pt-2">
          <button
            onClick={onGenerateBRD}
            disabled={docLoading}
            className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 py-2 rounded-lg flex items-center gap-1.5 transition shadow-sm disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            {docLoading ? "Synthesizing..." : "Generate Enterprise BRD"}
          </button>
          <button
            onClick={onGeneratePRD}
            disabled={docLoading}
            className="border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200 text-xs font-semibold px-4 py-2 rounded-lg flex items-center gap-1.5 transition disabled:opacity-50"
          >
            <FileCode className="w-3.5 h-3.5 text-indigo-400" />
            Generate Enterprise PRD
          </button>
        </div>
      </div>

      {/* Main Document & Reviewer Layout */}
      {activeDoc && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Document Content Pane (2 cols) */}
          <div className="lg:col-span-2 glass-panel p-6 space-y-6">
            <div className="flex flex-wrap items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800/80 gap-3">
              <div>
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 font-semibold">
                  {activeDoc.document_type || "BRD"} · Version {activeDoc.version || "1.0.0"}
                </span>
                <h3 className="font-bold text-slate-900 dark:text-slate-100 text-base mt-1">
                  {activeDoc.title}
                </h3>
                <div className="text-[11px] text-slate-500 mt-0.5 font-mono">
                  Author: {activeDoc.author} · Status: {activeDoc.status}
                </div>
              </div>

              {/* Real Word .docx and .md Downloads */}
              <div className="flex items-center gap-2">
                <a
                  href={`/api/projects/${currentProjectId}/ba/export-docx`}
                  download
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white flex items-center gap-1.5 transition shadow-sm"
                >
                  <FileDown className="w-3.5 h-3.5" />
                  Download .docx (Word)
                </a>
                <a
                  href={`/api/projects/${currentProjectId}/ba/export-md`}
                  download
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 flex items-center gap-1.5 transition"
                >
                  <Download className="w-3.5 h-3.5" />
                  .md
                </a>
              </div>
            </div>

            {/* Sections Walkthrough */}
            <div className="space-y-6 text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
              {(activeDoc.sections || []).map((sec: any) => (
                <div key={sec.section_id} className="space-y-2">
                  <h4 className="font-bold text-slate-900 dark:text-slate-100 text-sm flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
                    {sec.title}
                  </h4>
                  {sec.content && (
                    <div className="whitespace-pre-wrap font-sans text-xs bg-slate-50 dark:bg-slate-900/30 p-3 rounded-lg border border-slate-200 dark:border-slate-800/60">
                      {sec.content}
                    </div>
                  )}
                  {sec.table && (
                    <div className="overflow-x-auto">
                      <table className="doc-table">
                        <thead>
                          <tr>
                            {sec.table.headers.map((h: string) => (
                              <th key={h}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {sec.table.rows.map((row: string[], rIdx: number) => (
                            <tr key={rIdx}>
                              {row.map((cell: string, cIdx: number) => (
                                <td key={cIdx}>{cell}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {sec.rules && (
                    <div className="space-y-2">
                      <div className="font-semibold text-slate-800 dark:text-slate-200">
                        Functional Business Rules:
                      </div>
                      <div className="space-y-2">
                        {sec.rules.map((r: any) => (
                          <div
                            key={r.rule_id}
                            className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 space-y-1"
                          >
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-bold text-indigo-400 text-xs">
                                {r.rule_id}
                              </span>
                              <span className="font-semibold text-slate-800 dark:text-slate-200">
                                {r.rule_title}
                              </span>
                            </div>
                            <p className="text-slate-600 dark:text-slate-400 text-xs">
                              {r.rule_statement}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Reviewer Agent Audit Pane (1 col) */}
          <div className="glass-panel p-6 space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800/80">
              <div className="flex items-center gap-2">
                <FileCheck2 className="w-5 h-5 text-indigo-400" />
                <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm">
                  Document Reviewer Agent
                </h3>
              </div>
              <button
                onClick={onReviewDocument}
                className="text-xs px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition flex items-center gap-1 shadow-sm"
              >
                <Sparkles className="w-3 h-3" />
                Run Audit
              </button>
            </div>

            {docReview ? (
              <div className="space-y-4">
                {/* Score Banner */}
                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 text-center space-y-1">
                  <div className="text-3xl font-extrabold text-indigo-400 font-mono">
                    {docReview.total_score} / 100
                  </div>
                  <div className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Verdict:{" "}
                    <span
                      className={
                        docReview.verdict === "APPROVED"
                          ? "text-emerald-400 font-bold"
                          : "text-amber-400 font-bold"
                      }
                    >
                      {docReview.verdict}
                    </span>
                  </div>
                </div>

                {/* Score Breakdown Bars */}
                {docReview.scores && (
                  <div className="space-y-2 text-xs">
                    <span className="font-semibold text-slate-400 block">Quality Dimensions:</span>
                    {Object.entries(docReview.scores).map(([k, v]: [string, any]) => (
                      <div key={k} className="space-y-0.5">
                        <div className="flex justify-between text-[11px] text-slate-400 font-mono">
                          <span>{k}</span>
                          <span>{v}/20</span>
                        </div>
                        <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
                          <div
                            className="bg-indigo-500 h-full rounded-full"
                            style={{ width: `${(v / 20) * 100}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Critiques */}
                {docReview.critiques && docReview.critiques.length > 0 && (
                  <div className="space-y-2 text-xs">
                    <span className="font-semibold text-slate-400 block">Actionable Feedback:</span>
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {docReview.critiques.map((c: any, i: number) => (
                        <div
                          key={i}
                          className="p-2.5 rounded border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40 space-y-1 text-[11px]"
                        >
                          <div className="font-semibold text-amber-400">
                            {c.section || "General"} ({c.severity || "info"})
                          </div>
                          <div className="text-slate-700 dark:text-slate-300">
                            {c.issue || JSON.stringify(c)}
                          </div>
                          {c.recommendation && (
                            <div className="text-slate-500 text-[10px] italic">
                              Recommendation: {c.recommendation}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 1-Click Refine */}
                <button
                  onClick={onRefineDocument}
                  className="w-full bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold py-2.5 rounded-xl transition flex items-center justify-center gap-2 shadow-md shadow-indigo-600/20"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Refine Document with Recommendations
                </button>
              </div>
            ) : (
              <div className="py-12 text-center text-xs text-slate-500 space-y-2">
                <FileCheck2 className="w-8 h-8 mx-auto text-slate-600" />
                <p>Click &quot;Run Audit&quot; to invoke the autonomous Document Reviewer Agent.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
