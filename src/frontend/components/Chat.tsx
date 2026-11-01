"use client";

import { CopilotKit, useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import { Brain, ExternalLink, Loader2, MessageSquarePlus, Pencil, Send, Trash2, Wrench } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, when } from "../lib/api";
import { ModelPicker } from "./ModelPicker";
import { Button, Empty, ErrorNote, inputClass, Markdown, Spinner, useToast } from "./ui";

/** Headless CopilotKit over AG-UI: the UI waits until the agent is ready, so a send is never lost. */
function Conversation({ thread, onReplied }: { thread: any; onReplied: () => void }) {
  const { agent, isReady } = useAgent({ agentId: thread.agent });
  const { copilotkit } = useCopilotKit();
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);
  const [model, setModel] = useState<string>(thread.model || "");
  const [tools, setTools] = useState<{ models: string[]; default: string; tools: Record<string, any> } | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => { api("/settings/models").then(setTools).catch(() => setTools(null)); }, [thread.id]);
  const current = model || tools?.default || "";
  const toolCheck = tools?.tools?.[current];
  useEffect(() => setModel(thread.model || ""), [thread.id, thread.model]);
  // the server checks the pick too: a model this account may not use is refused there
  const pickModel = async (next: string) => {
    setError("");
    try {
      await api(`/chats/${thread.id}`, { method: "PATCH", json: { model: next } });
      setModel(next);
    } catch (e: any) {
      setError(e.message);
    }
  };
  useEffect(() => {
    // eslint-disable-next-line react-hooks/immutability -- AG-UI reads the thread id from the agent object
    agent.threadId = thread.id;
    agent.setMessages(thread.messages.map((m: any) => ({ id: m.id, role: m.role, content: m.content })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agent, thread.id]);
  const messages: any[] = agent.messages || [];
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [messages.length, running]);
  const send = async () => {
    const content = text.trim();
    if (!content || running || !isReady) return;
    setText("");
    setError("");
    setRunning(true);
    agent.addMessage({ id: crypto.randomUUID(), role: "user", content });
    try {
      await copilotkit.runAgent({ agent });
    } catch (e: any) {
      setError(e.message || "The agent could not reply");
    } finally {
      setRunning(false);
      onReplied();
    }
  };
  const shown = messages.filter((m) => m.role === "user" || m.role === "assistant");
  return (
    <>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4" data-testid="chat-messages">
        {!shown.length && <p className="text-sm text-slate-500">Ask about this project&apos;s documents and code, or try /scan, /gates, /verify, /docs.</p>}
        {shown.map((m) => (
          <div key={m.id} data-role={m.role} className={m.role === "user" ? "ml-auto w-fit max-w-[80%] rounded-xl bg-indigo-600 px-3 py-2 text-sm whitespace-pre-wrap text-white" : "max-w-full"}>
            {m.role === "user" ? (typeof m.content === "string" ? m.content : "") : (
              <>
                {m.toolCalls?.length > 0 && <p className="mono mb-1 flex flex-wrap items-center gap-1 text-[11px] text-slate-500"><Wrench className="h-3 w-3" /> {m.toolCalls.map((c: any) => c.function?.name).join(", ")}</p>}
                {m.content && <Markdown>{String(m.content)}</Markdown>}
              </>
            )}
          </div>
        ))}
        {running && <p className="flex items-center gap-1.5 text-xs text-slate-500"><Loader2 className="h-3 w-3 animate-spin" /> Agent is working</p>}
        <ErrorNote message={error} />
        <div ref={bottom} />
      </div>
      {toolCheck?.status === "failed" && <p role="alert" data-testid="tool-warning" className="mx-3 mb-1 rounded-lg bg-amber-500/15 px-3 py-1.5 text-xs text-amber-700 dark:text-amber-400">{current} failed the tool check ({toolCheck.reason}). It may ignore the project tools in this chat, so check its answers against the documents.</p>}
      <div className="flex items-center gap-2 border-t border-slate-200 px-3 pt-2 text-xs text-slate-500 dark:border-slate-800">Model <ModelPicker value={model} onChange={pickModel} compact /></div>
      <form className="flex items-end gap-2 px-3 pb-3 pt-2" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <textarea aria-label="Message" rows={2} disabled={!isReady} className={`${inputClass} resize-none`} placeholder={isReady ? "Ask about this project, its documents, or run an agent" : "Connecting"} value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
        <Button type="submit" disabled={!isReady || running || !text.trim()} aria-label="Send message"><Send className="h-4 w-4" /></Button>
      </form>
    </>
  );
}

