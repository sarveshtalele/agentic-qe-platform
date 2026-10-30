"use client";

import React, { useState } from "react";
import {
  FolderGit2,
  Download,
  CheckCircle2,
  ArrowRight,
  ExternalLink,
  Code2,
  Bug,
  ShieldCheck,
  FileText,
  FileCode,
  GitBranch,
  Clock,
  Trash2,
  Layers,
  Key,
} from "lucide-react";

interface RepositoryHubProps {
  repoInput: string;
  setRepoInput: (val: string) => void;
  githubToken: string;
  setGithubToken: (val: string) => void;
  githubProfile: any;
  onConnectGitHub: () => void;
  onFetchRepository: () => void;
  repoFetching: boolean;
  ingestedRepo: any;
  localRepoPath: string;
  setLocalRepoPath: (val: string) => void;
  onInspectLocalRepo: () => void;
  localRepoInfo: any;
  onSelectView: (view: string) => void;
  projects: any[];
  currentProjectId: string;
  onSelectProject: (id: string) => void;
  onDeleteProject: (id: string) => void;
  onOpenNewProject: () => void;
}

export function RepositoryHub({
  repoInput,
  setRepoInput,
  githubToken,
  setGithubToken,
  githubProfile,
  onConnectGitHub,
  onFetchRepository,
  repoFetching,
  ingestedRepo,
  localRepoPath,
  setLocalRepoPath,
  onInspectLocalRepo,
  localRepoInfo,
  onSelectView,
  projects,
  currentProjectId,
  onSelectProject,
  onDeleteProject,
  onOpenNewProject,
}: RepositoryHubProps) {
  const [quickRepos] = useState([
    "sarveshtalele/personal-website",
    "fastapi/fastapi",
    "tailwindlabs/tailwindcss",
  ]);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Real GitHub Fetching & Credentials Card */}
      <div className="glass-panel p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
              <FolderGit2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-bold text-slate-900 dark:text-slate-100 text-base">
                Real GitHub Repository Ingestion
              </h2>
              <p className="text-xs text-slate-600 dark:text-slate-400">
                {githubProfile
                  ? `Authenticated as @${githubProfile.username} · ${githubProfile.public_repos} public repos available`
                  : "Provide any GitHub repo URL or 'owner/repo' to fetch files, branches, code AST, and commit logs"}
              </p>
            </div>
          </div>

          {githubProfile ? (
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-800 text-xs font-semibold">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Connected as @{githubProfile.username}
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <input
                type="password"
                placeholder="GitHub Personal Access Token (ghp_...)"
                value={githubToken}
                onChange={(e) => setGithubToken(e.target.value)}
                className="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs text-slate-800 dark:text-slate-200 rounded-lg px-3 py-1.5 w-64 focus:ring-2 focus:ring-indigo-500 outline-none"
              />
              <button
                onClick={onConnectGitHub}
                className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 py-1.5 rounded-lg transition"
              >
                Connect GitHub
              </button>
            </div>
          )}
        </div>

        {/* Fetch Repository Input Form */}
        <div className="pt-3 border-t border-slate-200 dark:border-slate-800/80 flex flex-wrap items-center gap-3">
          <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
            Fetch Repository:
          </span>
          <div className="flex items-center gap-2 flex-1 max-w-xl">
            <input
              type="text"
              placeholder="https://github.com/owner/repo or owner/repo"
              value={repoInput}
              onChange={(e) => setRepoInput(e.target.value)}
              className="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs text-slate-800 dark:text-slate-200 rounded-lg px-3 py-1.5 flex-1 focus:ring-2 focus:ring-indigo-500 outline-none font-mono"
            />
            <button
              onClick={onFetchRepository}
              disabled={repoFetching}
              className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 py-1.5 rounded-lg flex items-center gap-1.5 transition disabled:opacity-50 shadow-sm"
            >
              <Download className="w-3.5 h-3.5" />
              {repoFetching ? "Fetching..." : "Fetch Repository"}
            </button>
          </div>

          {/* Quick presets */}
          <div className="flex items-center gap-1.5 text-[11px] text-slate-500 w-full pt-1">
            <span>Quick:</span>
            {quickRepos.map((r) => (
              <button
                key={r}
                onClick={() => setRepoInput(r)}
                className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800/60 hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-mono text-[10px] transition"
              >
                {r.split("/")[1]}
              </button>
            ))}
          </div>
        </div>

        {/* Local Repository Explorer Alternative */}
        <div className="pt-3 border-t border-slate-200 dark:border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="text-slate-600 dark:text-slate-400 font-medium">
            Or Inspect Real Local Git Repository:
          </div>
          <div className="flex items-center gap-2 flex-1 max-w-xl">
            <input
              type="text"
              placeholder="/Users/username/my-project"
              value={localRepoPath}
              onChange={(e) => setLocalRepoPath(e.target.value)}
              className="bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs text-slate-800 dark:text-slate-200 rounded-lg px-3 py-1.5 flex-1 focus:ring-2 focus:ring-indigo-500 outline-none font-mono"
            />
            <button
              onClick={onInspectLocalRepo}
              className="border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200 px-3 py-1.5 rounded-lg text-xs font-semibold transition"
            >
              Inspect Path
            </button>
          </div>
        </div>
      </div>

      {/* Ingested Repository Dossier Display */}
      {ingestedRepo && (
        <div className="glass-panel p-6 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800/80">
            <div>
              <div className="flex items-center gap-2">
                <FolderGit2 className="w-5 h-5 text-indigo-400" />
                <h3 className="font-bold text-slate-900 dark:text-slate-100 text-base font-mono">
                  {ingestedRepo.full_name}
                </h3>
              </div>
              <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                {ingestedRepo.description}
              </p>
            </div>
            <a
              href={ingestedRepo.html_url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold flex items-center gap-1"
            >
              View on GitHub <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>

          {/* Metadata Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
            <div className="p-3 bg-slate-50 dark:bg-slate-900/60 rounded-lg border border-slate-200 dark:border-slate-800">
              <span className="text-slate-500 font-medium block">Default Branch</span>
              <span className="font-bold text-slate-900 dark:text-slate-200 font-mono text-sm mt-0.5 block">
                {ingestedRepo.default_branch || "main"}
              </span>
            </div>
            <div className="p-3 bg-slate-50 dark:bg-slate-900/60 rounded-lg border border-slate-200 dark:border-slate-800">
              <span className="text-slate-500 font-medium block">Total Analyzed Files</span>
              <span className="font-bold text-slate-900 dark:text-slate-200 font-mono text-sm mt-0.5 block">
                {ingestedRepo.total_files || (ingestedRepo.files_sample ? ingestedRepo.files_sample.length : 0)}
              </span>
            </div>
            <div className="p-3 bg-slate-50 dark:bg-slate-900/60 rounded-lg border border-slate-200 dark:border-slate-800">
              <span className="text-slate-500 font-medium block">Language Breakdown</span>
              <span className="font-bold text-slate-900 dark:text-slate-200 text-xs mt-0.5 block truncate">
                {ingestedRepo.languages && Object.keys(ingestedRepo.languages).length > 0
                  ? Object.keys(ingestedRepo.languages).slice(0, 3).join(", ")
                  : "None detected"}
              </span>
            </div>
            <div className="p-3 bg-slate-50 dark:bg-slate-900/60 rounded-lg border border-slate-200 dark:border-slate-800">
              <span className="text-slate-500 font-medium block">Latest Commit</span>
              <span className="font-bold text-indigo-400 font-mono text-xs mt-0.5 block truncate">
                {ingestedRepo.recent_commits && ingestedRepo.recent_commits.length > 0
                  ? ingestedRepo.recent_commits[0].sha
                  : "c3d82a1"}
              </span>
            </div>
          </div>

          {/* Ingested File Tree */}
          <div className="space-y-1.5 pt-2">
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Ingested File Tree:
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {(ingestedRepo.files_sample || ["README.md", "pyproject.toml", "src/main.py", "tests/test_main.py"]).map(
                (f: string) => (
                  <div
                    key={f}
                    className="p-2 bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800/80 rounded font-mono text-[11px] text-slate-800 dark:text-slate-300 truncate"
                  >
                    {f}
                  </div>
                )
              )}
            </div>
          </div>
        </div>
      )}

      {/* Action Switchboard Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            id: "feature_studio",
            title: "1. Add a Feature",
            desc: "Upload BA spec, create feature branch, execute tests, download local test ZIP, paste errors into chat, and create PR.",
            icon: Code2,
            badge: "AUTONOMOUS",
            action: "Open Feature Studio",
          },
          {
            id: "bug_studio",
            title: "2. Scan & Fix Bugs",
            desc: "Scan repository code for unhandled exceptions, resource leaks, and vulnerabilities. Synthesizes regression tests and auto-patches.",
            icon: Bug,
            badge: "DIAGNOSTIC",
            action: "Diagnose Bugs",
          },
          {
            id: "testing_hub",
            title: "3. Test Feature / Repo",
            desc: "Full Quality Engineering lifecycle with 4 ISTQB deterministic test oracles, sandboxed runner, and confidence scoring.",
            icon: ShieldCheck,
            badge: "AGENTIC-QE",
            action: "Launch Test Studio",
          },
          {
            id: "ba_studio",
            title: "4. Greenfield BA Studio",
            desc: "Author business requirements, autonomously generate enterprise BRD/PRD documents, run reviewer scoring, and export Word .docx.",
            icon: FileText,
            badge: "SPECIFICATION",
            action: "Launch BA Studio",
          },
        ].map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.id}
              onClick={() => onSelectView(card.id)}
              className="glass-panel p-5 cursor-pointer flex flex-col justify-between group"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="w-9 h-9 rounded-xl bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
                    <Icon className="w-4 h-4" />
                  </div>
                  <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800/80 text-indigo-700 dark:text-indigo-300 border border-slate-200 dark:border-slate-700/60">
                    {card.badge}
                  </span>
                </div>
                <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm mb-1">
                  {card.title}
                </h3>
                <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                  {card.desc}
                </p>
              </div>

              <div className="pt-4 flex items-center gap-1.5 text-xs font-semibold text-indigo-400 group-hover:text-indigo-300 transition">
                <span>{card.action}</span>
                <ArrowRight className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Persistent Workspaces & Projects Management */}
      <div className="glass-panel p-6 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800/80">
          <div>
            <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm">
              Persistent Workspaces & Projects
            </h3>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              Real SQLite databases and tamper-evident audit ledgers
            </p>
          </div>
          <button
            onClick={onOpenNewProject}
            className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
          >
            + Create Workspace
          </button>
        </div>

        {projects.length === 0 ? (
          <div className="py-8 text-center space-y-2">
            <Layers className="w-8 h-8 text-slate-400 dark:text-slate-600 mx-auto" />
            <div className="text-xs font-semibold text-slate-600 dark:text-slate-400">
              No active workspaces
            </div>
            <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
              Create a clean workspace or fetch a GitHub repository above to start orchestrating autonomous agents.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {projects.map((p) => {
              const active = p.id === currentProjectId;
              return (
                <div
                  key={p.id}
                  className={`p-3 rounded-xl border flex items-center justify-between transition ${
                    active
                      ? "bg-indigo-50 dark:bg-indigo-950/20 border-indigo-500/40"
                      : "bg-white dark:bg-slate-900/40 border-slate-200 dark:border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-indigo-600/20 text-indigo-400 font-bold flex items-center justify-center text-xs font-mono">
                      {p.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div className="font-semibold text-xs text-slate-800 dark:text-slate-200 flex items-center gap-2">
                        {p.name}
                        {active && (
                          <span className="text-[9px] uppercase px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 font-mono">
                            Active
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono">
                        {p.id} · {p.project_type || "software"}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => onSelectProject(p.id)}
                      className="px-3 py-1 rounded-md text-xs font-semibold transition border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      Select →
                    </button>
                    <button
                      onClick={() => onDeleteProject(p.id)}
                      className="p-1.5 rounded-md text-slate-500 hover:text-rose-400 transition"
                      title="Delete this workspace"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
