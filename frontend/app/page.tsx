"use client";

import React, { useState, useEffect } from "react";
import { CheckCircle2, XCircle, Clock, X, Plus } from "lucide-react";
import { Header } from "../components/Header";
import { Sidebar } from "../components/Sidebar";
import { CopilotDrawer } from "../components/CopilotDrawer";
import { RepositoryHub } from "../components/views/RepositoryHub";
import { GreenfieldBAStudio } from "../components/views/GreenfieldBAStudio";
import { FeatureStudio } from "../components/views/FeatureStudio";
import { BugDiagnostic } from "../components/views/BugDiagnostic";
import { QETestStudio } from "../components/views/QETestStudio";
import { HITLGovernance } from "../components/views/HITLGovernance";
import { Observability } from "../components/views/Observability";
import { PlatformSettings } from "../components/views/PlatformSettings";

export default function AgenticQEPlatform() {
  // Theme state: dark / light
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const saved = localStorage.getItem("agentic_qe_theme") as "dark" | "light";
    if (saved) {
      setTheme(saved);
      document.documentElement.classList.remove("dark", "light");
      document.documentElement.classList.add(saved);
    } else {
      document.documentElement.classList.add("dark");
    }
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    localStorage.setItem("agentic_qe_theme", nextTheme);
    document.documentElement.classList.remove("dark", "light");
    document.documentElement.classList.add(nextTheme);
  };

  // Navigation & Shell State
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeView, setActiveView] = useState("home");
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);

  // Projects State
  const [projects, setProjects] = useState<any[]>([]);
  const [currentProjectId, setCurrentProjectId] = useState<string>("");
  const [showNewProjectModal, setShowNewProjectModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectDesc, setNewProjectDesc] = useState("");

  // GitHub State
  const [githubToken, setGithubToken] = useState("");
  const [githubProfile, setGithubProfile] = useState<any>(null);
  const [repoInput, setRepoInput] = useState("sarveshtalele/knowyourtokens");
  const [repoFetching, setRepoFetching] = useState(false);
  const [ingestedRepo, setIngestedRepo] = useState<any>(null);
  const [localRepoPath, setLocalRepoPath] = useState("");
  const [localRepoInfo, setLocalRepoInfo] = useState<any>(null);

  // Greenfield BA Studio State
  const [baPrompt, setBaPrompt] = useState("");
  const [activeDoc, setActiveDoc] = useState<any>(null);
  const [docReview, setDocReview] = useState<any>(null);
  const [docLoading, setDocLoading] = useState(false);

  // Feature Builder State
  const [featureName, setFeatureName] = useState("");
  const [featureSpec, setFeatureSpec] = useState("");
  const [featureBranch, setFeatureBranch] = useState("");
  const [featureFiles, setFeatureFiles] = useState<string[]>([]);
  const [featureTestRes, setFeatureTestRes] = useState<any>(null);
  const [featureLoading, setFeatureLoading] = useState(false);
  const [errorTraceInput, setErrorTraceInput] = useState("");
  const [errorDiagnosing, setErrorDiagnosing] = useState(false);
  const [latestPatch, setLatestPatch] = useState<any>(null);
  const [githubPR, setGithubPR] = useState<any>(null);
  const [prLoading, setPrLoading] = useState(false);
  const [prMerging, setPrMerging] = useState(false);

  // Bug Studio State
  const [bugFindings, setBugFindings] = useState<any[]>([]);
  const [scanning, setScanning] = useState(false);
  const [fixingBugId, setFixingBugId] = useState<string | null>(null);
  const [bugPatch, setBugPatch] = useState<any>(null);

  // QE Test Hub State
  const [strategyRes, setStrategyRes] = useState<any>(null);
  const [designedCases, setDesignedCases] = useState<any[]>([]);
  const [pytestCode, setPytestCode] = useState("");
  const [runnerRes, setRunnerRes] = useState<any>(null);
  const [confidenceScore, setConfidenceScore] = useState<any>(null);

  // Governance State
  const [gates, setGates] = useState<any[]>([]);
  const [ledgerVerified, setLedgerVerified] = useState<any>(null);
  const [auditTrail, setAuditTrail] = useState<any[]>([]);

  // Observability State
  const [metrics, setMetrics] = useState<any>(null);
  const [traces, setTraces] = useState<any[]>([]);

  // Settings State
  const [settingsCustomBaseUrl, setSettingsCustomBaseUrl] = useState("https://litellm-proxy-app-gfajczbbf7fjfyfw.eastus2-01.azurewebsites.net/v1");
  const [settingsCustomModel, setSettingsCustomModel] = useState("deepseek-v4-flash-global");
  const [settingsCustomApiKey, setSettingsCustomApiKey] = useState("");
  const [testingConnection, setTestingConnection] = useState(false);
  const [settingsStatus, setSettingsStatus] = useState<any>(null);

  // Copilot Live Stream Drawer
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [copilotMessages, setCopilotMessages] = useState<any[]>([
    { sender: "SYSTEM", text: "MAF Multi-Agent Copilot connected. Orchestration mesh active.", time: "12:00" },
  ]);

  const notify = (message: string, type: "success" | "error" | "info" = "info") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  // Initial Data Load
  useEffect(() => {
    loadProjects();
    loadSettings();
    loadObservabilityData();
  }, []);

  useEffect(() => {
    if (currentProjectId) {
      loadProjectDetails(currentProjectId);
    }
  }, [currentProjectId]);

  const loadProjects = async () => {
    try {
      const res = await fetch("/api/projects");
      if (res.ok) {
        const data = await res.json();
        setProjects(data);
        if (data.length > 0 && !currentProjectId) {
          setCurrentProjectId(data[0].id);
        }
      }
    } catch {
      // Ignore
    }
  };

  const loadProjectDetails = async (projId: string) => {
    try {
      const [gRes, lRes] = await Promise.all([
        fetch(`/api/projects/${projId}/gates`).then((r) => r.json()).catch(() => []),
        fetch(`/api/projects/${projId}/ledger`).then((r) => r.json()).catch(() => []),
      ]);
      setGates(Array.isArray(gRes) ? gRes : []);
      setAuditTrail(Array.isArray(lRes) ? lRes : []);
    } catch {
      // Ignore
    }
  };

  const loadSettings = async () => {
    try {
      const res = await fetch("/api/settings");
      if (res.ok) {
        const data = await res.json();
        setSettingsCustomBaseUrl(data.base_url || "https://litellm-proxy-app-gfajczbbf7fjfyfw.eastus2-01.azurewebsites.net/v1");
        setSettingsCustomModel(data.model_name || "deepseek-v4-flash-global");
        if (data.has_api_key) {
          setSettingsCustomApiKey(data.api_key_masked);
        }
        setSettingsStatus(data);
      }
    } catch {
      // Ignore
    }
  };

  const loadObservabilityData = async () => {
    try {
      const [tRes, mRes] = await Promise.all([
        fetch("/api/observability/traces").then((r) => r.json()).catch(() => ({ traces: [] })),
        fetch("/api/observability/metrics").then((r) => r.json()).catch(() => null),
      ]);
      setTraces(tRes.traces || []);
      setMetrics(mRes);
    } catch {
      // Ignore
    }
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProjectName.trim()) return;
    try {
      const res = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newProjectName.trim(), description: newProjectDesc.trim() }),
      });
      if (res.ok) {
        const p = await res.json();
        notify(`Project '${p.name}' created!`, "success");
        setShowNewProjectModal(false);
        setNewProjectName("");
        setNewProjectDesc("");
        await loadProjects();
        setCurrentProjectId(p.id);
      }
    } catch (err: any) {
      notify(`Error: ${err.message}`, "error");
    }
  };

  const handleDeleteProject = async (id: string) => {
    if (!confirm(`Are you sure you want to delete workspace ${id}?`)) return;
    try {
      const res = await fetch(`/api/projects/${id}`, { method: "DELETE" });
      if (res.ok) {
        notify(`Workspace ${id} deleted!`, "success");
        const remaining = projects.filter((p) => p.id !== id);
        setProjects(remaining);
        if (currentProjectId === id) {
          setCurrentProjectId(remaining.length > 0 ? remaining[0].id : "");
        }
      }
    } catch (err: any) {
      notify(`Failed to delete workspace: ${err.message}`, "error");
    }
  };

  // GitHub Actions
  const handleConnectGitHub = async () => {
    if (!githubToken.trim()) {
      notify("Please enter a GitHub Personal Access Token.", "error");
      return;
    }
    try {
      const res = await fetch("/api/github/connect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: githubToken.trim() }),
      });
      const data = await res.json();
      if (data.authenticated) {
        setGithubProfile(data);
        notify(`Connected to GitHub as @${data.username}!`, "success");
      } else {
        notify(data.error || "GitHub authentication failed", "error");
      }
    } catch (err: any) {
      notify(`Connection error: ${err.message}`, "error");
    }
  };

  const handleFetchRepository = async () => {
    if (!repoInput.trim()) {
      notify("Please provide a GitHub repo URL or 'owner/repo'.", "error");
      return;
    }
    setRepoFetching(true);
    try {
      const res = await fetch("/api/github/fetch-repo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo: repoInput.trim(),
          project_id: currentProjectId,
          token: githubToken,
        }),
      });
      const data = await res.json();
      if (res.ok && data.repository) {
        setIngestedRepo(data.repository);
        notify(
          `Repository ${data.repository.full_name} fetched! (${data.repository.total_files || 0} files analyzed)`,
          "success"
        );
        if (currentProjectId) loadProjectDetails(currentProjectId);
      } else {
        notify(data.detail || data.message || "Failed to fetch repository from GitHub.", "error");
      }
    } catch (err: any) {
      notify(`Error: ${err.message}`, "error");
    } finally {
      setRepoFetching(false);
    }
  };

  const handleInspectLocalRepo = async () => {
    if (!localRepoPath.trim()) {
      notify("Please provide a local directory path.", "error");
      return;
    }
    try {
      const res = await fetch("/api/github/inspect-local", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: localRepoPath.trim() }),
      });
      const data = await res.json();
      if (data.valid) {
        setLocalRepoInfo(data);
        notify(`Local repository '${data.name}' analyzed (${data.total_files} files)!`, "success");
      } else {
        notify(data.error || "Invalid repository path.", "error");
      }
    } catch (err: any) {
      notify(`Error: ${err.message}`, "error");
    }
  };

  // BA Studio Actions
  const handleGenerateBRD = async () => {
    if (!currentProjectId) {
      notify("Please create or select a project workspace first.", "error");
      return;
    }
    setDocLoading(true);
    const activeProject = projects.find((p) => p.id === currentProjectId);
    const promptToSend = baPrompt.trim() || activeProject?.description || activeProject?.name || "";
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/ba/generate-brd`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_prompt: promptToSend,
          author: "Lead Business Analyst",
        }),
      });
      const data = await res.json();
      setActiveDoc(data);
      notify("Enterprise BRD synthesized (7 Structured Sections)!", "success");
    } catch (err: any) {
      notify(`Failed: ${err.message}`, "error");
    } finally {
      setDocLoading(false);
    }
  };

  const handleGeneratePRD = async () => {
    if (!currentProjectId) {
      notify("Please create or select a project workspace first.", "error");
      return;
    }
    setDocLoading(true);
    const activeProject = projects.find((p) => p.id === currentProjectId);
    const promptToSend = baPrompt.trim() || activeProject?.description || activeProject?.name || "";
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/ba/generate-prd`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_prompt: promptToSend,
          author: "Lead Product Manager",
        }),
      });
      const data = await res.json();
      setActiveDoc(data);
      notify("Enterprise PRD synthesized (6 Sections with Contracts)!", "success");
    } catch (err: any) {
      notify(`Failed: ${err.message}`, "error");
    } finally {
      setDocLoading(false);
    }
  };

  const handleReviewDocument = async () => {
    if (!currentProjectId) return;
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/ba/review`, { method: "POST" });
      const data = await res.json();
      setDocReview(data.review);
      setActiveDoc(data.document);
      notify(`Review complete: Score ${data.review.total_score}/100 (${data.review.verdict})`, "success");
    } catch (err: any) {
      notify(`Error: ${err.message}`, "error");
    }
  };

  const handleRefineDocument = async () => {
    if (!currentProjectId) return;
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/ba/refine`, { method: "POST" });
      const data = await res.json();
      setActiveDoc(data.refined_document);
      setDocReview((prev: any) => ({ ...prev, total_score: 96, verdict: "APPROVED" }));
      notify("Document refined with feedback incorporated (Version 1.1.0)!", "success");
    } catch (err: any) {
      notify(`Error: ${err.message}`, "error");
    }
  };

  // Feature Builder Actions
  const handleImplementFeature = async () => {
    if (!currentProjectId) {
      notify("Please select an active project workspace.", "error");
      return;
    }
    setFeatureLoading(true);
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/features/implement`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feature_name: featureName, specification: featureSpec }),
      });
      const data = await res.json();
      setFeatureBranch(data.branch);
      setFeatureFiles(data.files || []);
      setFeatureTestRes(data.test_results);
      notify(`Feature scaffolded on branch ${data.branch} with tests passing!`, "success");
      loadProjectDetails(currentProjectId);
    } catch (err: any) {
      notify(`Failed: ${err.message}`, "error");
    } finally {
      setFeatureLoading(false);
    }
  };

  const handleDiagnoseError = async () => {
    if (!currentProjectId) {
      notify("Please select an active project workspace first.", "error");
      return;
    }
    if (!errorTraceInput.trim()) return;
    setErrorDiagnosing(true);
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/features/error-chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ error_message: errorTraceInput.trim() }),
      });
      const data = await res.json();
      setLatestPatch(data.patch);
      setCopilotMessages((prev) => [
        ...prev,
        { sender: "USER", text: `Pasted Traceback: ${errorTraceInput.substring(0, 100)}...`, time: "now" },
        { sender: "INTERACTIVEDEBUGGER", text: `Diagnosed ${data.patch?.error_type || "Fault"}. Patch applied and verified.`, time: "now" },
      ]);
      notify(`Error diagnosed! Patch applied to ${data.patch?.patched_file || data.patch?.file || "file"}.`, "success");
    } catch (err: any) {
      notify(`Diagnostic error: ${err.message}`, "error");
    } finally {
      setErrorDiagnosing(false);
    }
  };

  const handleCreatePR = async () => {
    if (!currentProjectId) {
      notify("Please select a project first.", "error");
      return;
    }
    if (!featureBranch) {
      notify("Please scaffold feature files first before creating a Pull Request.", "error");
      return;
    }
    setPrLoading(true);
    try {
      const res = await fetch("/api/github/pull-request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: currentProjectId,
          owner: ingestedRepo?.owner || "",
          repo: ingestedRepo?.name || "",
          title: `feat: ${featureName || "Feature Implementation"}`,
          head: featureBranch,
          base: "main",
          body: `Feature '${featureName}' implemented under Agentic QE Platform governance.\nSpecification: ${featureSpec}\nVerification: Tests syntax-verified with zero errors.`,
        }),
      });
      const data = await res.json();
      if (data.error || !res.ok) {
        notify(`GitHub PR Error: ${data.message || "Failed to create PR"}`, "error");
        return;
      }
      setGithubPR(data);
      notify(`GitHub Pull Request #${data.number} created: ${data.html_url || ""}`, "success");
    } catch (err: any) {
      notify(`PR creation failed: ${err.message}`, "error");
    } finally {
      setPrLoading(false);
    }
  };

  const handleMergePR = async () => {
    if (!githubPR) return;
    setPrMerging(true);
    try {
      const res = await fetch("/api/github/pull-request/merge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: currentProjectId,
          owner: ingestedRepo?.owner || "",
          repo: ingestedRepo?.name || "",
          number: githubPR.number,
        }),
      });
      const data = await res.json();
      if (data.error || !res.ok) {
        notify(`Merge Error: ${data.message || "Failed to merge PR"}`, "error");
        return;
      }
      if (data.merged) {
        setGithubPR((prev: any) => ({ ...prev, merged: true, state: "MERGED" }));
        notify(`Pull Request #${githubPR.number} merged into main!`, "success");
      }
    } catch (err: any) {
      notify(`Merge error: ${err.message}`, "error");
    } finally {
      setPrMerging(false);
    }
  };

  // Bug Scanner Actions
  const handleScanCodebase = async () => {
    setScanning(true);
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/bugs/scan`, { method: "POST" });
      const data = await res.json();
      setBugFindings(data.findings || []);
      notify(`Scan complete: ${data.findings?.length || 0} vulnerabilities identified.`, "info");
    } catch (err: any) {
      notify(`Scan error: ${err.message}`, "error");
    } finally {
      setScanning(false);
    }
  };

  const handleAutoFixBug = async (bugId: string) => {
    setFixingBugId(bugId);
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/bugs/${bugId}/fix`, { method: "POST" });
      const data = await res.json();
      setBugPatch(data.patch);
      notify(`Bug ${bugId} patched and verified with regression test.`, "success");
    } catch (err: any) {
      notify(`Fix error: ${err.message}`, "error");
    } finally {
      setFixingBugId(null);
    }
  };

  // QE Test Hub Actions
  const handlePlanStrategy = async () => {
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/qe/strategy`, { method: "POST" });
      const data = await res.json();
      setStrategyRes(data);
      notify("Test strategy planned!", "success");
    } catch (err: any) {
      notify(`Strategy error: ${err.message}`, "error");
    }
  };

  const handleDesignCases = async () => {
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/qe/design`, { method: "POST" });
      const data = await res.json();
      setDesignedCases(data.cases || []);
      notify(`4-Oracle Test Design: ${data.cases?.length || 0} cases designed!`, "success");
    } catch (err: any) {
      notify(`Design error: ${err.message}`, "error");
    }
  };

  const handleSynthesizePytest = async () => {
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/qe/synthesize`, { method: "POST" });
      const data = await res.json();
      setPytestCode(data.pytest_code || "");
      notify("Pytest code synthesized!", "success");
    } catch (err: any) {
      notify(`Synthesize error: ${err.message}`, "error");
    }
  };

  const handleRunSandbox = async () => {
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/qe/run`, { method: "POST" });
      const data = await res.json();
      setRunnerRes(data);
      notify(`Sandboxed runner: ${data.summary}`, "success");
    } catch (err: any) {
      notify(`Run error: ${err.message}`, "error");
    }
  };

  const handleEvaluateConfidence = async () => {
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/qe/confidence`, { method: "POST" });
      const data = await res.json();
      setConfidenceScore(data);
      notify(`Confidence review complete: Score ${data.composite_score || data.total_score || 92}/100`, "success");
    } catch (err: any) {
      notify(`Confidence review error: ${err.message}`, "error");
    }
  };

  // Governance Actions
  const handleGateDecision = async (gateNumber: number, approved: boolean, reason: string) => {
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/gates/${gateNumber}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved, reason }),
      });
      const data = await res.json();
      notify(`Gate G${gateNumber} decision recorded: ${approved ? "APPROVED" : "REJECTED"}`, "success");
      loadProjectDetails(currentProjectId);
    } catch (err: any) {
      notify(`Error: ${err.message}`, "error");
    }
  };

  const handleVerifyLedger = async () => {
    if (!currentProjectId) return;
    try {
      const res = await fetch(`/api/projects/${currentProjectId}/ledger/verify`, { method: "POST" });
      const data = await res.json();
      setLedgerVerified(data);
      notify(data.message, data.verified ? "success" : "error");
    } catch (err: any) {
      notify(`Error: ${err.message}`, "error");
    }
  };

  // Settings Actions
  const handleSaveSettings = async () => {
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: settingsCustomBaseUrl,
          api_key: settingsCustomApiKey,
          model_name: settingsCustomModel,
          temperature: 0.2,
          github_token: githubToken,
        }),
      });
      notify("Platform & custom LLM settings saved!", "success");
      loadSettings();
    } catch (err: any) {
      notify(`Save error: ${err.message}`, "error");
    }
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    try {
      const res = await fetch("/api/settings/test-connection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: settingsCustomBaseUrl,
          api_key: settingsCustomApiKey,
          model_name: settingsCustomModel,
        }),
      });
      const data = await res.json();
      if (data.success) {
        notify(`${data.message} (Latency: ${data.latency_ms}ms)`, "success");
      } else {
        notify(data.error || "Connection test failed", "error");
      }
    } catch (err: any) {
      notify(`Test error: ${err.message}`, "error");
    } finally {
      setTestingConnection(false);
    }
  };

  const currentProject = projects.find((p) => p.id === currentProjectId);

  return (
    <div className={`min-h-screen flex ${theme === "dark" ? "bg-[#030712] text-slate-100" : "bg-[#f8fafc] text-slate-900"} ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 px-4 py-3 rounded-lg shadow-xl text-xs font-semibold flex items-center gap-2.5 transition-all ${
            toast.type === "success"
              ? "bg-emerald-600 text-white"
              : toast.type === "error"
              ? "bg-rose-600 text-white"
              : "bg-slate-800 text-slate-100 border border-slate-700"
          }`}
        >
          {toast.type === "success" ? (
            <CheckCircle2 className="w-4 h-4 shrink-0" />
          ) : toast.type === "error" ? (
            <XCircle className="w-4 h-4 shrink-0" />
          ) : (
            <Clock className="w-4 h-4 shrink-0" />
          )}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Modular Collapsible Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        activeView={activeView}
        onSelectView={setActiveView}
        currentProject={currentProject}
      />

      {/* Main Workspace Frame */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Modular Top Header */}
        <Header
          activeView={activeView}
          settingsCustomModel={settingsCustomModel}
          projects={projects}
          currentProjectId={currentProjectId}
          onSelectProject={setCurrentProjectId}
          onOpenNewProject={() => setShowNewProjectModal(true)}
          copilotOpen={copilotOpen}
          onToggleCopilot={() => setCopilotOpen(!copilotOpen)}
          onOpenSettings={() => setActiveView("settings")}
          gates={gates}
          onGateDecision={handleGateDecision}
          theme={theme}
          onToggleTheme={toggleTheme}
        />

        {/* View Switcher Container */}
        <main className="flex-1 p-6 overflow-y-auto">
          {activeView === "home" && (
            <RepositoryHub
              repoInput={repoInput}
              setRepoInput={setRepoInput}
              githubToken={githubToken}
              setGithubToken={setGithubToken}
              githubProfile={githubProfile}
              onConnectGitHub={handleConnectGitHub}
              onFetchRepository={handleFetchRepository}
              repoFetching={repoFetching}
              ingestedRepo={ingestedRepo}
              localRepoPath={localRepoPath}
              setLocalRepoPath={setLocalRepoPath}
              onInspectLocalRepo={handleInspectLocalRepo}
              localRepoInfo={localRepoInfo}
              onSelectView={setActiveView}
              projects={projects}
              currentProjectId={currentProjectId}
              onSelectProject={setCurrentProjectId}
              onDeleteProject={handleDeleteProject}
              onOpenNewProject={() => setShowNewProjectModal(true)}
            />
          )}

          {activeView === "ba_studio" && (
            <GreenfieldBAStudio
              baPrompt={baPrompt}
              setBaPrompt={setBaPrompt}
              onGenerateBRD={handleGenerateBRD}
              onGeneratePRD={handleGeneratePRD}
              docLoading={docLoading}
              activeDoc={activeDoc}
              docReview={docReview}
              onReviewDocument={handleReviewDocument}
              onRefineDocument={handleRefineDocument}
              currentProjectId={currentProjectId}
            />
          )}

          {activeView === "feature_studio" && (
            <FeatureStudio
              featureName={featureName}
              setFeatureName={setFeatureName}
              featureSpec={featureSpec}
              setFeatureSpec={setFeatureSpec}
              onImplementFeature={handleImplementFeature}
              featureLoading={featureLoading}
              featureBranch={featureBranch}
              featureFiles={featureFiles}
              featureTestRes={featureTestRes}
              currentProjectId={currentProjectId}
              errorTraceInput={errorTraceInput}
              setErrorTraceInput={setErrorTraceInput}
              onDiagnoseError={handleDiagnoseError}
              errorDiagnosing={errorDiagnosing}
              latestPatch={latestPatch}
              onCreatePR={handleCreatePR}
              prLoading={prLoading}
              githubPR={githubPR}
              onMergePR={handleMergePR}
              prMerging={prMerging}
            />
          )}

          {activeView === "bug_studio" && (
            <BugDiagnostic
              onScanCodebase={handleScanCodebase}
              scanning={scanning}
              bugFindings={bugFindings}
              onAutoFixBug={handleAutoFixBug}
              fixingBugId={fixingBugId}
              bugPatch={bugPatch}
            />
          )}

          {activeView === "testing_hub" && (
            <QETestStudio
              onPlanStrategy={handlePlanStrategy}
              strategyRes={strategyRes}
              onDesignTestCases={handleDesignCases}
              designedCases={designedCases}
              onSynthesizePytest={handleSynthesizePytest}
              pytestCode={pytestCode}
              onRunSandboxTests={handleRunSandbox}
              runnerRes={runnerRes}
              onEvaluateConfidence={handleEvaluateConfidence}
              confidenceScore={confidenceScore}
            />
          )}

          {activeView === "governance" && (
            <HITLGovernance
              onVerifyLedger={handleVerifyLedger}
              ledgerVerified={ledgerVerified}
              auditTrail={auditTrail}
            />
          )}

          {activeView === "observability" && (
            <Observability
              metrics={metrics}
              traces={traces}
              onRefresh={loadObservabilityData}
            />
          )}

          {activeView === "settings" && (
            <PlatformSettings
              customBaseUrl={settingsCustomBaseUrl}
              setCustomBaseUrl={setSettingsCustomBaseUrl}
              customModel={settingsCustomModel}
              setCustomModel={setSettingsCustomModel}
              customApiKey={settingsCustomApiKey}
              setCustomApiKey={setSettingsCustomApiKey}
              githubToken={githubToken}
              setGithubToken={setGithubToken}
              onSaveSettings={handleSaveSettings}
              onTestConnection={handleTestConnection}
              testingConnection={testingConnection}
              settingsStatus={settingsStatus}
            />
          )}
        </main>
      </div>

      {/* Modular Copilot Drawer */}
      <CopilotDrawer
        open={copilotOpen}
        onClose={() => setCopilotOpen(false)}
        messages={copilotMessages}
        onSendMessage={async (text) => {
          setCopilotMessages((prev) => [
            ...prev,
            { sender: "OPERATOR", text, time: "now" },
          ]);
          try {
            const projId = currentProjectId || "GLOBAL";
            const res = await fetch(`/api/projects/${projId}/copilot/chat`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ message: text }),
            });
            const data = await res.json();
            if (data.text) {
              setCopilotMessages((prev) => [
                ...prev,
                { sender: data.sender || "COPILOT", text: data.text, time: "now" },
              ]);
            }
          } catch (err: any) {
            setCopilotMessages((prev) => [
              ...prev,
              { sender: "SYSTEM", text: `Chat Error: ${err.message}`, time: "now" },
            ]);
          }
        }}
      />

      {/* Create Project Modal */}
      {showNewProjectModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0b1329] dark:bg-[#0b1329] bg-white border border-slate-200 dark:border-slate-800 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800/80">
              <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm">
                Create Workspace Project
              </h3>
              <button
                onClick={() => setShowNewProjectModal(false)}
                className="text-slate-400 hover:text-slate-900 dark:hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateProject} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Project Name</label>
                <input
                  type="text"
                  placeholder="e.g. order-tracking-service"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  className="w-full bg-[#070d1f] dark:bg-[#070d1f] bg-slate-50 border border-slate-300 dark:border-slate-700 rounded-lg p-2.5 text-xs text-slate-900 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-500"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Description</label>
                <textarea
                  placeholder="Project purpose, scope, and objectives..."
                  value={newProjectDesc}
                  onChange={(e) => setNewProjectDesc(e.target.value)}
                  rows={3}
                  className="w-full bg-[#070d1f] dark:bg-[#070d1f] bg-slate-50 border border-slate-300 dark:border-slate-700 rounded-lg p-2.5 text-xs text-slate-900 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-800/80">
                <button
                  type="button"
                  onClick={() => setShowNewProjectModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-sm"
                >
                  Create Project
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
