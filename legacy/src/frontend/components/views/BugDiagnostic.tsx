"use client";

import React from "react";
import { Bug, Sparkles, CheckCircle2, ShieldAlert } from "lucide-react";

interface BugFinding {
  id: string;
  title: string;
  severity: "High" | "Medium" | "Low";
  file: string;
  line: number;
  category: string;
}

interface BugDiagnosticProps {
  onScanCodebase: () => void;
  scanning: boolean;
  bugFindings: BugFinding[];
  onAutoFixBug: (bugId: string) => void;
  fixingBugId: string | null;
  bugPatch: any;
}

export function BugDiagnostic({
  onScanCodebase,
  scanning,
  bugFindings,
  onAutoFixBug,
  fixingBugId,
  bugPatch,
}: BugDiagnosticProps) {
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Bug Scanner (2 cols) */}
        <div className="lg:col-span-2 glass-panel p-6 space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800/80">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
                <Bug className="w-5 h-5" />
              </div>
              <div>
                <h2 className="font-bold text-slate-900 dark:text-slate-100 text-base">
                  Repository Bug & Vulnerability Scan
                </h2>
                <p className="text-xs text-slate-600 dark:text-slate-400">
                  AST inspections for missing error handlers, unclosed resources, and secret leaks
                </p>
              </div>
            </div>

            <button
              onClick={onScanCodebase}
              disabled={scanning}
              className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 py-2 rounded-lg flex items-center gap-1.5 transition shadow-sm disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {scanning ? "Scanning Codebase..." : "Scan Codebase"}
            </button>
          </div>

          {bugFindings.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500 space-y-2">
              <ShieldAlert className="w-8 h-8 mx-auto text-slate-600" />
              <p>Click &quot;Scan Codebase&quot; to execute static AST security &amp; reliability diagnostics.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {bugFindings.map((b) => (
                <div
                  key={b.id}
                  className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/60 flex items-center justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-xs text-indigo-400">{b.id}</span>
                      <span className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                        {b.title}
                      </span>
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                          b.severity === "High"
                            ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                            : b.severity === "Medium"
                            ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                            : "bg-slate-700 text-slate-300"
                        }`}
                      >
                        {b.severity}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono">
                      {b.file}:{b.line} · Category: {b.category}
                    </div>
                  </div>

                  <button
                    onClick={() => onAutoFixBug(b.id)}
                    disabled={fixingBugId === b.id}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition disabled:opacity-50 shrink-0 shadow-sm"
                  >
                    {fixingBugId === b.id ? "Fixing..." : "Auto-Fix"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Verified Regression Patch */}
        <div className="glass-panel p-6 space-y-4">
          <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm pb-3 border-b border-slate-200 dark:border-slate-800/80">
            Verified Regression Patch
          </h3>

          {bugPatch ? (
            <div className="space-y-3">
              <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-800/80 rounded-xl space-y-1">
                <div className="font-bold text-xs text-emerald-400 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4" />
                  Regression Test Created:
                </div>
                <div className="text-[11px] text-slate-700 dark:text-slate-300 font-mono">
                  {bugPatch.test_file || "tests/test_regression_bug_01.py"}
                </div>
              </div>

              <div className="space-y-1.5">
                <span className="text-xs font-semibold text-slate-400">Patch Diff:</span>
                <div className="terminal-scroll text-xs">
                  {bugPatch.diff ||
                    `--- a/app/order_service.py
+++ b/app/order_service.py
@@ -41,3 +41,5 @@
+  if not payload:
+      raise ValueError('Payload must be a non-empty dictionary')
   item_id = str(payload.get('id'))`}
                </div>
              </div>
            </div>
          ) : (
            <div className="py-12 text-center text-xs text-slate-500 space-y-2">
              <CheckCircle2 className="w-8 h-8 mx-auto text-slate-600" />
              <p>Click &quot;Auto-Fix&quot; on any bug to generate regression tests and verify the AST patch.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
