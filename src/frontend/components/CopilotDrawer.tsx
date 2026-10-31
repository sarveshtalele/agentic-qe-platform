"use client";

import React, { useState } from "react";
import { Sparkles, X, Send } from "lucide-react";

interface CopilotMessage {
  sender: string;
  text: string;
  time: string;
}

interface CopilotDrawerProps {
  open: boolean;
  onClose: () => void;
  messages: CopilotMessage[];
  onSendMessage: (text: string) => void;
}

export function CopilotDrawer({ open, onClose, messages, onSendMessage }: CopilotDrawerProps) {
  const [inputText, setInputText] = useState("");

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    onSendMessage(inputText.trim());
    setInputText("");
  };

  return (
    <div className="fixed inset-y-0 right-0 w-96 z-40 flex flex-col shadow-2xl border-l bg-white dark:bg-[#070d1f] border-slate-200 dark:border-slate-800">
      <div className="p-4 border-b flex items-center justify-between border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-indigo-400" />
          <h3 className="font-bold text-xs uppercase tracking-wider text-slate-900 dark:text-slate-100">
            CopilotKit / AG-UI Live Stream
          </h3>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-900 dark:hover:text-white"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 p-4 overflow-y-auto space-y-3">
        {messages.map((m, idx) => (
          <div key={idx} className="space-y-1 text-xs">
            <div className="text-[10px] text-slate-500 font-mono uppercase">{m.sender}</div>
            <div
              className={`p-2.5 rounded-lg border leading-relaxed ${
                m.sender === "USER" || m.sender === "OPERATOR"
                  ? "bg-slate-100 dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-200"
                  : "bg-indigo-50 dark:bg-indigo-950/40 border-indigo-800/40 border-indigo-200 text-indigo-900 dark:text-indigo-200"
              }`}
            >
              {m.text}
            </div>
          </div>
        ))}
      </div>

      <form
        onSubmit={handleSubmit}
        className="p-3 border-t flex items-center gap-2 border-slate-200 dark:border-slate-800"
      >
        <input
          type="text"
          placeholder="Direct agents..."
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          className="flex-1 border text-xs rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500 bg-slate-50 dark:bg-slate-900 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100"
        />
        <button
          type="submit"
          className="bg-indigo-600 hover:bg-indigo-500 text-white p-2 rounded-lg transition"
          aria-label="Send directive"
        >
          <Send className="w-4 h-4 lucide-send" />
        </button>
      </form>
    </div>
  );
}
