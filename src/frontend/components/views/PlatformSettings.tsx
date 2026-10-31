"use client";

import React from "react";
import { Settings, Cpu, Key, CheckCircle2, AlertTriangle, Radio } from "lucide-react";

interface PlatformSettingsProps {
  customBaseUrl: string;
  setCustomBaseUrl: (val: string) => void;
  customModel: string;
  setCustomModel: (val: string) => void;
  customApiKey: string;
  setCustomApiKey: (val: string) => void;
  githubToken: string;
  setGithubToken: (val: string) => void;
  onSaveSettings: () => void;
  onTestConnection: () => void;
  testingConnection: boolean;
  settingsStatus: any;
}

export function PlatformSettings({
  customBaseUrl,
  setCustomBaseUrl,
  customModel,
  setCustomModel,
  customApiKey,
  setCustomApiKey,
  githubToken,
  setGithubToken,
  onSaveSettings,
  onTestConnection,
  testingConnection,
  settingsStatus,
}: PlatformSettingsProps) {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="glass-panel p-6 space-y-6">
        <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800/80">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
              <Settings className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-bold text-slate-900 dark:text-slate-100 text-base">
                Platform Settings &amp; Custom LLM Configuration
              </h2>
              <p className="text-xs text-slate-600 dark:text-slate-400">
                Configure your custom LLM Base URL, API Key, and Model Name for all MAF agents
              </p>
            </div>
          </div>

          <div className="px-2.5 py-1 rounded bg-slate-100 dark:bg-slate-800/80 border border-slate-300 dark:border-slate-700/60 text-xs font-mono font-semibold text-indigo-600 dark:text-indigo-400">
            Active: {customModel || "deepseek-v4-flash-global"}
          </div>
        </div>

        <div className="space-y-4">
          <h3 className="font-bold text-xs uppercase tracking-wider text-slate-400">
            Custom LLM Configuration
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Custom Base URL
              </label>
              <input
                type="text"
                value={customBaseUrl}
                onChange={(e) => setCustomBaseUrl(e.target.value)}
                placeholder="https://api.openai.com/v1"
                className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg p-2.5 text-xs text-slate-900 dark:text-slate-100 font-mono outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <span className="text-[10px] text-slate-500 block">
                Supports LiteLLM Azure proxy, OpenAI, Azure OpenAI, OpenRouter, vLLM, Ollama, Anthropic
              </span>
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Model Name
              </label>
              <input
                type="text"
                value={customModel}
                onChange={(e) => setCustomModel(e.target.value)}
                placeholder="gpt-4o, claude-3-5-sonnet, deepseek-v4-flash-global"
                className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg p-2.5 text-xs text-slate-900 dark:text-slate-100 font-mono outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <span className="text-[10px] text-slate-500 block">
                Exact model identifier passed to the inference endpoint
              </span>
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Custom API Key
              </label>
              <input
                type="password"
                value={customApiKey}
                onChange={(e) => setCustomApiKey(e.target.value)}
                placeholder="sk-..."
                className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg p-2.5 text-xs text-slate-900 dark:text-slate-100 font-mono outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <span className="text-[10px] text-slate-500 block">
                Key is securely stored in local platform configuration
              </span>
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                GitHub Personal Access Token
              </label>
              <input
                type="password"
                value={githubToken}
                onChange={(e) => setGithubToken(e.target.value)}
                placeholder="ghp_..."
                className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg p-2.5 text-xs text-slate-900 dark:text-slate-100 font-mono outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <span className="text-[10px] text-slate-500 block">
                Used for private repository cloning, branch listing, and Pull Request creation
              </span>
            </div>
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-slate-200 dark:border-slate-800/80">
            <button
              onClick={onTestConnection}
              disabled={testingConnection}
              className="border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-100 text-xs font-semibold px-4 py-2 rounded-lg flex items-center gap-2 transition disabled:opacity-50 shadow-sm"
            >
              <Radio className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              {testingConnection ? "Probing Endpoint..." : "Test Endpoint Connectivity"}
            </button>

            <button
              onClick={onSaveSettings}
              className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-5 py-2 rounded-lg flex items-center gap-1.5 transition shadow-sm"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              Save Settings
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
