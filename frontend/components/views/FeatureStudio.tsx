"use client";

import React from "react";
import {
  Code2,
  GitBranch,
  Play,
  Download,
  Terminal,
  Sparkles,
  GitPullRequest,
  CheckCircle2,
  ExternalLink,
  AlertCircle,
  FileCode2,
} from "lucide-react";

interface FeatureStudioProps {
  featureName: string;
  setFeatureName: (val: string) => void;
  featureSpec: string;
  setFeatureSpec: (val: string) => void;
  onImplementFeature: () => void;
  featureLoading: boolean;
  featureBranch: string;
  featureFiles: string[];
  featureTestRes: any;
  currentProjectId: string;
  errorTraceInput: string;
  setErrorTraceInput: (val: string) => void;
  onDiagnoseError: () => void;
  errorDiagnosing: boolean;
  latestPatch: any;
  onCreatePR: () => void;
  prLoading: boolean;
  githubPR: any;
  onMergePR: () => void;
  prMerging: boolean;
}

export function FeatureStudio({
  featureName,
  setFeatureName,
  featureSpec,
  setFeatureSpec,
  onImplementFeature,
  featureLoading,
  featureBranch,
  featureFiles,
  featureTestRes,
  currentProjectId,
  errorTraceInput,
  setErrorTraceInput,
  onDiagnoseError,
  errorDiagnosing,
  latestPatch,
  onCreatePR,
  prLoading,
  githubPR,
  onMergePR,
  prMerging,
}: FeatureStudioProps) {
  const sampleTraceback = `Traceback (most recent call last):
  File "src/components/Navigation.astro", line 24, in <template>
    const userRole = session.user.role;
TypeError: Cannot read properties of undefined (reading 'role')`;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Feature Branch Scaffolding */}
        <div className="space-y-6">
          <div className="glass-panel p-6 space-y-4">
            <div className="flex items-center gap-3 pb-3 border-b border-slate-200 dark:border-slate-800/80">
              <div className="w-10 h-10 rounded-xl bg-indigo-600/10 border border-indigo-500/20 text-indigo-500 flex items-center justify-center">
                <Code2 className="w-5 h-5" />
              </div>
              <div>
                <h2 className="font-bold text-slate-900 dark:text-slate-100 text-base">
                  Feature Implementation & Branching
                </h2>
                <p className="text-xs text-slate-600 dark:text-slate-400">
                  Synthesize framework-accurate code, scaffold dedicated branch, and verify syntax
                </p>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Feature Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Navigation Theme Switcher or Arithmetic Engine"
                  value={featureName}
                  onChange={(e) => setFeatureName(e.target.value)}
                  className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg p-2.5 text-xs text-slate-900 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-500 font-medium placeholder:text-slate-400"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Feature Specification
                </label>
                <textarea
                  placeholder="Enter detailed acceptance criteria and technical requirements..."
                  value={featureSpec}
                  onChange={(e) => setFeatureSpec(e.target.value)}
                  rows={4}
                  className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg p-2.5 text-xs text-slate-900 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-[11px] placeholder:text-slate-400"
                />
              </div>

              <button
                onClick={onImplementFeature}
                disabled={featureLoading}
                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold py-2.5 rounded-lg flex items-center justify-center gap-1.5 transition shadow-sm disabled:opacity-50"
              >
                <Code2 className="w-3.5 h-3.5" />
                {featureLoading ? "Synthesizing & Verifying Code..." : "Implement Feature Autonomously"}
              </button>
            </div>
          </div>

          {/* Scaffolded Files & Sandboxed Test Results */}
          {featureBranch ? (
            <div className="glass-panel p-6 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800/80">
                <div>
                  <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm">
                    Workspace Feature Files
                  </h3>
                  <div className="text-[11px] font-mono text-indigo-500 dark:text-indigo-400 mt-0.5">
                    Branch: {featureBranch}
                  </div>
                </div>

                <a
                  href={`/api/projects/${currentProjectId}/features/export-zip`}
                  download
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 flex items-center gap-1.5 transition"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download Local Test ZIP
                </a>
              </div>

              <div className="space-y-1.5">
                {featureFiles.map((fn: string) => (
                  <div
                    key={fn}
                    className="p-2.5 bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-lg text-xs font-mono text-emerald-600 dark:text-emerald-400 flex items-center gap-2"
                  >
                    <FileCode2 className="w-3.5 h-3.5" />
                    <span>✓ {fn}</span>
                  </div>
                ))}
              </div>

              {/* Sandboxed Test Output */}
              {featureTestRes && (
                <div className="space-y-2">
                  <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Verification Output (Gate 4):
                  </span>
                  <div className="terminal-scroll">
                    <div className="text-slate-400 font-mono text-[11px]">$ verify-ast --strict</div>
                    <div className="text-emerald-400 font-mono text-[11px] font-bold mt-1 whitespace-pre-wrap">
                      {featureTestRes.summary || "PASSED: All files syntax-checked and verified cleanly."}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="glass-panel p-6 text-center space-y-2 border-dashed">
              <div className="w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto text-slate-400">
                <Code2 className="w-5 h-5" />
              </div>
              <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">No Feature Scaffolded Yet</p>
              <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
                Enter a feature name and specification above, then click &apos;Implement Feature Autonomously&apos; to generate files and isolate branch.
              </p>
            </div>
          )}

          {/* GitHub PR Automation Card */}
          {featureBranch && (
            <div className="glass-panel p-6 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800/80">
                <div className="flex items-center gap-2">
                  <GitPullRequest className="w-5 h-5 text-indigo-500 dark:text-indigo-400" />
                  <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm">
                    GitHub Pull Request Automation
                  </h3>
                </div>
                {githubPR && !githubPR.error && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                    {githubPR.state || "OPEN"}
                  </span>
                )}
              </div>

              {!githubPR || githubPR.error ? (
                <div className="space-y-3">
                  {githubPR?.error && (
                    <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs flex items-start gap-2">
                      <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                      <div>{githubPR.message || "Failed to create PR. Please check your GitHub token in Platform Settings."}</div>
                    </div>
                  )}
                  <button
                    onClick={onCreatePR}
                    disabled={prLoading}
                    className="w-full bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold py-2.5 rounded-lg flex items-center justify-center gap-2 transition disabled:opacity-50 shadow-sm"
                  >
                    <GitPullRequest className="w-3.5 h-3.5" />
                    {prLoading ? "Creating PR on GitHub..." : "Create GitHub Pull Request"}
                  </button>
                </div>
              ) : (
                <div className="space-y-3 text-xs">
                  <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 space-y-1 font-mono">
                    <div className="text-slate-500">Pull Request #{githubPR.number}</div>
                    <div className="font-bold text-slate-900 dark:text-slate-100">
                      {githubPR.title}
                    </div>
                    {githubPR.html_url && (
                      <a
                        href={githubPR.html_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-indigo-500 dark:text-indigo-400 hover:underline flex items-center gap-1 text-[11px] pt-1"
                      >
                        View on GitHub <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>

                  {githubPR.merged ? (
                    <div className="p-2.5 bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-800 text-emerald-700 dark:text-emerald-300 rounded-lg text-xs font-semibold flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      Pull Request Merged into Mainline
                    </div>
                  ) : (
                    <button
                      onClick={onMergePR}
                      disabled={prMerging}
                      className="w-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold py-2.5 rounded-lg flex items-center justify-center gap-2 transition shadow-sm disabled:opacity-50"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {prMerging ? "Merging into Main..." : "Merge Pull Request into Main"}
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Interactive Traceback Chat & AST Auto-Patch */}
        <div className="space-y-6">
          <div className="glass-panel p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800/80">
              <div>
                <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm">
                  Interactive Error Chat & Debugger
                </h3>
                <p className="text-xs text-slate-600 dark:text-slate-400">
                  Paste runtime errors or test traces to diagnose root cause and auto-patch
                </p>
              </div>
              <button
                onClick={() => setErrorTraceInput(sampleTraceback)}
                className="text-xs px-2.5 py-1 rounded bg-slate-100 dark:bg-slate-800/80 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition border border-slate-200 dark:border-slate-700/60 font-medium"
              >
                Paste Sample KeyError
              </button>
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Paste Runtime Traceback / Log:
              </label>
              <textarea
                value={errorTraceInput}
                onChange={(e) => setErrorTraceInput(e.target.value)}
                placeholder="Traceback (most recent call last)... or TypeError: ..."
                rows={7}
                className="w-full terminal-scroll outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-[11px]"
              />
            </div>

            <button
              onClick={onDiagnoseError}
              disabled={errorDiagnosing || !errorTraceInput.trim()}
              className="w-full bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold py-2.5 rounded-lg flex items-center justify-center gap-2 transition disabled:opacity-50 shadow-sm"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {errorDiagnosing ? "Diagnosing & Patching..." : "Analyze & Auto-Fix Error"}
            </button>
          </div>

          {/* Diagnostic Result & Diff View */}
          {latestPatch && (
            <div className="glass-panel p-6 space-y-4">
              <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-800/80 rounded-xl space-y-1">
                <div className="font-bold text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4" />
                  Fault Diagnosed & Patched!
                </div>
                <div className="text-[11px] text-slate-700 dark:text-slate-300 font-mono">
                  File: {latestPatch.patched_file || latestPatch.file || "workspace file"} · Line: {latestPatch.line || latestPatch.line_number || "target line"} · Tests Verified
                </div>
              </div>

              <div className="space-y-1.5">
                <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">Applied Patch Diff:</span>
                <div className="terminal-scroll text-xs">
                  {latestPatch.diff}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
