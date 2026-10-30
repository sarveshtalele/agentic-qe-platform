"use client";

import React, { useState } from "react";
import { ShieldCheck, CheckCircle2, XCircle, Clock, X } from "lucide-react";

export interface Gate {
  gate_number: number;
  name: string;
  control_id: string;
  status: string;
  decision_by?: string;
  decision_reason?: string;
  decision_timestamp?: string;
}

interface QualityGateRibbonProps {
  gates: Gate[];
  onGateDecision: (gateNumber: number, approved: boolean, reason: string) => void;
}

export function QualityGateRibbon({ gates, onGateDecision }: QualityGateRibbonProps) {
  const [activeModalGate, setActiveModalGate] = useState<Gate | null>(null);
  const [decisionReason, setDecisionReason] = useState("");

  if (!gates || gates.length === 0) return null;

  return (
    <>
      <div className="border-b px-6 py-2.5 flex items-center gap-2 overflow-x-auto text-xs bg-[#070d1f]/80 dark:bg-[#070d1f]/80 bg-slate-100/90 border-slate-200 dark:border-slate-800/80">
        <span className="font-semibold text-slate-600 dark:text-slate-400 mr-1 shrink-0 flex items-center gap-1.5 font-mono text-[11px]">
          <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
          Quality Gates:
        </span>
        {gates.map((g) => {
          const approved = g.status === "APPROVED";
          const rejected = g.status === "REJECTED";
          return (
            <button
              key={g.gate_number}
              onClick={() => {
                setActiveModalGate(g);
                setDecisionReason(g.decision_reason || "");
              }}
              className={`px-3 py-1 rounded-full font-semibold flex items-center gap-1.5 transition shrink-0 text-xs border ${
                approved
                  ? "bg-emerald-50 dark:bg-emerald-950/60 text-emerald-400 dark:text-emerald-300 text-emerald-700 border-emerald-800/80 border-emerald-300"
                  : rejected
                  ? "bg-rose-50 dark:bg-rose-950/60 text-rose-400 dark:text-rose-300 text-rose-700 border-rose-800/80 border-rose-300"
                  : "bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-800 hover:border-indigo-500"
              }`}
              title={`${g.name} - ${g.status}`}
            >
              {approved ? (
                <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              ) : rejected ? (
                <XCircle className="w-3 h-3 text-rose-400" />
              ) : (
                <Clock className="w-3 h-3 text-slate-400" />
              )}
              <span>
                G{g.gate_number}: {g.name.split(" ")[0]}
              </span>
            </button>
          );
        })}
      </div>

      {/* Gate Inspection & Decision Modal */}
      {activeModalGate && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0b1329] dark:bg-[#0b1329] bg-white border border-slate-200 dark:border-slate-800 rounded-2xl p-6 max-w-lg w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800/80">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-indigo-400" />
                <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm">
                  Quality Gate G{activeModalGate.gate_number} Inspection
                </h3>
              </div>
              <button
                onClick={() => setActiveModalGate(null)}
                className="text-slate-400 hover:text-slate-900 dark:hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Stage Name:</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  {activeModalGate.name}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Control ID:</span>
                <span className="font-mono text-indigo-400">{activeModalGate.control_id}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Current Status:</span>
                <span
                  className={`font-semibold px-2 py-0.5 rounded text-[11px] ${
                    activeModalGate.status === "APPROVED"
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                      : activeModalGate.status === "REJECTED"
                      ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                      : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                  }`}
                >
                  {activeModalGate.status}
                </span>
              </div>

              <div className="pt-2">
                <label className="block text-slate-400 mb-1">Human Decision Reason & Notes:</label>
                <textarea
                  value={decisionReason}
                  onChange={(e) => setDecisionReason(e.target.value)}
                  placeholder="State review criteria, test evidence, or reason for decision..."
                  className="w-full bg-[#070d1f] dark:bg-[#070d1f] bg-slate-50 border border-slate-300 dark:border-slate-700 rounded-lg p-2.5 text-xs text-slate-900 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-500"
                  rows={3}
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-800/80">
              <button
                onClick={() => {
                  onGateDecision(activeModalGate.gate_number, false, decisionReason);
                  setActiveModalGate(null);
                }}
                className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-rose-600/20 text-rose-300 border border-rose-600/30 hover:bg-rose-600/30 transition"
              >
                Reject Gate
              </button>
              <button
                onClick={() => {
                  onGateDecision(activeModalGate.gate_number, true, decisionReason);
                  setActiveModalGate(null);
                }}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition shadow-sm"
              >
                Approve Gate
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
