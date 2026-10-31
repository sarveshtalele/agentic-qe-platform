"use client";

import React from "react";
import {
  FolderGit2,
  FileText,
  Code2,
  Bug,
  ShieldCheck,
  Lock,
  Activity,
  Settings,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  activeView: string;
  onSelectView: (view: string) => void;
  currentProject: any;
}

export function Sidebar({
  collapsed,
  onToggleCollapse,
  activeView,
  onSelectView,
  currentProject,
}: SidebarProps) {
  const navItems = [
    { id: "home", label: "Repository Hub", icon: FolderGit2, badge: "Repo" },
    { id: "ba_studio", label: "Greenfield BA Studio", icon: FileText, badge: "Spec" },
    { id: "feature_studio", label: "Feature Builder", icon: Code2, badge: "Code" },
    { id: "bug_studio", label: "Bug Diagnostic", icon: Bug, badge: "Fix" },
    { id: "testing_hub", label: "QE Test Studio", icon: ShieldCheck, badge: "ISTQB" },
    { id: "governance", label: "HITL Governance", icon: Lock, badge: "Gates" },
    { id: "observability", label: "Observability & MAF", icon: Activity, badge: "Traces" },
    { id: "settings", label: "Platform Settings", icon: Settings, badge: "LLM" },
  ];

  return (
    <aside
      className={`border-r flex flex-col transition-all duration-200 sticky top-0 h-screen select-none z-30 ${
        collapsed ? "w-16 p-2 items-center" : "w-60 p-4"
      } bg-white dark:bg-[#060a17] border-slate-200 dark:border-slate-800/80`}
    >
      {/* Brand & Collapse Header */}
      <div className="flex items-center justify-between pb-5 border-b border-slate-200 dark:border-slate-800/80 mb-3 w-full">
        <div className="flex items-center gap-2.5 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white font-bold flex items-center justify-center shrink-0 shadow-lg shadow-indigo-600/30">
            <ShieldCheck className="w-4 h-4" />
          </div>
          {!collapsed && (
            <div>
              <div className="font-bold text-sm tracking-tight text-slate-900 dark:text-white flex items-center gap-1.5">
                Agentic QE
                <span className="text-[9px] uppercase px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 font-mono">
                  MAF
                </span>
              </div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400 tracking-wider uppercase font-semibold">
                Platform
              </div>
            </div>
          )}
        </div>
        <button
          onClick={onToggleCollapse}
          className="w-7 h-7 rounded-md border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800/80 flex items-center justify-center text-slate-400 hover:text-slate-900 dark:hover:text-white transition shrink-0"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation Categories */}
      <div className="space-y-1 flex-1 overflow-y-auto w-full">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectView(item.id)}
              title={collapsed ? item.label : undefined}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-semibold transition ${
                active
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-100 dark:hover:text-white hover:text-slate-900 hover:bg-slate-100 dark:hover:bg-slate-900/60"
              } ${collapsed ? "justify-center px-0" : ""}`}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {!collapsed && <span className="flex-1 text-left">{item.label}</span>}
            </button>
          );
        })}
      </div>

      {/* Active Project Footer Card */}
      {!collapsed && (
        <div className="pt-3 border-t border-slate-200 dark:border-slate-800/80 w-full">
          {currentProject ? (
            <div className="p-2.5 bg-slate-50 dark:bg-slate-900/80 rounded-lg border border-slate-200 dark:border-slate-800 text-[11px]">
              <div className="text-slate-500 font-medium">Active Workspace</div>
              <div className="font-semibold text-slate-900 dark:text-white truncate mt-0.5">
                {currentProject.name}
              </div>
              <div className="text-slate-500 font-mono text-[10px] mt-0.5">{currentProject.id}</div>
            </div>
          ) : (
            <div className="p-2.5 bg-slate-50 dark:bg-slate-900/40 rounded-lg border border-dashed border-slate-200 dark:border-slate-800 text-[11px] text-center text-slate-500">
              No active workspace
            </div>
          )}
          <div className="mt-2 text-[10px] text-slate-500 flex items-center gap-1.5 px-1 font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block animate-pulse" />
            <span>SQLite & Audit Ledger Online</span>
          </div>
        </div>
      )}
    </aside>
  );
}
