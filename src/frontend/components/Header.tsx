"use client";

import React from "react";
import { Cpu, Plus, Sparkles } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { QualityGateRibbon, Gate } from "./QualityGateRibbon";

interface HeaderProps {
  activeView: string;
  settingsCustomModel: string;
  projects: any[];
  currentProjectId: string;
  onSelectProject: (id: string) => void;
  onOpenNewProject: () => void;
  copilotOpen: boolean;
  onToggleCopilot: () => void;
  onOpenSettings: () => void;
  gates: Gate[];
  onGateDecision: (gateNumber: number, approved: boolean, reason: string) => void;
  theme: "dark" | "light";
  onToggleTheme: () => void;
}

export function Header({
  activeView,
  settingsCustomModel,
  projects,
  currentProjectId,
  onSelectProject,
  onOpenNewProject,
  copilotOpen,
  onToggleCopilot,
  onOpenSettings,
  gates,
  onGateDecision,
  theme,
  onToggleTheme,
}: HeaderProps) {
  const viewTitles: Record<string, { title: string; subtitle: string }> = {
    home: {
      title: "Repository Hub & Brownfield Ingestion",
      subtitle: "Agentic QE Governed Platform",
    },
    ba_studio: {
      title: "Greenfield BA Document Studio (BRD / PRD)",
      subtitle: "Autonomous Specification & Reviewer Mesh",
    },
    feature_studio: {
      title: "Autonomous Feature Builder & Interactive Error Chat",
      subtitle: "Brownfield Scaffolding, Sandboxed Tests & Auto-Patch",
    },
    bug_studio: {
      title: "Codebase Bug Diagnostic & Regression Fixer",
      subtitle: "AST Static Analysis & Verified Regression Patching",
    },
    testing_hub: {
      title: "Quality Engineering & 4-Oracle Deterministic Test Studio",
      subtitle: "ISTQB Deterministic Oracles & Release Confidence Scoring",
    },
    governance: {
      title: "HITL Governance & SHA-256 Cryptographic Ledger",
      subtitle: "Non-Repudiation Audit & Sequential Hash Chain Proof",
    },
    observability: {
      title: "Multi-Agent Observability, Traces & Latency Metrics",
      subtitle: "Microsoft Agent Framework (MAF) Real-Time Mesh",
    },
    settings: {
      title: "Custom LLM & Platform Credentials Configuration",
      subtitle: "LiteLLM Azure Proxy & Endpoint Credentials",
    },
  };

  const currentInfo = viewTitles[activeView] || viewTitles.home;

  return (
    <div className="sticky top-0 z-20">
      <header className="h-16 px-6 flex items-center justify-between border-b bg-[#060a17]/90 dark:bg-[#060a17]/90 bg-white/95 backdrop-blur-md border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-4">
          <div>
            <div className="text-[10px] uppercase font-bold tracking-wider text-indigo-600 dark:text-indigo-400 font-mono">
              {currentInfo.subtitle}
            </div>
            <div className="font-bold text-slate-900 dark:text-slate-100 text-sm">
              {currentInfo.title}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Active Model Indicator Pill */}
          <button
            onClick={onOpenSettings}
            className="hidden md:flex items-center gap-1.5 text-[11px] px-2.5 py-1.5 rounded-lg transition border border-slate-300 dark:border-slate-800 bg-slate-100 dark:bg-slate-900 text-slate-700 dark:text-slate-300 hover:border-slate-400 dark:hover:border-slate-700 shadow-sm"
            title="Configured model: deepseek-v4-flash-global via LiteLLM Azure proxy"
          >
            <Cpu className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
            <span className="font-mono text-indigo-600 dark:text-indigo-400 font-semibold">
              {settingsCustomModel || "deepseek-v4-flash-global"}
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse ml-0.5" />
          </button>

          {/* Workspace Project Selector */}
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-600 dark:text-slate-400 font-medium">
              Project:
            </span>
            <select
              value={currentProjectId}
              onChange={(e) => onSelectProject(e.target.value)}
              className="border text-xs rounded-lg px-2.5 py-1.5 focus:ring-2 focus:ring-indigo-500 outline-none bg-white dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-slate-800 dark:text-slate-200 font-medium"
            >
              {projects.length === 0 ? (
                <option value="">(No workspaces created)</option>
              ) : (
                projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.id})
                  </option>
                ))
              )}
            </select>
          </div>

          {/* New Project Button */}
          <button
            onClick={onOpenNewProject}
            className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-3 py-1.5 rounded-lg flex items-center gap-1 shadow-sm transition"
          >
            <Plus className="w-3.5 h-3.5" />
            New Project
          </button>

          {/* Dark / Light Mode Switcher */}
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />

          {/* Copilot Stream Toggle */}
          <button
            onClick={onToggleCopilot}
            className="border text-xs font-semibold px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition border-slate-300 dark:border-slate-700 text-slate-800 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            Copilot Stream
          </button>
        </div>
      </header>

      {/* 6-Gate Ribbon */}
      <QualityGateRibbon gates={gates} onGateDecision={onGateDecision} />
    </div>
  );
}
