"use client";

import { ImagePlus, Plus, Table2, Trash2, Type } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Markdown } from "./ui";
import { upload } from "../lib/api";

type Block = { kind: "text" | "table"; raw: string; gap: string };

const SEPARATOR = /^\s*\|[\s:|-]+\|\s*$/;
const isRow = (line: string) => line.trimStart().startsWith("|");
const blank = (line: string) => !line.trim();
const splitRow = (line: string) => line.trim().replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/).map((cell) => cell.trim().replace(/\\\|/g, "|"));
const cell = (value: string) => value.replace(/\|/g, "\\|");

/** Splits a document into blocks. Each keeps its exact text, so an unedited block is saved unchanged. */
export function parseBlocks(content: string, gherkin: boolean): Block[] {
  const lines = content.split("\n");
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const start = i;
    let kind: Block["kind"] = "text";
    if (gherkin) {
      kind = isRow(lines[i]) ? "table" : "text";
      while (i < lines.length && isRow(lines[i]) === (kind === "table")) i++;
      blocks.push({ kind, raw: lines.slice(start, i).join("\n"), gap: i < lines.length ? "\n" : "" });
      continue;
    }
    if (blank(lines[i])) {
      i++;
      continue;
    }
    if (lines[i].startsWith("```")) {
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) i++;
      i = Math.min(i + 1, lines.length);
    } else if (isRow(lines[i]) && SEPARATOR.test(lines[i + 1] || "")) {
      kind = "table";
      while (i < lines.length && isRow(lines[i])) i++;
    } else if (/^#{1,6}\s/.test(lines[i])) {
      i++;
    } else {
      i++;
      while (i < lines.length && !blank(lines[i]) && !lines[i].startsWith("```") && !/^#{1,6}\s/.test(lines[i]) && !(isRow(lines[i]) && SEPARATOR.test(lines[i + 1] || ""))) i++;
    }
    const raw = lines.slice(start, i).join("\n");
    let blanks = 0;
    while (i < lines.length && blank(lines[i])) {
      blanks++;
      i++;
    }
    blocks.push({ kind, raw, gap: "\n".repeat(i < lines.length ? blanks + 1 : blanks) });
  }
  return blocks;
}

export const joinBlocks = (blocks: Block[]) => blocks.map((b) => b.raw + b.gap).join("");

function tableRows(raw: string, gherkin: boolean): string[][] {
  const lines = raw.split("\n").filter((line) => line.trim());
  return (gherkin ? lines : lines.filter((_, i) => i !== 1)).map(splitRow);
}

function tableText(rows: string[][], gherkin: boolean, indent: string): string {
  if (!gherkin) return [`| ${rows[0].map(cell).join(" | ")} |`, `| ${rows[0].map(() => "---").join(" | ")} |`, ...rows.slice(1).map((row) => `| ${row.map(cell).join(" | ")} |`)].join("\n");
  const widths = rows[0].map((_, c) => Math.max(...rows.map((row) => cell(row[c] || "").length)));
  return rows.map((row) => `${indent}| ${row.map((value, c) => cell(value).padEnd(widths[c])).join(" | ")} |`).join("\n");
}

