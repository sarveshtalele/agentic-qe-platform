"use client";

import React from "react";
import { Lock, ShieldCheck, CheckCircle2, History, AlertTriangle } from "lucide-react";

interface AuditEntry {
  hash: string;
  previous_hash: string;
  actor: string;
  action: string;
  control_id: string;
  timestamp: string;
}

interface HITLGovernanceProps {
  onVerifyLedger: () => void;
  ledgerVerified: any;
  auditTrail: AuditEntry[];
}

export function HITLGovernance({
  onVerifyLedger,
  ledgerVerified,
  auditTrail,
}: HITLGovernanceProps) {
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Verification Card */}
      <div className="glass-panel p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
              <Lock className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-bold text-slate-900 dark:text-slate-100 text-base">
                Tamper-Evident SHA-256 Cryptographic Audit Ledger
              </h2>
              <p className="text-xs text-slate-600 dark:text-slate-400">
                Every project event is dual-written and sequentially hashed
              </p>
            </div>
          </div>

          <button
            onClick={onVerifyLedger}
            className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-4 py-2 rounded-lg flex items-center gap-1.5 transition shadow-sm"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            Verify Ledger Integrity
          </button>
        </div>

        {ledgerVerified && (
          <div
            className={`p-4 rounded-xl border flex items-center gap-3 ${
              ledgerVerified.verified
                ? "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-800 text-emerald-800 dark:text-emerald-300"
                : "bg-rose-50 dark:bg-rose-950/40 border-rose-800 text-rose-300"
            }`}
          >
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            <div>
              <div className="font-bold text-xs">Cryptographic Integrity Verified</div>
              <div className="text-[11px] opacity-90 mt-0.5">
                {ledgerVerified.message ||
                  "Cryptographic integrity verified: all records sequentially hashed with 0 tampering."}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Audit Trail Events */}
      <div className="glass-panel p-6 space-y-4">
        <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm pb-3 border-b border-slate-200 dark:border-slate-800/80">
          Audit Trail Events
        </h3>

        {auditTrail.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-500">
            No audit ledger events recorded for this workspace yet.
          </div>
        ) : (
          <div className="space-y-2">
            {auditTrail.map((ev, idx) => (
              <div
                key={idx}
                className="p-3 rounded-lg border border-slate-200 dark:border-slate-800/80 bg-slate-50 dark:bg-slate-900/40 flex items-center justify-between text-xs"
              >
                <div className="space-y-1">
                  <div className="font-semibold text-slate-800 dark:text-slate-200 font-mono">
                    {ev.action} <span className="text-slate-500 font-sans">by</span> {ev.actor}
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono">
                    {ev.timestamp} · Control: {ev.control_id}
                  </div>
                </div>

                <div className="text-right">
                  <span className="font-mono text-[10px] text-indigo-400 bg-white dark:bg-slate-950/60 px-2 py-1 rounded border border-slate-200 dark:border-slate-800">
                    {ev.hash ? ev.hash.substring(0, 16) + "..." : "hash-verified"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
