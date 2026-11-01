"use client";

import React, { useState } from "react";
import {
  Sparkles,
  Send,
  ShieldCheck,
  Bug,
  Code2,
  Terminal,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Bot,
  User,
  Copy,
  Check,
} from "lucide-react";

interface ChatMessage {
  sender: string;
  text: string;
  time: string;
  action?: string;
  data?: any;
}

interface InteractiveCopilotViewProps {
  currentProjectId: string;
  currentProjectName?: string;
  messages: ChatMessage[];
  onSendMessage: (text: string) => Promise<void>;
  loading: boolean;
}

export function InteractiveCopilotView({
  currentProjectId,
  currentProjectName,
  messages,
  onSendMessage,
  loading,
}: InteractiveCopilotViewProps) {
  const [inputText, setInputText] = useState("");
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  const quickCommands = [
    { label: "🔍 Scan Repo", command: "/scan", desc: "AST anti-pattern scan" },
    { label: "🛠️ Fix Bug", command: "/fix BUG-01", desc: "Synthesize unified diff" },
    { label: "🧪 Run Pytest", command: "/test", desc: "Isolated sandbox run" },
    { label: "🛡️ Verify Ledger", command: "/verify", desc: "SHA-256 cryptographic proof" },
    { label: "🚦 Quality Gates", command: "/gates", desc: "G0-G5 status check" },
  ];

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputText.trim() || loading) return;
    const msg = inputText.trim();
    setInputText("");
    await onSendMessage(msg);
  };

  const handleQuickCommand = async (cmd: string) => {
    if (loading) return;
    await onSendMessage(cmd);
  };

  const handleCopy = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      {/* Header Banner */}
      <div className="glass-panel p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600/10 border border-indigo-500/20 text-indigo-500 flex items-center justify-center shadow-sm">
            <Sparkles className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-bold text-slate-900 dark:text-slate-100 text-base">
                Centralized Autonomous Copilot
              </h2>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 font-semibold">
                Online
              </span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400">
              Interactive SDLC pair-programmer powered by Microsoft Agent Framework (MAF)
            </p>
          </div>
        </div>

        <div className="text-xs font-mono px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300">
          Workspace: <span className="font-bold text-indigo-600 dark:text-indigo-400">{currentProjectName || currentProjectId || "GLOBAL"}</span>
        </div>
      </div>

      {/* Quick Action Directives */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 mr-1">
          Quick Actions:
        </span>
        {quickCommands.map((q) => (
          <button
            key={q.command}
            onClick={() => handleQuickCommand(q.command)}
            disabled={loading}
            className="text-xs px-3 py-1.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-indigo-500/50 hover:bg-indigo-50/50 dark:hover:bg-indigo-950/40 text-slate-800 dark:text-slate-200 transition shadow-sm flex items-center gap-1.5 disabled:opacity-50"
            title={q.desc}
          >
            <span>{q.label}</span>
          </button>
        ))}
      </div>

      {/* Chat Thread Panel */}
      <div className="glass-panel p-4 flex flex-col h-[560px]">
        <div className="flex-1 overflow-y-auto space-y-4 pr-1">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-500">
                <Bot className="w-6 h-6" />
              </div>
              <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100">
                How can I assist your Quality Engineering workflow?
              </h3>
              <p className="text-xs text-slate-500 max-w-md">
                Ask architectural questions, trigger repository AST scans with <code className="font-mono text-indigo-500">/scan</code>, execute sandboxed tests with <code className="font-mono text-indigo-500">/test</code>, or verify SHA-256 audit ledger with <code className="font-mono text-indigo-500">/verify</code>.
              </p>
            </div>
          ) : (
            messages.map((m, idx) => {
              const isUser = m.sender === "USER" || m.sender === "OPERATOR";
              return (
                <div
                  key={idx}
                  className={`flex gap-3 text-xs leading-relaxed ${
                    isUser ? "justify-end" : "justify-start"
                  }`}
                >
                  {!isUser && (
                    <div className="w-7 h-7 rounded-lg bg-indigo-600/10 border border-indigo-500/30 text-indigo-600 dark:text-indigo-400 flex items-center justify-center shrink-0 mt-0.5 font-bold">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}

                  <div className={`max-w-[80%] space-y-1.5 ${isUser ? "items-end" : "items-start"}`}>
                    <div className="flex items-center gap-2 px-1">
                      <span className="text-[10px] font-mono uppercase font-semibold text-slate-500">
                        {m.sender}
                      </span>
                      <span className="text-[10px] text-slate-400">{m.time}</span>
                    </div>

                    <div
                      className={`p-3.5 rounded-2xl border shadow-sm relative group ${
                        isUser
                          ? "bg-indigo-600 text-white border-indigo-600 rounded-tr-none"
                          : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-800 dark:text-slate-200 rounded-tl-none whitespace-pre-wrap font-sans"
                      }`}
                    >
                      <div>{m.text}</div>

                      {!isUser && (
                        <button
                          onClick={() => handleCopy(m.text, idx)}
                          className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                          title="Copy response"
                        >
                          {copiedIdx === idx ? (
                            <Check className="w-3.5 h-3.5 text-emerald-500" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>
                      )}
                    </div>
                  </div>

                  {isUser && (
                    <div className="w-7 h-7 rounded-lg bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 flex items-center justify-center shrink-0 mt-0.5 font-bold">
                      <User className="w-4 h-4" />
                    </div>
                  )}
                </div>
              );
            })
          )}
          {loading && (
            <div className="flex items-center gap-2 text-xs text-indigo-500 font-mono p-3 bg-indigo-50/50 dark:bg-indigo-950/20 rounded-xl border border-indigo-200 dark:border-indigo-900/50">
              <Sparkles className="w-4 h-4 animate-spin" />
              <span>Copilot is reasoning and coordinating agents...</span>
            </div>
          )}
        </div>

        {/* Input Bar */}
        <form
          onSubmit={handleSend}
          className="pt-3 border-t border-slate-200 dark:border-slate-800 flex items-center gap-2"
        >
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Type directive (e.g. /scan, /fix, /test, /verify, /feature, or ask a question)..."
            className="flex-1 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-xl px-4 py-2.5 text-xs text-slate-900 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
          />
          <button
            type="submit"
            disabled={loading || !inputText.trim()}
            className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs flex items-center gap-1.5 transition disabled:opacity-50 shadow-sm"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Send</span>
          </button>
        </form>
      </div>
    </div>
  );
}