function TableBlock({ raw, gherkin, label, readOnly, onChange }: { raw: string; gherkin: boolean; label: string; readOnly: boolean; onChange: (raw: string) => void }) {
  const rows = useMemo(() => {
    const parsed = tableRows(raw, gherkin);
    const width = Math.max(...parsed.map((row) => row.length));
    return parsed.map((row) => [...row, ...Array(width - row.length).fill("")]);
  }, [raw, gherkin]);
  const indent = raw.match(/^\s*/)?.[0] || "";
  const commit = (next: string[][]) => onChange(tableText(next, gherkin, indent));
  const setCell = (r: number, c: number, value: string) => commit(rows.map((row, i) => (i === r ? row.map((v, j) => (j === c ? value : v)) : row)));
  if (readOnly) {
    return <div className="doc-table-wrap"><table className="doc-table"><thead><tr>{rows[0].map((v, c) => <th key={c}>{v}</th>)}</tr></thead><tbody>{rows.slice(1).map((row, r) => <tr key={r}>{row.map((v, c) => <td key={c}>{v}</td>)}</tr>)}</tbody></table></div>;
  }
  const button = "rounded border border-slate-300 px-1.5 py-0.5 text-[11px] font-semibold text-slate-600 hover:border-indigo-500 hover:text-indigo-500 dark:border-slate-700 dark:text-slate-400";
  return (
    <div data-testid="table-block">
      <div className="doc-table-wrap">
        <table className="doc-table">
          <tbody>
            {rows.map((row, r) => (
              <tr key={r} className={r === 0 ? "doc-table-head" : ""}>
                {row.map((value, c) => <td key={c}><textarea rows={1} aria-label={`${label}, row ${r + 1}, column ${c + 1}`} className="doc-cell" value={value} onChange={(e) => setCell(r, c, e.target.value.replace(/\s*\n\s*/g, " "))} /></td>)}
                <td className="w-6 !border-0 !bg-transparent !p-0">{r > 0 && rows.length > 2 && <button type="button" aria-label={`Remove row ${r + 1}`} title="Remove row" className="ml-1 text-slate-400 hover:text-rose-500" onClick={() => commit(rows.filter((_, i) => i !== r))}><Trash2 className="h-3.5 w-3.5" /></button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-1 flex flex-wrap gap-1.5">
        <button type="button" className={button} onClick={() => commit([...rows, rows[0].map(() => "")])}>Add row</button>
        <button type="button" className={button} onClick={() => commit(rows.map((row, r) => [...row, r === 0 ? `Column ${row.length + 1}` : ""]))}>Add column</button>
        {rows[0].length > 1 && <button type="button" className={button} onClick={() => commit(rows.map((row) => row.slice(0, -1)))}>Remove last column</button>}
      </div>
    </div>
  );
}

export function GherkinText({ text }: { text: string }) {
  const keyword = /^(\s*)(Feature:|Rule:|Background:|Scenario Outline:|Scenario Template:|Scenario:|Example:|Examples:|Given|When|Then|And|But)(.*)$/;
  return (
    <pre className="mono overflow-auto text-sm leading-relaxed">
      {text.split("\n").map((line, i) => {
        const match = line.match(keyword);
        if (line.trim().startsWith("@")) return <div key={i} className="text-amber-600 dark:text-amber-400">{line}</div>;
        if (!match) return <div key={i}>{line || " "}</div>;
        const heading = match[2].endsWith(":");
        return <div key={i} className={heading ? "font-bold" : ""}>{match[1]}<span className="font-bold text-indigo-500">{match[2]}</span>{match[3]}</div>;
      })}
    </pre>
  );
}

function TextBlock({ raw, gherkin, readOnly, onChange, onRemove }: { raw: string; gherkin: boolean; readOnly: boolean; onChange: (raw: string) => void; onRemove: () => void }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(raw);
  const box = useRef<HTMLTextAreaElement>(null);
  useEffect(() => setValue(raw), [raw]);
  useEffect(() => {
    if (editing) box.current?.focus();
  }, [editing]);
  const view = gherkin ? <GherkinText text={value} /> : <Markdown>{value}</Markdown>;
  if (readOnly) return view;
  if (editing) {
    return (
      <div className="rounded-lg border border-indigo-500 p-2" data-testid="text-editor">
        <textarea ref={box} aria-label="Edit this block" spellCheck={!gherkin} className="doc-text-input mono w-full bg-transparent text-[13px] leading-relaxed outline-none" value={value}
          onChange={(e) => setValue(e.target.value)}
          onBlur={() => { setEditing(false); if (value !== raw) onChange(value); }}
          onKeyDown={(e) => { if (e.key === "Escape") { setValue(raw); setEditing(false); } }} />
        <div className="mt-2 border-t border-dashed border-slate-300 pt-2 dark:border-slate-700" data-testid="live-preview">{view}</div>
      </div>
    );
  }
  return (
    <div className="group/text relative">
      <div role="button" tabIndex={0} title="Select to edit" data-testid="text-block" className="cursor-text rounded-lg px-1 outline-none hover:bg-indigo-500/5 focus:ring-2 focus:ring-indigo-500"
        onClick={(e) => { if (!(e.target as HTMLElement).closest("a")) setEditing(true); }}
        onKeyDown={(e) => { if (e.key === "Enter" && e.target === e.currentTarget) { e.preventDefault(); setEditing(true); } }}>{view}</div>
      <button type="button" aria-label="Remove this block" title="Remove this block" className="absolute -right-5 top-1 text-slate-400 opacity-0 hover:text-rose-500 focus:opacity-100 group-hover/text:opacity-100" onClick={onRemove}><Trash2 className="h-3.5 w-3.5" /></button>
    </div>
  );
}

function Insert({ documentId, onInsert, onError }: { documentId: string; onInsert: (raw: string) => void; onError: (message: string) => void }) {
  const button = "inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-600 hover:border-indigo-500 hover:text-indigo-500 dark:border-slate-700 dark:bg-[#0b1329] dark:text-slate-300";
  const addImage = async (file?: File) => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    try {
      const saved = await upload(`/documents/${documentId}/images`, form);
      onInsert(`![${file.name.replace(/[[\]]/g, "")}](${saved.url})`);
    } catch (e: any) {
      onError(e.message);
    }
  };
  return (
    <>
      <button type="button" className={button} onClick={() => onInsert("New text. Select it to edit.")}><Type className="h-3.5 w-3.5" /> Add text</button>
      <button type="button" className={button} onClick={() => onInsert("| Column 1 | Column 2 |\n| --- | --- |\n|  |  |")}><Table2 className="h-3.5 w-3.5" /> Add table</button>
      <label className={`${button} cursor-pointer`}><ImagePlus className="h-3.5 w-3.5" /> Add image<input aria-label="Add image" type="file" accept="image/png,image/jpeg,image/gif,image/webp" className="sr-only" onChange={(e) => { addImage(e.target.files?.[0]); e.target.value = ""; }} /></label>
    </>
  );
}

/** The formatted document. Unless read-only, each block can be edited where it appears. */
export function DocumentEditor({ documentId, value, gherkin, readOnly = false, onChange, onError = () => {} }: { documentId: string; value: string; gherkin: boolean; readOnly?: boolean; onChange?: (value: string) => void; onError?: (message: string) => void }) {
  const blocks = useMemo(() => parseBlocks(value, gherkin), [value, gherkin]);
  const emit = (next: Block[]) => onChange?.(joinBlocks(next));
  const update = (index: number, raw: string) => emit(blocks.map((block, i) => (i === index ? { ...block, raw } : block)));
  const remove = (index: number) => emit(blocks.filter((_, i) => i !== index));
  const insert = (index: number, raw: string) => {
    const next = [...blocks];
    if (index >= 0 && !next[index].gap) next[index] = { ...next[index], gap: "\n\n" };
    next.splice(index + 1, 0, { kind: "text", raw, gap: index + 1 < blocks.length ? "\n\n" : "\n" });
    emit(next);
  };
  return (
    <div className="doc-page" data-testid="document-page">
      {!blocks.length && <p className="text-sm text-slate-500">This document is empty.</p>}
      {blocks.map((block, i) => (
        <div key={i} className="group/block">
          {block.kind === "table"
            ? <TableBlock raw={block.raw} gherkin={gherkin} label={`Table ${blocks.slice(0, i).filter((b) => b.kind === "table").length + 1}`} readOnly={readOnly} onChange={(raw) => update(i, raw)} />
            : <TextBlock raw={block.raw} gherkin={gherkin} readOnly={readOnly} onChange={(raw) => (raw.trim() ? update(i, raw) : remove(i))} onRemove={() => remove(i)} />}
          {!readOnly && !gherkin && (
            <div className="hidden h-7 items-center gap-1.5 focus-within:flex group-hover/block:flex" aria-label="Insert after this block">
              <Plus className="h-3.5 w-3.5 text-slate-400" /><Insert documentId={documentId} onInsert={(raw) => insert(i, raw)} onError={onError} />
            </div>
          )}
        </div>
      ))}
      {!readOnly && !gherkin && <div className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-slate-200 pt-3 dark:border-slate-800" data-testid="doc-toolbar"><Insert documentId={documentId} onInsert={(raw) => insert(blocks.length - 1, raw)} onError={onError} /></div>}
    </div>
  );
}