export function Chat({ projectId, standalone = false }: { projectId: string; standalone?: boolean }) {
  const [agents, setAgents] = useState<any[]>([]);
  const [threads, setThreads] = useState<any[]>([]);
  const [thread, setThread] = useState<any>(null);
  const [memories, setMemories] = useState<any[]>([]);
  const [memory, setMemory] = useState("");
  const [showMemory, setShowMemory] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();

  const loadThreads = useCallback(() => api(`/projects/${projectId}/chats`).then(setThreads), [projectId]);
  const loadMemories = useCallback(() => api(`/projects/${projectId}/memories`).then(setMemories), [projectId]);

  useEffect(() => {
    api("/chat/agents").then(setAgents);
    loadThreads().catch((e) => setError(e.message));
    loadMemories();
  }, [loadThreads, loadMemories]);

  // title and message count arrive after the assistant replies
  useEffect(() => {
    if (!thread) return;
    const timer = setInterval(loadThreads, 5000);
    return () => clearInterval(timer);
  }, [thread, loadThreads]);

  const open = async (id: string) => setThread(await api(`/chats/${id}`));
  const create = async (agent = "project-copilot") => {
    setThread(null);  // the old chat closes at once, so nothing typed can land in it
    const created = await api(`/projects/${projectId}/chats`, { json: { agent } });
    await loadThreads();
    setThread({ ...created, messages: [] });
  };
  const remove = async (id: string) => {
    if (!confirm("Delete this chat?")) return;
    await api(`/chats/${id}`, { method: "DELETE" });
    if (thread?.id === id) setThread(null);
    loadThreads();
  };
  const rename = async (t: any) => {
    const title = prompt("Chat title", t.title);
    if (title) {
      await api(`/chats/${t.id}`, { method: "PATCH", json: { title } });
      loadThreads();
    }
  };
  const addMemory = async () => {
    if (!memory.trim()) return;
    await api(`/projects/${projectId}/memories`, { json: { content: memory } });
    setMemory("");
    loadMemories();
    toast("Saved to project memory");
  };

  return (
    <div className={`grid gap-3 md:grid-cols-[250px_1fr] ${standalone ? "h-screen p-3" : "h-[calc(100vh-110px)]"}`}>
      <div className="flex min-h-0 flex-col gap-2 rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-[#0b1329]">
        <select aria-label="Agent for new chat" className={inputClass} defaultValue="project-copilot" id="new-agent">
          {agents.map((a) => <option key={a.key} value={a.key}>{a.name}</option>)}
        </select>
        <Button onClick={() => create((document.getElementById("new-agent") as HTMLSelectElement).value)}><MessageSquarePlus className="h-4 w-4" /> New chat</Button>
        <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto" aria-label="Saved chats">
          {threads.map((t) => (
            <li key={t.id} className={`group flex items-center gap-1 rounded-lg px-2 py-1.5 ${thread?.id === t.id ? "bg-indigo-600/15" : "hover:bg-slate-100 dark:hover:bg-slate-900"}`}>
              <button className="min-w-0 flex-1 text-left" onClick={() => open(t.id)}>
                <span className="block truncate text-[13px] font-semibold">{t.title}</span>
                <span className="block truncate text-[11px] text-slate-500">{agents.find((a) => a.key === t.agent)?.name} · {when(t.updated_at)}</span>
              </button>
              <button aria-label={`Rename ${t.title}`} onClick={() => rename(t)} className="text-slate-400 opacity-0 hover:text-indigo-500 group-hover:opacity-100"><Pencil className="h-3.5 w-3.5" /></button>
              <button aria-label={`Delete ${t.title}`} onClick={() => remove(t.id)} className="text-slate-400 opacity-0 hover:text-rose-500 group-hover:opacity-100"><Trash2 className="h-3.5 w-3.5" /></button>
            </li>
          ))}
        </ul>
        <button onClick={() => setShowMemory(!showMemory)} className="flex items-center gap-1.5 text-xs font-semibold text-slate-600 dark:text-slate-400"><Brain className="h-3.5 w-3.5" /> Project memory ({memories.length})</button>
        {showMemory && (
          <div className="max-h-52 space-y-1 overflow-y-auto">
            {memories.map((m) => (
              <div key={m.id} className="flex items-start gap-1 text-[11px]">
                <span className="flex-1">{m.content}</span>
                <button aria-label="Forget" onClick={() => api(`/memories/${m.id}`, { method: "DELETE" }).then(loadMemories)} className="text-slate-400 hover:text-rose-500"><Trash2 className="h-3 w-3" /></button>
              </div>
            ))}
            <div className="flex gap-1">
              <input className={inputClass} value={memory} onChange={(e) => setMemory(e.target.value)} placeholder="Add a fact to remember" />
              <Button variant="secondary" onClick={addMemory}>Add</Button>
            </div>
          </div>
        )}
        {!standalone && (
          <a href={`/chat/${projectId}`} target="atlas-chat" rel="noopener" onClick={(e) => { e.preventDefault(); window.open(`/chat/${projectId}`, `atlas-chat-${projectId}`, "width=1000,height=800"); }} className="flex items-center gap-1.5 text-xs font-semibold text-indigo-500"><ExternalLink className="h-3.5 w-3.5" /> Open in new window</a>
        )}
      </div>
      <div className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-[#0b1329]" data-testid="chat-pane">
        <ErrorNote message={error} />
        {thread ? (
          <CopilotKit key={thread.id} runtimeUrl="/api/copilotkit" enableInspector={false}>
            <Conversation thread={thread} onReplied={() => { loadThreads(); loadMemories(); }} />
          </CopilotKit>
        ) : threads.length || agents.length ? (
          <div className="m-auto max-w-md p-6"><Empty title="Start or open a chat">Each agent reads this project&apos;s real documents and code. Chats and memory are saved.</Empty></div>
        ) : <Spinner />}
      </div>
    </div>
  );
}
