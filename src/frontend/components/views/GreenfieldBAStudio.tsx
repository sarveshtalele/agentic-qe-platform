"use client";

import React, { useState, useEffect } from "react";
import {
  FileText,
  Sparkles,
  Download,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  FileCheck2,
  FileDown,
  FileCode,
  Edit3,
  Eye,
  Save,
  Plus,
  Trash2,
  History,
  Terminal,
  Layers,
  Copy,
  Check,
} from "lucide-react";

interface GreenfieldBAStudioProps {
  baPrompt: string;
  setBaPrompt: (val: string) => void;
  onGenerateBRD: () => void;
  onGeneratePRD: () => void;
  docLoading: boolean;
  activeDoc: any;
  docReview: any;
  onReviewDocument: () => void;
  onRefineDocument: () => void;
  currentProjectId: string;
  onSaveDocument?: (doc: any) => Promise<void>;
  docSaving?: boolean;
  docVersions?: any[];
  onLoadVersion?: (v: any) => void;
}

export function GreenfieldBAStudio({
  baPrompt,
  setBaPrompt,
  onGenerateBRD,
  onGeneratePRD,
  docLoading,
  activeDoc,
  docReview,
  onReviewDocument,
  onRefineDocument,
  currentProjectId,
  onSaveDocument,
  docSaving = false,
  docVersions = [],
  onLoadVersion,
}: GreenfieldBAStudioProps) {
  const [docFormat, setDocFormat] = useState<"sections" | "gherkin" | "markdown" | "versions">("sections");
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editedDoc, setEditedDoc] = useState<any>(null);
  const [editedGherkin, setEditedGherkin] = useState<string>("");
  const [copiedGherkin, setCopiedGherkin] = useState<boolean>(false);

  useEffect(() => {
    if (activeDoc) {
      setEditedDoc(JSON.parse(JSON.stringify(activeDoc)));
      setEditedGherkin(activeDoc.gherkin || "");
    }
  }, [activeDoc]);

  const presets = [
    {
      name: "Calculator App",
      prompt:
        "Python-based high-precision calculator application to replace manual calculation processes across engineering and finance teams. Delivers command-line interface with core arithmetic functions (+, -, *, /, ^), floating point boundary precision up to 8 decimals, comprehensive error handling for division by zero and operand formatting, calculation history ledger, and 100% unit test coverage.",
    },
    {
      name: "Personal Website / Blog",
      prompt:
        "Modern developer portfolio and technical blog built with Astro, TypeScript, and TailwindCSS. Supports responsive dark/light themes, MDX blog post publishing with syntax highlighting, tag-based navigation, OpenGraph social previews, RSS feed generation, and sub-second First Contentful Paint with zero layout shift.",
    },
    {
      name: "Checkout Preset",
      prompt:
        "Autonomous checkout and order processing service: Validates order transaction payloads with unique idempotency keys, supports exponential retry (max 3 retries) on payment gateway timeouts, dual-writes all transactions to a SHA-256 tamper-evident ledger, and broadcasts real-time order status updates via SSE.",
    },
  ];

  const handleSave = async () => {
    if (!onSaveDocument || !editedDoc) return;
    const docToSave = {
      ...editedDoc,
      gherkin: editedGherkin,
    };
    await onSaveDocument(docToSave);
    setIsEditing(false);
  };

  const handleUpdateSectionContent = (secIdx: number, newContent: string) => {
    if (!editedDoc) return;
    const next = { ...editedDoc };
    next.sections[secIdx].content = newContent;
    setEditedDoc(next);
  };

  const handleUpdateTableCell = (secIdx: number, rowIdx: number, colIdx: number, val: string) => {
    if (!editedDoc) return;
    const next = { ...editedDoc };
    next.sections[secIdx].table.rows[rowIdx][colIdx] = val;
    setEditedDoc(next);
  };

  const handleAddTableRow = (secIdx: number) => {
    if (!editedDoc) return;
    const next = { ...editedDoc };
    const headers = next.sections[secIdx].table.headers || [];
    const newRow = headers.map((_: any, i: number) => (i === 0 ? `BR-00${next.sections[secIdx].table.rows.length + 1}` : "New business constraint"));
    next.sections[secIdx].table.rows.push(newRow);
    setEditedDoc(next);
  };

  const handleDeleteTableRow = (secIdx: number, rowIdx: number) => {
    if (!editedDoc) return;
    const next = { ...editedDoc };
    next.sections[secIdx].table.rows.splice(rowIdx, 1);
    setEditedDoc(next);
  };

  const handleCopyGherkin = () => {
    const text = isEditing ? editedGherkin : (activeDoc?.gherkin || editedGherkin);
    navigator.clipboard.writeText(text);
    setCopiedGherkin(true);
    setTimeout(() => setCopiedGherkin(false), 2000);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Top Specification Synthesizer Card */}
      <div className="glass-panel p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600/10 border border-indigo-500/20 text-indigo-500 flex items-center justify-center">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-bold text-slate-900 dark:text-slate-100 text-base">
                Greenfield Requirements Studio (BRD / PRD &amp; Gherkin BDD)
              </h2>
              <p className="text-xs text-slate-600 dark:text-slate-400">
                Business Requirements Definition, Gherkin Scenarios, Reviewer Agent Scoring &amp; Multi-Format Export
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-semibold text-slate-500 mr-1">Presets:</span>
            {presets.map((p) => (
              <button
                key={p.name}
                onClick={() => setBaPrompt(p.prompt)}
                className="text-[11px] px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 text-slate-700 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 transition border border-slate-200 dark:border-slate-700/60 font-medium"
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
            Raw Business Requirements Prompt:
          </label>
          <textarea
            value={baPrompt}
            onChange={(e) => setBaPrompt(e.target.value)}
            placeholder="Paste raw business requirements or feature goals..."
            rows={3}
            className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-xl p-3 text-xs text-slate-800 dark:text-slate-200 outline-none focus:ring-2 focus:ring-indigo-500 font-mono leading-relaxed"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 pt-1">
          <button
            onClick={onGenerateBRD}
            disabled={docLoading}
            className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 py-2 rounded-lg flex items-center gap-1.5 transition shadow-sm disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            {docLoading ? "Synthesizing..." : "Generate Enterprise BRD"}
          </button>
          <button
            onClick={onGeneratePRD}
            disabled={docLoading}
            className="border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200 text-xs font-semibold px-4 py-2 rounded-lg flex items-center gap-1.5 transition disabled:opacity-50"
          >
            <FileCode className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400" />
            Generate Enterprise PRD
          </button>
        </div>
      </div>

      {/* Main Document & Reviewer Layout */}
      {activeDoc && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Document Content Pane (2 cols) */}
          <div className="lg:col-span-2 glass-panel p-6 space-y-6">
            {/* Header with Title and Format Tabs */}
            <div className="space-y-4 pb-4 border-b border-slate-200 dark:border-slate-800/80">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 border border-indigo-500/30 font-semibold">
                      {activeDoc.document_type || "BRD"} · Version {isEditing ? editedDoc?.version : activeDoc.version || "1.0.0"}
                    </span>
                    {activeDoc.status && (
                      <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 font-semibold">
                        {activeDoc.status}
                      </span>
                    )}
                  </div>
                  {isEditing ? (
                    <input
                      type="text"
                      value={editedDoc?.title || ""}
                      onChange={(e) => setEditedDoc({ ...editedDoc, title: e.target.value })}
                      className="font-bold text-slate-900 dark:text-slate-100 text-base mt-1.5 bg-white dark:bg-slate-900 border border-indigo-500 rounded px-2.5 py-1 w-full outline-none"
                    />
                  ) : (
                    <h3 className="font-bold text-slate-900 dark:text-slate-100 text-base mt-1">
                      {activeDoc.title}
                    </h3>
                  )}
                  <div className="text-[11px] text-slate-500 mt-0.5 font-mono">
                    Author: {activeDoc.author} · Project: {activeDoc.project_name || currentProjectId}
                  </div>
                </div>

                {/* Edit & Save Action Buttons */}
                <div className="flex flex-wrap items-center gap-2">
                  {isEditing ? (
                    <>
                      <button
                        onClick={handleSave}
                        disabled={docSaving}
                        className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white flex items-center gap-1.5 transition shadow-sm disabled:opacity-50"
                      >
                        <Save className="w-3.5 h-3.5" />
                        {docSaving ? "Saving Version..." : "Save & Version"}
                      </button>
                      <button
                        onClick={() => {
                          setEditedDoc(JSON.parse(JSON.stringify(activeDoc)));
                          setEditedGherkin(activeDoc.gherkin || "");
                          setIsEditing(false);
                        }}
                        className="px-2.5 py-1.5 rounded-lg text-xs font-semibold border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition"
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => setIsEditing(true)}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-indigo-500/40 bg-indigo-50 dark:bg-indigo-950/30 hover:bg-indigo-100 dark:hover:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 flex items-center gap-1.5 transition shadow-sm"
                    >
                      <Edit3 className="w-3.5 h-3.5 text-indigo-500" />
                      Edit Document
                    </button>
                  )}
                </div>
              </div>

              {/* View / Format Switcher Tabs */}
              <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100 dark:border-slate-800/60">
                <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-900/80 p-1 rounded-xl border border-slate-200 dark:border-slate-800 text-xs">
                  <button
                    onClick={() => setDocFormat("sections")}
                    className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition ${
                      docFormat === "sections"
                        ? "bg-white dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 shadow-sm"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    <Layers className="w-3.5 h-3.5" />
                    Structured Sections
                  </button>
                  <button
                    onClick={() => setDocFormat("gherkin")}
                    className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition ${
                      docFormat === "gherkin"
                        ? "bg-white dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 shadow-sm"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    <Terminal className="w-3.5 h-3.5" />
                    Gherkin BDD (.feature)
                  </button>
                  <button
                    onClick={() => setDocFormat("markdown")}
                    className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition ${
                      docFormat === "markdown"
                        ? "bg-white dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 shadow-sm"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    <FileCode className="w-3.5 h-3.5" />
                    Markdown (.md)
                  </button>
                  <button
                    onClick={() => setDocFormat("versions")}
                    className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition ${
                      docFormat === "versions"
                        ? "bg-white dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 shadow-sm"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    <History className="w-3.5 h-3.5" />
                    Versions ({docVersions.length})
                  </button>
                </div>

                {/* Real Downloads: Word .docx, Markdown .md, Gherkin .feature */}
                <div className="flex flex-wrap items-center gap-1.5">
                  <a
                    href={`/api/projects/${currentProjectId}/ba/export-docx`}
                    download
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white flex items-center gap-1.5 transition shadow-sm"
                    title="Download Microsoft Word .docx format"
                  >
                    <FileDown className="w-3.5 h-3.5" />
                    Download .docx (Word)
                  </a>
                  <a
                    href={`/api/projects/${currentProjectId}/ba/export-md`}
                    download
                    className="px-2.5 py-1.5 rounded-lg text-xs font-semibold border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 flex items-center gap-1 transition"
                    title="Download GitHub Flavored Markdown"
                  >
                    <Download className="w-3.5 h-3.5" />
                    .md
                  </a>
                  <a
                    href={`/api/projects/${currentProjectId}/ba/export-feature`}
                    download
                    className="px-2.5 py-1.5 rounded-lg text-xs font-semibold border border-emerald-500/40 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100 dark:hover:bg-emerald-900/40 flex items-center gap-1 transition"
                    title="Download Executable Gherkin Feature file"
                  >
                    <Terminal className="w-3.5 h-3.5 text-emerald-500" />
                    .feature
                  </a>
                </div>
              </div>
            </div>

            {/* TAB 1: Structured Sections (View & Edit Mode) */}
            {docFormat === "sections" && (
              <div className="space-y-6 text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                {(isEditing ? editedDoc?.sections || [] : activeDoc.sections || []).map((sec: any, secIdx: number) => (
                  <div key={sec.section_id || secIdx} className="space-y-2">
                    <h4 className="font-bold text-slate-900 dark:text-slate-100 text-sm flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
                      {sec.title}
                    </h4>

                    {/* Content Section */}
                    {sec.content && (
                      isEditing ? (
                        <textarea
                          rows={4}
                          value={sec.content}
                          onChange={(e) => handleUpdateSectionContent(secIdx, e.target.value)}
                          className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg p-3 text-xs text-slate-800 dark:text-slate-200 font-sans leading-relaxed outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                      ) : (
                        <div className="whitespace-pre-wrap font-sans text-xs bg-slate-50 dark:bg-slate-900/30 p-3 rounded-lg border border-slate-200 dark:border-slate-800/60">
                          {sec.content}
                        </div>
                      )
                    )}

                    {/* Table Section */}
                    {sec.table && (
                      <div className="space-y-2">
                        <div className="overflow-x-auto">
                          <table className="doc-table">
                            <thead>
                              <tr>
                                {sec.table.headers.map((h: string) => (
                                  <th key={h}>{h}</th>
                                ))}
                                {isEditing && <th className="w-12 text-center">Action</th>}
                              </tr>
                            </thead>
                            <tbody>
                              {sec.table.rows.map((row: string[], rIdx: number) => (
                                <tr key={rIdx}>
                                  {row.map((cell: string, cIdx: number) => (
                                    <td key={cIdx}>
                                      {isEditing ? (
                                        <input
                                          type="text"
                                          value={cell}
                                          onChange={(e) => handleUpdateTableCell(secIdx, rIdx, cIdx, e.target.value)}
                                          className="w-full bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded px-2 py-1 text-xs text-slate-900 dark:text-slate-100 outline-none focus:ring-1 focus:ring-indigo-500"
                                        />
                                      ) : (
                                        cell
                                      )}
                                    </td>
                                  ))}
                                  {isEditing && (
                                    <td className="text-center">
                                      <button
                                        onClick={() => handleDeleteTableRow(secIdx, rIdx)}
                                        className="text-rose-500 hover:text-rose-400 p-1 rounded"
                                        title="Delete rule"
                                      >
                                        <Trash2 className="w-3.5 h-3.5" />
                                      </button>
                                    </td>
                                  )}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>

                        {isEditing && (
                          <button
                            onClick={() => handleAddTableRow(secIdx)}
                            className="text-xs px-3 py-1.5 rounded-lg border border-indigo-500/30 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/30 font-semibold flex items-center gap-1.5 transition"
                          >
                            <Plus className="w-3.5 h-3.5" />
                            Add Row to {sec.title}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* TAB 2: Gherkin BDD Feature View & Editor */}
            {docFormat === "gherkin" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-emerald-500" />
                    <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                      Executable Gherkin BDD Specification (.feature)
                    </span>
                  </div>
                  <button
                    onClick={handleCopyGherkin}
                    className="text-xs px-2.5 py-1 rounded border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 flex items-center gap-1 transition"
                  >
                    {copiedGherkin ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    {copiedGherkin ? "Copied!" : "Copy Gherkin"}
                  </button>
                </div>

                {isEditing ? (
                  <textarea
                    rows={22}
                    value={editedGherkin}
                    onChange={(e) => setEditedGherkin(e.target.value)}
                    className="w-full terminal-scroll font-mono text-xs outline-none focus:ring-2 focus:ring-indigo-500"
                    placeholder="Feature: ...&#10;  Scenario: ...&#10;    Given ...&#10;    When ...&#10;    Then ..."
                  />
                ) : (
                  <div className="terminal-scroll font-mono text-xs whitespace-pre-wrap leading-relaxed">
                    {activeDoc.gherkin || editedGherkin}
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: Raw Markdown View */}
            {docFormat === "markdown" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileCode className="w-4 h-4 text-indigo-400" />
                    <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                      Clean GitHub Flavored Markdown Export
                    </span>
                  </div>
                </div>
                <div className="terminal-scroll font-mono text-xs whitespace-pre-wrap leading-relaxed">
                  {`# ${activeDoc.title}\n\n**Project:** ${activeDoc.project_name || currentProjectId}\n**Version:** ${activeDoc.version || "1.0.0"} | **Status:** ${activeDoc.status || "DRAFT"}\n**Author:** ${activeDoc.author || "Business Analyst"}\n\n---\n\n` +
                    (activeDoc.sections || [])
                      .map((s: any) => `## ${s.title}\n\n${s.content || ""}`)
                      .join("\n\n")}
                </div>
              </div>
            )}

            {/* TAB 4: Saved Document Versions */}
            {docFormat === "versions" && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <History className="w-4 h-4 text-indigo-400" />
                    <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                      Project Document Versions &amp; Cryptographic SHA-256 Ledger
                    </span>
                  </div>
                </div>

                {docVersions.length === 0 ? (
                  <div className="text-center py-10 text-xs text-slate-500 space-y-2">
                    <History className="w-8 h-8 mx-auto text-slate-400" />
                    <p>No historical versions recorded yet.</p>
                    <p className="text-[11px] text-slate-400">Click &apos;Edit Document&apos; and then &apos;Save &amp; Version&apos; to create persistent immutable versions.</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="doc-table">
                      <thead>
                        <tr>
                          <th>Version</th>
                          <th>Filename</th>
                          <th>Status</th>
                          <th>SHA-256 Digest</th>
                          <th>Timestamp</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {docVersions.map((v: any) => (
                          <tr key={v.id}>
                            <td className="font-mono font-bold text-indigo-600 dark:text-indigo-400">{v.version}</td>
                            <td className="font-mono text-[11px]">{v.filename}</td>
                            <td>
                              <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                                {v.status}
                              </span>
                            </td>
                            <td className="font-mono text-[11px] text-slate-500" title={v.full_sha256}>
                              {v.sha256}
                            </td>
                            <td className="text-[11px] text-slate-500">{new Date(v.created_at).toLocaleString()}</td>
                            <td>
                              <a
                                href={`/api/projects/${currentProjectId}/ba/export-docx`}
                                download
                                className="text-[11px] text-indigo-600 dark:text-indigo-400 hover:underline font-semibold"
                              >
                                Download .docx
                              </a>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Reviewer Agent Audit Pane (1 col) */}
          <div className="glass-panel p-6 space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800/80">
              <div className="flex items-center gap-2">
                <FileCheck2 className="w-5 h-5 text-indigo-500 dark:text-indigo-400" />
                <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm">
                  Document Reviewer Agent
                </h3>
              </div>
              <button
                onClick={onReviewDocument}
                className="text-xs px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition flex items-center gap-1 shadow-sm"
              >
                <Sparkles className="w-3 h-3" />
                Run Audit
              </button>
            </div>

            {docReview ? (
              <div className="space-y-4">
                {/* Score Banner */}
                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900/80 border border-slate-200 dark:border-slate-800 text-center space-y-1">
                  <div className="text-3xl font-extrabold text-indigo-600 dark:text-indigo-400 font-mono">
                    {docReview.total_score} / 100
                  </div>
                  <div className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Verdict:{" "}
                    <span
                      className={
                        docReview.verdict === "APPROVED"
                          ? "text-emerald-500 dark:text-emerald-400 font-bold"
                          : "text-amber-500 dark:text-amber-400 font-bold"
                      }
                    >
                      {docReview.verdict}
                    </span>
                  </div>
                </div>

                {/* Dimension Breakdown */}
                {docReview.scores && (
                  <div className="space-y-2 text-xs">
                    <span className="font-semibold text-slate-600 dark:text-slate-400 block">Quality Dimensions:</span>
                    {Object.entries(docReview.scores).map(([k, v]: [string, any]) => (
                      <div key={k} className="space-y-0.5">
                        <div className="flex justify-between text-[11px] text-slate-600 dark:text-slate-400 font-mono">
                          <span>{k}</span>
                          <span>{v}/20</span>
                        </div>
                        <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
                          <div
                            className="bg-indigo-500 h-full rounded-full"
                            style={{ width: `${(v / 20) * 100}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Critiques */}
                {docReview.critiques && docReview.critiques.length > 0 && (
                  <div className="space-y-2 text-xs">
                    <span className="font-semibold text-slate-600 dark:text-slate-400 block">Actionable Feedback:</span>
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {docReview.critiques.map((c: any, i: number) => (
                        <div
                          key={i}
                          className="p-2.5 rounded border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40 space-y-1 text-[11px]"
                        >
                          <div className="font-semibold text-amber-500 dark:text-amber-400">
                            {c.section || "General"} ({c.severity || "info"})
                          </div>
                          <div className="text-slate-700 dark:text-slate-300">
                            {c.issue || JSON.stringify(c)}
                          </div>
                          {c.recommendation && (
                            <div className="text-slate-500 text-[10px] italic">
                              Recommendation: {c.recommendation}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 1-Click Refine */}
                <button
                  onClick={onRefineDocument}
                  className="w-full bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold py-2.5 rounded-xl transition flex items-center justify-center gap-2 shadow-md shadow-indigo-600/20"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Refine Document with Recommendations
                </button>
              </div>
            ) : (
              <div className="py-12 text-center text-xs text-slate-500 space-y-2">
                <FileCheck2 className="w-8 h-8 mx-auto text-slate-600" />
                <p>Click &quot;Run Audit&quot; to invoke the autonomous Document Reviewer Agent.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
