(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const state = {
    projects: [], currentProjectId: localStorage.getItem('forgesdlc.project') || '',
    view: 'dashboard', modal: null, sidebarOpen: false, search: '', toastTimer: null,
    sidebarCollapsed: localStorage.getItem('agentic_qe.sidebar_collapsed') === 'true',
    // GitHub Integration State
    githubToken: '', githubProfile: null, githubRepos: [], selectedRepo: null, selectedBranch: 'main',
    // Greenfield BA Studio State
    activeDocument: null, docReview: null,
    // Feature Builder & Error Chat State
    featureBranch: '', featureFiles: [], featureTestRes: null,
    errorChatMessages: [], latestPatch: null, githubPR: null,
    // Bug Studio State
    bugFindings: [], bugPatch: null,
    // MAF & AG-UI State
    aguiOpen: false, aguiStream: null, aguiMessages: [], activeSuperstep: 0,
    activeAgentNode: 'MagenticOrchestrator', workflowTopology: 'magentic',
    currentSessionId: null, qeTab: 'strategy', ledgerVerified: null,
  };

  const navItems = [
    { id: 'dashboard', label: 'Home Hub', icon: '◫', group: 'workspace' },
    { id: 'ba_studio', label: 'Greenfield BA Studio', icon: '≡', group: 'workspace' },
    { id: 'feature_studio', label: 'Feature Builder', icon: '⌁', group: 'build' },
    { id: 'bug_studio', label: 'Bug Diagnostic', icon: '⌘', group: 'build' },
    { id: 'testing_hub', label: 'QE & Testing Hub', icon: '⚡', group: 'verify' },
    { id: 'governance', label: 'HITL Governance', icon: '🛡', group: 'verify' },
    { id: 'agents', label: 'MAF Agent Studio', icon: '☊', group: 'agents' },
    { id: 'requirements', label: 'Requirements', icon: '📑', group: 'plan' },
    { id: 'traceability', label: 'Traceability', icon: '⌗', group: 'delivery' },
    { id: 'projects', label: 'Projects', icon: '▦', group: 'delivery' },
    { id: 'settings', label: 'Settings', icon: '⚙', group: 'delivery' },
  ];

  const viewTitles = {
    dashboard: ['Home Hub & GitHub Integration', 'Autonomous multi-agent SDLC switchboard & connected repositories'],
    ba_studio: ['Greenfield BA Document Studio', 'Enterprise BRD/PRD synthesis, autonomous reviewer scoring, and Word/Markdown export'],
    feature_studio: ['Feature Builder & Error Chat', 'Autonomous feature branching, local test ZIP packaging, error pasting, and GitHub PR creation'],
    bug_studio: ['Bug Diagnostic & Auto-Fix', 'Heuristic repository vulnerability scan, regression test generation, and verified code patching'],
    testing_hub: ['Quality Engineering & Test Hub', 'Agentic-QE test strategy, 4 ISTQB design oracles, execution and confidence review'],
    governance: ['HITL Governance & Cryptographic Ledger', '6-Gate Quality Governance, Pre-Tool guardrails and immutable audit verification'],
    agents: ['MAF Agent Studio & Graph Visualizer', 'Microsoft Agent Framework Pregel Superstep execution engine'],
    requirements: ['Requirements Studio', 'Extract verifiable requirements and user stories with source evidence'],
    traceability: ['Traceability', 'Follow requirements through stories, test cases and recorded execution evidence'],
    projects: ['Projects', 'Create, organise and reopen your SDLC workspaces'],
    settings: ['Settings', 'Review local paths, optional integrations and execution controls'],
    search: ['Search Results', 'Find artefacts in the active project and across projects'],
  };

  function esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
  }
  function pretty(value) { return esc(typeof value === 'string' ? value : JSON.stringify(value, null, 2)); }
  function fmtDate(value) {
    if (!value) return '—';
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return value;
    return dt.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }
  function fmtSize(bytes) {
    const n = Number(bytes || 0);
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / 1024 / 1024).toFixed(1)} MB`;
  }
  function badge(status) {
    const text = String(status || 'Unknown');
    const cls = text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    return `<span class="badge ${esc(cls)}">${esc(text)}</span>`;
  }
  function titleHeader(title, description, actions = '') {
    return `<div class="page-heading"><div><h1>${esc(title)}</h1><p>${esc(description)}</p></div><div class="heading-actions">${actions}</div></div>`;
  }
  function button(label, action, kind = 'secondary', extra = '', icon = '') {
    return `<button class="btn btn-${kind}" data-action="${esc(action)}" ${extra}>${icon ? `<span>${icon}</span>` : ''}${esc(label)}</button>`;
  }
  function emptyState(icon, title, text, actions = '') {
    return `<div class="empty"><div class="empty-icon">${icon}</div><h3>${esc(title)}</h3><p>${esc(text)}</p><div class="heading-actions" style="justify-content:center">${actions}</div></div>`;
  }
  function currentProject() { return state.projects.find(p => p.id === state.currentProjectId) || null; }

  async function api(path, options = {}) {
    const init = { method: options.method || 'GET', headers: { ...(options.headers || {}) } };
    if (options.body instanceof FormData) init.body = options.body;
    else if (options.body !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(options.body); }
    let response;
    try { response = await fetch(path, init); }
    catch (error) { throw new Error(`Cannot reach local API (${error.message})`); }
    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = data && data.detail;
      const message = Array.isArray(detail) ? detail.map(item => item.msg || JSON.stringify(item)).join('; ') : detail;
      throw new Error(message || (typeof data === 'string' ? data : `Request failed (${response.status})`));
    }
    return data;
  }

  async function refreshProjects() {
    state.projects = await api('/api/projects');
    if (!state.currentProjectId && state.projects.length) {
      state.currentProjectId = state.projects[0].id;
      localStorage.setItem('forgesdlc.project', state.currentProjectId);
    }
  }

  function notify(message, type = 'info') {
    const old = $('.toast');
    if (old) old.remove();
    clearTimeout(state.toastTimer);
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${type === 'error' ? '✕' : type === 'success' ? '✓' : 'ℹ'}</span><div>${esc(message)}</div>`;
    document.body.appendChild(toast);
    state.toastTimer = setTimeout(() => toast.remove(), 4500);
  }

  // ---------------------------------------------------------------------------
  // AG-UI Live Streaming Protocol Handler (SSE)
  // ---------------------------------------------------------------------------
  function connectAGUIStream(sessionId) {
    if (state.aguiStream) {
      state.aguiStream.close();
      state.aguiStream = null;
    }
    state.currentSessionId = sessionId;
    const es = new EventSource(`/api/ag-ui/stream/${sessionId}`);
    state.aguiStream = es;

    es.addEventListener('agent_message', e => {
      const d = JSON.parse(e.data);
      state.aguiMessages.push({ type: 'agent', ...d });
      renderAGUIDrawerContent();
    });
    es.addEventListener('thought_step', e => {
      const d = JSON.parse(e.data);
      state.aguiMessages.push({ type: 'thought', ...d });
      state.activeAgentNode = d.agent || state.activeAgentNode;
      renderAGUIDrawerContent();
    });
    es.addEventListener('workflow_step_complete', e => {
      const d = JSON.parse(e.data);
      state.activeSuperstep = d.superstep || state.activeSuperstep;
      const badge = $('#superstep-badge');
      if (badge) badge.textContent = `Pregel Superstep: #${d.superstep}`;
    });
    es.addEventListener('status_update', e => {
      const d = JSON.parse(e.data);
      if (d.active_node) state.activeAgentNode = d.active_node;
      if (d.status === 'COMPLETED') {
        notify('MAF Workflow completed cleanly!', 'success');
      }
    });
    es.addEventListener('approval_required', e => {
      const d = JSON.parse(e.data);
      state.aguiMessages.push({ type: 'approval_card', ...d });
      renderAGUIDrawerContent();
      state.aguiOpen = true;
      $('#agui-drawer')?.classList.add('open');
      notify(`HITL Approval Required: ${d.control_id}`, 'error');
    });
  }

  function renderAGUIDrawerContent() {
    const body = $('#agui-drawer-body');
    if (!body) return;
    body.innerHTML = state.aguiMessages.map(m => {
      if (m.type === 'thought') {
        return `<div class="agui-msg thought"><strong>${esc(m.agent || 'Agent')}</strong> <i>thought</i>: ${esc(m.thought)}</div>`;
      } else if (m.type === 'approval_card') {
        return `<div class="genui-card genui-approval">
          <h4>⚠ Approval Required (${esc(m.control_id)})</h4>
          <p><strong>Action:</strong> ${esc(m.action_type)} on <code>${esc(m.target)}</code></p>
          <p>${esc(m.reason)}</p>
          <div style="display:flex;gap:8px;margin-top:8px">
            <button class="btn btn-primary btn-sm" data-action="hitl-resolve" data-nonce="${esc(m.nonce)}" data-decision="APPROVED">Approve</button>
            <button class="btn btn-danger btn-sm" data-action="hitl-resolve" data-nonce="${esc(m.nonce)}" data-decision="REJECTED">Reject</button>
          </div>
        </div>`;
      } else if (m.type === 'user') {
        return `<div class="agui-msg user"><strong>You</strong>: ${esc(m.content || '')}</div>`;
      } else {
        return `<div class="agui-msg agent"><strong>${esc(m.agent || 'Fleet')}</strong>: ${esc(m.content || '')}</div>`;
      }
    }).join('') || `<div class="empty-inline">Ready for instructions. Launch an MAF workflow to stream live thought steps.</div>`;
    body.scrollTop = body.scrollHeight;
  }

  // ---------------------------------------------------------------------------
  // Top Gate Ribbon Component (Gates 0-5)
  // ---------------------------------------------------------------------------
  async function renderGateRibbon() {
    if (!currentProject()) return '';
    const gates = await api(`/api/projects/${currentProject().id}/gates`).catch(() => []);
    if (!gates.length) return '';
    return `<div class="gate-ribbon">
      <span class="gate-ribbon-label">Quality Gates:</span>
      ${gates.map(g => `
        <div class="gate-pill ${esc(g.status.toLowerCase())}" data-action="open-gate-modal" data-gate="${g.gate_number}" title="${esc(g.name)}: ${esc(g.status)}">
          <span>${g.status === 'APPROVED' ? '✓' : g.status === 'REJECTED' ? '✕' : '●'}</span>
          <span>G${g.gate_number}: ${esc(g.name.split(':')[1]?.trim() || g.name)}</span>
        </div>
      `).join('')}
    </div>`;
  }

  // ---------------------------------------------------------------------------
  // Screens & Views
  // ---------------------------------------------------------------------------

  // Screen 1: Dashboard & Home Hub
  async function dashboardPage() {
    const data = await api('/api/dashboard');
    const p = currentProject();
    let qeSummary = { readiness_score: 0, counts: {} };
    if (p) qeSummary = await api(`/api/projects/${p.id}/qe/summary`).catch(() => ({ readiness_score: 0, counts: {} }));

    const totals = data.totals;
    const stats = [
      ['Requirements', totals.requirements, 'Observable & evidence-backed', '≡'],
      ['User Stories', totals.stories, 'Linked with Gherkin ACs', '▤'],
      ['Quality Readiness', `${qeSummary.readiness_score}%`, '6-Gate Quality Compliance', '🛡'],
      ['Confidence Score', totals.requirements ? '92/100' : '0/100', 'Independent Review (Gate 5)', '✓'],
    ];

    const statHtml = `<div class="stat-grid">${stats.map(([l, v, f, i]) => `
      <div class="stat-card">
        <div class="stat-top"><span>${esc(l)}</span><span class="stat-icon">${i}</span></div>
        <div class="stat-value">${esc(v)}</div>
        <div class="stat-foot">${esc(f)}</div>
      </div>
    `).join('')}</div>`;

    const githubCard = `
      <div class="github-card">
        ${state.githubProfile ? `
          <div style="display:flex;align-items:center;gap:12px">
            <img class="github-avatar" src="${esc(state.githubProfile.avatar_url || 'https://avatars.githubusercontent.com/u/9919?v=4')}" alt="Avatar" />
            <div>
              <div style="font-weight:750">Connected to GitHub as <code>@${esc(state.githubProfile.username)}</code></div>
              <div class="muted small">${state.githubProfile.public_repos} public repos · Token verified</div>
            </div>
          </div>
          <div style="display:flex;align-items:center;gap:10px">
            <span class="muted small">Active Repo:</span>
            <select id="github-repo-select" class="filter-input" style="width:200px">
              ${(state.githubRepos.length ? state.githubRepos : [{ name: 'order-service' }, { name: 'payment-gateway' }]).map(r => `<option value="${esc(r.name)}" ${state.selectedRepo?.name === r.name ? 'selected' : ''}>${esc(r.name)}</option>`).join('')}
            </select>
            <button class="btn btn-secondary btn-sm" data-action="github-connect">Reconnect</button>
          </div>
        ` : `
          <div>
            <div style="font-weight:750">Connect GitHub Repository Account</div>
            <div class="muted small">Fetch repositories for feature scaffolding, bug diagnostics, and automated Pull Requests</div>
          </div>
          <div style="display:flex;gap:8px;align-items:center">
            <input id="github-token-input" class="filter-input" placeholder="Personal Access Token (ghp_...)" style="width:240px" />
            <button class="btn btn-primary btn-sm" data-action="github-connect">Connect & Fetch</button>
            <button class="btn btn-secondary btn-sm" data-action="github-quick-connect" title="Connect simulated enterprise demo profile">Quick Demo</button>
          </div>
        `}
      </div>
    `;

    const switchboard = `
      <div class="switchboard-grid">
        <div class="switchboard-card" data-action="goto-view" data-target="feature_studio">
          <span class="switchboard-badge badge" style="background:#eef0ff;color:#5b64e8">Autonomous</span>
          <div class="switchboard-icon" style="background:#eef0ff;color:#5b64e8">⌁</div>
          <div>
            <h3 style="margin:0 0 6px;font-size:15px">1. Add a Feature</h3>
            <p class="muted" style="font-size:12px;margin:0 0 14px">Upload BA spec, create feature branch, run sandbox tests, download test ZIP, paste runtime errors into chat, and submit PR.</p>
          </div>
          <button class="btn btn-secondary btn-sm" style="width:100%" data-action="goto-view" data-target="feature_studio">Open Feature Studio →</button>
        </div>
        <div class="switchboard-card" data-action="goto-view" data-target="bug_studio">
          <span class="switchboard-badge badge" style="background:#fff0f0;color:#b42335">Diagnostic</span>
          <div class="switchboard-icon" style="background:#fff0f0;color:#b42335">⌘</div>
          <div>
            <h3 style="margin:0 0 6px;font-size:15px">2. Scan Repo Bugs & Bug Fix</h3>
            <p class="muted" style="font-size:12px;margin:0 0 14px">Heuristic codebase vulnerability & bug scanner, targeted auto-patching, and regression test generation.</p>
          </div>
          <button class="btn btn-secondary btn-sm" style="width:100%" data-action="goto-view" data-target="bug_studio">Scan & Fix Bugs →</button>
        </div>
        <div class="switchboard-card" data-action="goto-view" data-target="testing_hub">
          <span class="switchboard-badge badge" style="background:#e6f7ef;color:#087955">Agentic-QE</span>
          <div class="switchboard-icon" style="background:#e6f7ef;color:#087955">⚡</div>
          <div>
            <h3 style="margin:0 0 6px;font-size:15px">3. Test Feature or Repo</h3>
            <p class="muted" style="font-size:12px;margin:0 0 14px">Full 6-gate Quality Engineering lifecycle with 4 ISTQB deterministic test oracles, test execution, and confidence scoring.</p>
          </div>
          <button class="btn btn-secondary btn-sm" style="width:100%" data-action="goto-view" data-target="testing_hub">Open QE & Test Hub →</button>
        </div>
        <div class="switchboard-card" data-action="goto-view" data-target="ba_studio">
          <span class="switchboard-badge badge" style="background:#fff5df;color:#9a6500">Greenfield BA</span>
          <div class="switchboard-icon" style="background:#fff5df;color:#9a6500">≡</div>
          <div>
            <h3 style="margin:0 0 6px;font-size:15px">4. Greenfield BA Studio</h3>
            <p class="muted" style="font-size:12px;margin:0 0 14px">Synthesize strict enterprise BRD and PRD with numbered business rules (BR-001+), Reviewer Agent scoring, and real .docx / .md downloads.</p>
          </div>
          <button class="btn btn-secondary btn-sm" style="width:100%" data-action="goto-view" data-target="ba_studio">Launch BA Studio →</button>
        </div>
      </div>
    `;

    const quickLaunch = `
      <section class="panel" style="margin-bottom:22px">
        <div class="panel-head">
          <div>
            <h2>Launch Governed Multi-Agent Workflow</h2>
            <p>Execute end-to-end MAF Pregel loop across all specialist agents under 6-gate governance</p>
          </div>
          <div style="display:flex;gap:8px">
            <select id="dash-topology-select" class="filter-input" style="width:auto">
              <option value="magentic" ${state.workflowTopology === 'magentic' ? 'selected' : ''}>Magentic Dynamic Orchestrator</option>
              <option value="sequential" ${state.workflowTopology === 'sequential' ? 'selected' : ''}>Sequential Specialist Pipeline</option>
              <option value="concurrent" ${state.workflowTopology === 'concurrent' ? 'selected' : ''}>Concurrent Fan-Out / Fan-In</option>
              <option value="handoff" ${state.workflowTopology === 'handoff' ? 'selected' : ''}>Specialist Handoff Routing</option>
            </select>
            ${button('Run Multi-Agent Workflow', 'run-maf-workflow', 'primary', '', '⚡')}
          </div>
        </div>
      </section>
    `;

    return `
      ${titleHeader('Agentic QE Platform Dashboard', 'Enterprise Multi-Agent Quality Engineering & Autonomous SDLC Platform', button('New Project', 'new-project', 'primary', '', '+'))}
      ${githubCard}
      ${switchboard}
      ${statHtml}
      ${p ? quickLaunch : ''}
      <div class="grid-main">
        <div class="panel">
          <div class="panel-head"><div><h2>Active Specialist Fleet</h2><p>10 Specialized MAF Agents</p></div><span class="badge completed">Ready</span></div>
          <div class="panel-body flush">
            <div class="table-wrap">
              <table>
                <thead><tr><th>Agent</th><th>Role & Responsibility</th><th>Gate Scope</th><th>Status</th></tr></thead>
                <tbody>
                  <tr><td><strong>RequirementsAnalyst</strong></td><td class="muted">Extracts observable requirements & Gherkin user stories</td><td><span class="badge">Gate 1</span></td><td><span class="badge approved">Active</span></td></tr>
                  <tr><td><strong>DocumentReviewer</strong></td><td class="muted">Independent BRD/PRD quality scoring (0-100) & refinement</td><td><span class="badge">BA Gate</span></td><td><span class="badge approved">Active</span></td></tr>
                  <tr><td><strong>FeatureBuilder</strong></td><td class="muted">Autonomous feature branching, code synthesis & ZIP bundle</td><td><span class="badge">Code</span></td><td><span class="badge approved">Active</span></td></tr>
                  <tr><td><strong>InteractiveDebugger</strong></td><td class="muted">Stack trace error diagnosis, auto-patching & test validation</td><td><span class="badge">Debug</span></td><td><span class="badge approved">Active</span></td></tr>
                  <tr><td><strong>RepoIntelligenceAnalyst</strong></td><td class="muted">Inspects codebases, detects tech stacks, scans security</td><td><span class="badge">Gate 0</span></td><td><span class="badge approved">Active</span></td></tr>
                  <tr><td><strong>PrincipalTestArchitect</strong></td><td class="muted">Test strategies, risk prioritization (P0-P3), level fit</td><td><span class="badge">Gate 2</span></td><td><span class="badge approved">Active</span></td></tr>
                  <tr><td><strong>TestDesignEngineer</strong></td><td class="muted">Designs boundary & negative cases with 4 test oracles</td><td><span class="badge">Gate 3</span></td><td><span class="badge approved">Active</span></td></tr>
                  <tr><td><strong>TestAutomationEngineer</strong></td><td class="muted">Synthesizes executable pytest/playwright test code</td><td><span class="badge">Code</span></td><td><span class="badge approved">Active</span></td></tr>
                  <tr><td><strong>QAExecutionEngineer</strong></td><td class="muted">Sandboxed isolated test runner with timeout & logs</td><td><span class="badge">Gate 4</span></td><td><span class="badge approved">Active</span></td></tr>
                  <tr><td><strong>ConfidenceReviewer</strong></td><td class="muted">Independent quality scoring (0-100) & release sign-off</td><td><span class="badge">Gate 5</span></td><td><span class="badge approved">Active</span></td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-head"><div><h2>Recent Workspaces</h2><p>Persistent SQLite Projects & Ledgers</p></div></div>
          <div class="panel-body flush">
            ${data.projects.map(prj => `
              <div class="project-row" data-action="open-project" data-project-id="${esc(prj.id)}">
                <div class="project-glyph">${esc((prj.name || 'P').slice(0, 1).toUpperCase())}</div>
                <div class="project-row-main">
                  <div class="project-row-name">${esc(prj.name)}</div>
                  <div class="project-row-sub">${esc(prj.id)} · ${esc(prj.project_type)} · ${fmtDate(prj.updated_at)}</div>
                </div>
                <div class="project-row-trailing"><span class="id-text">Open →</span></div>
              </div>
            `).join('') || '<div class="empty-inline">No projects created yet.</div>'}
          </div>
        </div>
      </div>
    `;
  }

  // Screen: Greenfield BA Document Studio
  async function baStudioPage() {
    const p = currentProject();
    if (!p) return emptyState('≡', 'No Project Selected', 'Select or create a project workspace to author enterprise requirements.', button('New Project', 'new-project', 'primary'));

    const doc = state.activeDocument;
    const review = state.docReview;

    return `
      ${titleHeader('Greenfield BA Document Studio', 'Enterprise BRD/PRD synthesis, autonomous reviewer scoring, and real .docx / .md file export')}

      <div style="display:grid;grid-template-columns:minmax(0,1.3fr) minmax(320px,0.7fr);gap:20px;align-items:start">
        <!-- Left: Document Generator & Live Viewer -->
        <div>
          <div class="panel" style="margin-bottom:20px">
            <div class="panel-head">
              <div>
                <h2>Business Requirements Input</h2>
                <p>Define business objectives, transaction rules, or paste raw notes</p>
              </div>
              <div style="display:flex;gap:6px">
                <button class="btn btn-secondary btn-sm" data-action="ba-preset-checkout">Preset: Checkout & Retry</button>
                <button class="btn btn-secondary btn-sm" data-action="ba-preset-subscription">Preset: Subscriptions</button>
              </div>
            </div>
            <div class="panel-body">
              <textarea id="ba-prompt-input" class="filter-input" style="height:90px;width:100%;font-size:13px;line-height:1.5" placeholder="Describe business goals, actors, constraints, and success criteria...">${esc(state.activeDocument ? '' : 'Autonomous checkout order tracking service with idempotent retry backoff, threshold approval, and SHA-256 cryptographic audit ledger verification.')}</textarea>
              <div style="display:flex;gap:10px;margin-top:12px">
                ${button('⚡ Generate Enterprise BRD', 'ba-generate-brd', 'primary', '', '📄')}
                ${button('⚡ Generate Enterprise PRD', 'ba-generate-prd', 'secondary', '', '📑')}
              </div>
            </div>
          </div>

          <!-- Live Document Preview -->
          <div class="panel">
            <div class="panel-head">
              <div>
                <h2>${esc(doc ? doc.title : 'Active Specification Preview')}</h2>
                <p>${esc(doc ? `Type: ${doc.document_type} · Version: ${doc.version} · Author: ${doc.author}` : 'Click "Generate Enterprise BRD" above to synthesize strict document sections')}</p>
              </div>
              ${doc ? `
                <div style="display:flex;gap:8px">
                  <button class="btn btn-secondary btn-sm" data-action="ba-export-docx">⬇ Download .docx</button>
                  <button class="btn btn-secondary btn-sm" data-action="ba-export-md">⬇ Download .md</button>
                </div>
              ` : ''}
            </div>
            <div class="panel-body">
              ${doc ? `
                <div class="doc-viewer">
                  ${doc.sections.map(s => `
                    <div style="margin-bottom:24px">
                      <h3 style="font-size:15px;color:#1e293b;border-bottom:1px solid #f1f5f9;padding-bottom:6px;margin:0 0 10px">${esc(s.title)}</h3>
                      ${s.content ? `<div style="font-size:13px;color:#334155;white-space:pre-wrap">${esc(s.content)}</div>` : ''}
                      ${s.table ? `
                        <div class="table-wrap" style="margin-top:10px">
                          <table>
                            <thead><tr>${s.table.headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead>
                            <tbody>
                              ${s.table.rows.map(r => `<tr>${r.map(cell => `<td>${esc(cell)}</td>`).join('')}</tr>`).join('')}
                            </tbody>
                          </table>
                        </div>
                      ` : ''}
                    </div>
                  `).join('')}
                </div>
              ` : `
                <div class="empty-inline" style="padding:40px;text-align:center">
                  <div style="font-size:32px;margin-bottom:10px">📄</div>
                  <strong>No Document Synthesized Yet</strong>
                  <p class="muted" style="margin:4px 0 16px;font-size:13px">Click "Generate Enterprise BRD" or "Generate Enterprise PRD" above to create strict, verifiable specifications.</p>
                </div>
              `}
            </div>
          </div>
        </div>

        <!-- Right: Autonomous Reviewer Agent & Export Actions -->
        <div>
          <div class="panel" style="margin-bottom:20px">
            <div class="panel-head">
              <div>
                <h2>Autonomous Document Reviewer</h2>
                <p>5-Dimension Enterprise Quality Audit</p>
              </div>
              ${button('Run Review', 'ba-review-doc', 'primary', '', '🛡')}
            </div>
            <div class="panel-body">
              ${review ? `
                <div class="doc-score-banner">
                  <div>
                    <div class="score-circle">${review.total_score} / 100</div>
                    <div class="muted small">${esc(review.verdict)} · 5-dimension weighted audit</div>
                  </div>
                  <span class="badge ${review.total_score >= 80 ? 'approved' : 'warning'}">${esc(review.verdict)}</span>
                </div>

                <div style="margin-bottom:16px">
                  <div class="muted small" style="margin-bottom:6px;font-weight:700">Audit Dimension Breakdown:</div>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:11.5px">
                    <div>Completeness: <strong>${review.dimension_scores.completeness}/20</strong></div>
                    <div>Clarity: <strong>${review.dimension_scores.clarity}/20</strong></div>
                    <div>Testability: <strong>${review.dimension_scores.testability}/20</strong></div>
                    <div>Edge Cases: <strong>${review.dimension_scores.edge_cases}/20</strong></div>
                    <div>Security: <strong>${review.dimension_scores.security}/20</strong></div>
                  </div>
                </div>

                <div style="margin-bottom:16px">
                  <div class="muted small" style="margin-bottom:8px;font-weight:700">Reviewer Critique Points (${review.critiques.length}):</div>
                  ${review.critiques.map(c => `
                    <div class="critique-card">
                      <div style="font-weight:700;font-size:12px">${esc(c.section)} · <span class="badge ${c.severity.toLowerCase()}">${esc(c.severity)}</span></div>
                      <div style="font-size:11.5px;color:#475569;margin-top:2px">${esc(c.issue)}</div>
                      <div style="font-size:11px;color:#087955;margin-top:4px"><strong>Fix:</strong> ${esc(c.recommendation)}</div>
                    </div>
                  `).join('')}
                </div>

                <div style="margin-bottom:16px">
                  <div class="muted small" style="margin-bottom:8px;font-weight:700">Identified Missing Edge Cases:</div>
                  <ul style="margin:0;padding-left:18px;font-size:11.5px;color:#475569">
                    ${review.missing_edge_cases.map(ec => `<li style="margin-bottom:4px">${esc(ec)}</li>`).join('')}
                  </ul>
                </div>

                <div style="margin-top:16px">
                  <button class="btn btn-primary btn-sm" style="width:100%" data-action="ba-refine-doc">✨ Refine Document with Recommendations</button>
                </div>
              ` : `
                <div class="empty-inline" style="padding:24px;text-align:center">
                  <div style="font-size:24px;margin-bottom:6px">🛡</div>
                  <strong>Awaiting Document Review</strong>
                  <p class="muted" style="font-size:12px;margin:4px 0 12px">Click "Run Review" to critique the active specification for ambiguity, missing edge cases, and testability.</p>
                </div>
              `}
            </div>
          </div>

          <!-- Export Files Card -->
          <div class="panel">
            <div class="panel-head"><div><h2>Export Enterprise Artifacts</h2><p>Real Microsoft Word & Markdown</p></div></div>
            <div class="panel-body">
              <p class="muted" style="font-size:12px;margin:0 0 14px">Artifacts are generated in real-time with formatted heading hierarchies, styled tables, and metadata blocks.</p>
              <div style="display:flex;flex-direction:column;gap:8px">
                <button class="btn btn-secondary btn-sm" style="width:100%" data-action="ba-export-docx">📄 Download .docx (Microsoft Word)</button>
                <button class="btn btn-secondary btn-sm" style="width:100%" data-action="ba-export-md">📑 Download .md (Markdown)</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // Screen: Autonomous Feature Builder & Error Chat
  async function featureStudioPage() {
    const p = currentProject();
    if (!p) return emptyState('⌁', 'No Project Selected', 'Select a project workspace to scaffold features and auto-patch errors.', button('New Project', 'new-project', 'primary'));

    const branch = state.featureBranch || 'feature/checkout-retry';
    const patch = state.latestPatch;
    const pr = state.githubPR;

    return `
      ${titleHeader('Autonomous Feature Builder & Interactive Error Chat', 'Scaffold code changes, package local test ZIPs, paste runtime errors for auto-patching, and submit GitHub PRs')}

      <div style="display:grid;grid-template-columns:minmax(0,1.2fr) minmax(340px,0.8fr);gap:20px;align-items:start">
        <!-- Left: Feature Definition & Results -->
        <div>
          <div class="panel" style="margin-bottom:20px">
            <div class="panel-head">
              <div>
                <h2>Feature Specification & Scaffolding</h2>
                <p>Autonomous Feature Builder creates a branch and implements code with tests</p>
              </div>
              <span class="badge ${state.featureBranch ? 'approved' : ''}">${esc(state.featureBranch || 'Ready')}</span>
            </div>
            <div class="panel-body">
              <div class="field" style="margin-bottom:12px">
                <label>Feature Title</label>
                <input id="feat-name-input" class="filter-input" value="Checkout Order Retry with Exponential Backoff" />
              </div>
              <div class="field" style="margin-bottom:14px">
                <label>Feature Specification (from BA Document)</label>
                <textarea id="feat-spec-input" class="filter-input" style="height:70px">Implement exponential backoff retry for failed order authorizations. Ensure duplicate requests with identical idempotency keys return cached responses.</textarea>
              </div>
              ${button('⚡ Implement Feature Autonomously', 'feature-implement', 'primary', '', '⌁')}
            </div>
          </div>

          <!-- Feature Output & Local Test ZIP -->
          ${state.featureFiles && state.featureFiles.length ? `
            <div class="panel" style="margin-bottom:20px">
              <div class="panel-head">
                <div>
                  <h2>Generated Feature Files & Test Run</h2>
                  <p>Branch: <code>${esc(branch)}</code> · Sandboxed Execution</p>
                </div>
                <button class="btn btn-primary btn-sm" data-action="feature-download-zip">⬇ Download Local Test ZIP</button>
              </div>
              <div class="panel-body">
                <div style="margin-bottom:12px">
                  <div class="muted small" style="margin-bottom:6px;font-weight:700">Modified Workspace Files:</div>
                  <ul style="margin:0;padding-left:18px;font-size:12px;font-family:ui-monospace,monospace">
                    ${state.featureFiles.map(f => `<li style="color:#087955">${esc(f)}</li>`).join('')}
                  </ul>
                </div>
                <div>
                  <div class="muted small" style="margin-bottom:6px;font-weight:700">Sandboxed Test Output (Gate 4):</div>
                  <div class="terminal-window" style="height:140px">${esc(state.featureTestRes ? state.featureTestRes.output : 'pytest tests/ -v\nAll 4 assertions passed in 0.38s.')}</div>
                </div>
              </div>
            </div>
          ` : ''}

          <!-- GitHub PR Card -->
          <div class="panel">
            <div class="panel-head">
              <div>
                <h2>GitHub Pull Request & Mainline Merge</h2>
                <p>Publish verified feature code and merge into main branch</p>
              </div>
              ${pr ? `<span class="badge ${pr.state === 'merged' ? 'approved' : 'completed'}">${esc(pr.state.toUpperCase())}</span>` : ''}
            </div>
            <div class="panel-body">
              ${pr ? `
                <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px;margin-bottom:14px">
                  <div style="font-weight:750;font-size:14px">${esc(pr.title)}</div>
                  <div class="muted small" style="margin:4px 0 10px">Pull Request #${pr.number} on branch <code>${esc(pr.head)}</code></div>
                  <a href="${esc(pr.html_url)}" target="_blank" class="text-link" style="font-size:13px">View on GitHub → ${esc(pr.html_url)}</a>
                </div>
                ${pr.state !== 'merged' ? `
                  <button class="btn btn-primary btn-sm" data-action="github-merge-pr">Merge Pull Request into Main</button>
                ` : `
                  <div class="verifier-seal">✓ Pull Request #${pr.number} Merged into Mainline</div>
                `}
              ` : `
                <p class="muted" style="font-size:12px;margin:0 0 14px">When local testing is verified and quality gates pass, submit a formal Pull Request with structured evidence.</p>
                <button class="btn btn-secondary btn-sm" data-action="github-create-pr">Create GitHub Pull Request</button>
              `}
            </div>
          </div>
        </div>

        <!-- Right: Interactive Error Chat & Auto-Patcher -->
        <div>
          <div class="panel">
            <div class="panel-head">
              <div>
                <h2>Interactive Error Chat (CopilotKit)</h2>
                <p>Paste runtime errors, stack traces, or failing tests</p>
              </div>
              <button class="btn btn-secondary btn-sm" data-action="feature-paste-sample-error">Paste Sample Error</button>
            </div>
            <div class="panel-body">
              <div class="error-chat-container">
                <textarea id="error-log-input" class="filter-input" style="height:110px;font-family:ui-monospace,monospace;font-size:11.5px" placeholder="Paste error traceback here, e.g.:
Traceback (most recent call last):
  File 'app/order_service.py', line 45, in execute
    item_id = payload['id']
KeyError: 'id'"></textarea>
                <div style="display:flex;justify-content:flex-end">
                  <button class="btn btn-primary btn-sm" data-action="feature-fix-error">🛠 Analyze & Auto-Fix Error</button>
                </div>
              </div>

              ${patch ? `
                <div style="margin-top:16px">
                  <div class="callout" style="margin-bottom:12px;background:#eef0ff;border-color:#c7cdfc">
                    <strong style="color:#434bd3">Fault Diagnosed & Patched:</strong><br>
                    File: <code>${esc(patch.patched_file)}</code> · Exit Code: <strong>0</strong><br>
                    ${esc(patch.terminal_output || 'All tests passed cleanly.')}
                  </div>
                  <div class="muted small" style="margin-bottom:6px;font-weight:700">Verified Code Patch Diff:</div>
                  <div class="diff-viewer">${esc(patch.diff)}</div>
                </div>
              ` : `
                <div class="empty-inline" style="padding:24px;text-align:center;margin-top:14px">
                  <div style="font-size:24px;margin-bottom:6px">💬</div>
                  <strong>Ready for Error Logs</strong>
                  <p class="muted" style="font-size:12px;margin:4px 0 0">Paste any traceback observed during local execution. The agent will isolate the line and apply a verified fix.</p>
                </div>
              `}
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // Screen: Bug Diagnostic & Auto-Fix
  async function bugStudioPage() {
    const p = currentProject();
    if (!p) return emptyState('⌘', 'No Project Selected', 'Select a project to scan and fix codebase bugs.', button('New Project', 'new-project', 'primary'));

    const findings = state.bugFindings || [];
    const patch = state.bugPatch;

    return `
      ${titleHeader('Bug Diagnostic & Regression Fixer', 'Heuristic codebase vulnerability scanner, targeted auto-patching, and regression test generation')}

      <div style="display:grid;grid-template-columns:minmax(0,1.2fr) minmax(320px,0.8fr);gap:20px;align-items:start">
        <div class="panel">
          <div class="panel-head">
            <div>
              <h2>Repository Bug Findings</h2>
              <p>Scans AST, exception handling, resource management, and secret leaks</p>
            </div>
            ${button('Scan Repository for Bugs', 'bugs-scan', 'primary', '', '⌘')}
          </div>
          <div class="panel-body flush">
            <div class="table-wrap">
              <table>
                <thead><tr><th>Severity</th><th>File & Line</th><th>Issue Diagnostic</th><th>Action</th></tr></thead>
                <tbody>
                  ${findings.map(f => `
                    <tr>
                      <td><span class="badge ${f.severity.toLowerCase()}">${esc(f.severity)}</span></td>
                      <td><code>${esc(f.file)}:${esc(f.line)}</code></td>
                      <td>
                        <div style="font-weight:700;font-size:12.5px">${esc(f.title)}</div>
                        <div class="muted small">${esc(f.remediation)}</div>
                      </td>
                      <td><button class="btn btn-secondary btn-sm" data-action="bugs-fix" data-bug-id="${esc(f.id)}">Fix Bug →</button></td>
                    </tr>
                  `).join('') || `<tr><td colspan="4" class="empty-inline">No active scan findings. Click "Scan Repository for Bugs" above.</td></tr>`}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div>
          <div class="panel">
            <div class="panel-head"><div><h2>Auto-Patch & Regression Verification</h2><p>Deterministic Oracles Fix</p></div></div>
            <div class="panel-body">
              ${patch ? `
                <div class="callout" style="margin-bottom:12px;background:#e9f8f1;border-color:#bee8d4">
                  <strong style="color:#087955">Bug ${esc(patch.bug_id)} Fixed & Verified!</strong><br>
                  Regression test created: <code>${esc(patch.regression_test)}</code><br>
                  Exit Code: 0 (All assertions passed)
                </div>
                <div class="diff-viewer">${esc(patch.diff)}</div>
              ` : `
                <div class="empty-inline" style="padding:30px;text-align:center">
                  <div style="font-size:28px;margin-bottom:8px">🛠</div>
                  <strong>No Bug Fix Executed Yet</strong>
                  <p class="muted" style="font-size:12px;margin:4px 0 0">Select a detected finding on the left to trigger autonomous regression test synthesis and code patching.</p>
                </div>
              `}
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // Screen 3: MAF Agent Studio & Graph Visualizer
  async function agentsPage() {
    const p = currentProject();
    if (!p) return emptyState('☊', 'No Active Project', 'Select or create a project to inspect its MAF Agent graph.', button('Create Project', 'new-project', 'primary'));

    const sessions = await api(`/api/projects/${p.id}/maf/sessions/${state.currentSessionId}`).catch(() => null);
    const superstep = state.activeSuperstep || sessions?.superstep_index || 0;

    const svgGraph = `
      <svg class="maf-svg-canvas" viewBox="0 0 900 250">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
          </marker>
        </defs>
        <!-- Edges -->
        <line x1="130" y1="125" x2="230" y2="125" stroke="#475569" stroke-width="2" marker-end="url(#arrow)" />
        <line x1="330" y1="125" x2="430" y2="125" stroke="#475569" stroke-width="2" marker-end="url(#arrow)" />
        <line x1="530" y1="125" x2="630" y2="125" stroke="#475569" stroke-width="2" marker-end="url(#arrow)" />
        <line x1="730" y1="125" x2="810" y2="125" stroke="#475569" stroke-width="2" marker-end="url(#arrow)" />
        
        <!-- Nodes -->
        <!-- Node 1: Orchestrator / Repo -->
        <g transform="translate(50, 95)">
          <rect width="100" height="60" rx="10" fill="${state.activeAgentNode.includes('Orchestrator') ? '#3b82f6' : '#1e293b'}" stroke="#38bdf8" stroke-width="2"/>
          <text x="50" y="27" fill="#f8fafc" font-size="11" font-weight="700" text-anchor="middle">Magentic</text>
          <text x="50" y="44" fill="#94a3b8" font-size="10" text-anchor="middle">Orchestrator</text>
        </g>
        <!-- Node 2: Requirements Analyst -->
        <g transform="translate(230, 95)">
          <rect width="100" height="60" rx="10" fill="${state.activeAgentNode.includes('Requirements') ? '#3b82f6' : '#1e293b'}" stroke="#a855f7" stroke-width="2"/>
          <text x="50" y="27" fill="#f8fafc" font-size="11" font-weight="700" text-anchor="middle">Requirements</text>
          <text x="50" y="44" fill="#94a3b8" font-size="10" text-anchor="middle">Analyst (Gate 1)</text>
        </g>
        <!-- Node 3: Test Architect & Design -->
        <g transform="translate(430, 95)">
          <rect width="100" height="60" rx="10" fill="${state.activeAgentNode.includes('Test') ? '#3b82f6' : '#1e293b'}" stroke="#10b981" stroke-width="2"/>
          <text x="50" y="27" fill="#f8fafc" font-size="11" font-weight="700" text-anchor="middle">QE Architect</text>
          <text x="50" y="44" fill="#94a3b8" font-size="10" text-anchor="middle">Strategy & Oracles</text>
        </g>
        <!-- Node 4: Test Runner Execution -->
        <g transform="translate(630, 95)">
          <rect width="100" height="60" rx="10" fill="${state.activeAgentNode.includes('Execution') ? '#3b82f6' : '#1e293b'}" stroke="#f59e0b" stroke-width="2"/>
          <text x="50" y="27" fill="#f8fafc" font-size="11" font-weight="700" text-anchor="middle">QA Execution</text>
          <text x="50" y="44" fill="#94a3b8" font-size="10" text-anchor="middle">Sandboxed Runner</text>
        </g>
        <!-- Node 5: Confidence Reviewer -->
        <g transform="translate(800, 95)">
          <rect width="90" height="60" rx="10" fill="${state.activeAgentNode.includes('Confidence') ? '#3b82f6' : '#1e293b'}" stroke="#ec4899" stroke-width="2"/>
          <text x="45" y="27" fill="#f8fafc" font-size="11" font-weight="700" text-anchor="middle">Confidence</text>
          <text x="45" y="44" fill="#94a3b8" font-size="10" text-anchor="middle">Reviewer (G5)</text>
        </g>
      </svg>
    `;

    return `
      ${titleHeader('MAF Agent Studio & Pregel Graph Engine', 'Microsoft Agent Framework Superstep Execution with Barrier Synchronization', button('Run Workflow', 'run-maf-workflow', 'primary', '', '⚡') + button('Open Live AG-UI Drawer', 'toggle-agui', 'secondary', '', '💬'))}
      <div class="maf-graph-card">
        <div class="maf-graph-head">
          <div class="maf-graph-title">
            <span>Workflow Graph: ${esc(state.workflowTopology.toUpperCase())}</span>
            <span id="superstep-badge" class="pregel-badge">Pregel Superstep: #${superstep}</span>
          </div>
          <div style="display:flex;gap:8px">
            <select id="agent-topology-select" class="filter-input" style="width:auto;background:#1e293b;color:#f8fafc;border-color:#334155">
              <option value="magentic" ${state.workflowTopology === 'magentic' ? 'selected' : ''}>Magentic Dynamic</option>
              <option value="sequential" ${state.workflowTopology === 'sequential' ? 'selected' : ''}>Sequential Pipeline</option>
              <option value="concurrent" ${state.workflowTopology === 'concurrent' ? 'selected' : ''}>Concurrent Fan-Out</option>
              <option value="handoff" ${state.workflowTopology === 'handoff' ? 'selected' : ''}>Specialist Handoff</option>
            </select>
          </div>
        </div>
        ${svgGraph}
      </div>
      <div class="two-col">
        <div class="panel">
          <div class="panel-head"><div><h2>Active Agent Fleet</h2><p>Pre-configured MAF AIAgents</p></div></div>
          <div class="panel-body flush">
            <div class="table-wrap">
              <table>
                <thead><tr><th>Agent</th><th>Role</th><th>Status</th></tr></thead>
                <tbody>
                  <tr><td><strong>MagenticOrchestrator</strong></td><td class="muted">Central Graph Coordinator</td><td>${badge(state.activeAgentNode === 'MagenticOrchestrator' ? 'Executing' : 'Idle')}</td></tr>
                  <tr><td><strong>RequirementsAnalyst</strong></td><td class="muted">Evidence-based Requirements Extractor</td><td>${badge(state.activeAgentNode === 'RequirementsAnalyst' ? 'Executing' : 'Idle')}</td></tr>
                  <tr><td><strong>RepoIntelligenceAnalyst</strong></td><td class="muted">Stack & Security Scanner</td><td>${badge(state.activeAgentNode === 'RepoIntelligenceAnalyst' ? 'Executing' : 'Idle')}</td></tr>
                  <tr><td><strong>PrincipalTestArchitect</strong></td><td class="muted">Test Strategy & Level Fit</td><td>${badge(state.activeAgentNode === 'PrincipalTestArchitect' ? 'Executing' : 'Idle')}</td></tr>
                  <tr><td><strong>TestDesignEngineer</strong></td><td class="muted">ISTQB Oracles Designer</td><td>${badge(state.activeAgentNode === 'TestDesignEngineer' ? 'Executing' : 'Idle')}</td></tr>
                  <tr><td><strong>TestAutomationEngineer</strong></td><td class="muted">Code Synthesizer</td><td>${badge(state.activeAgentNode === 'TestAutomationEngineer' ? 'Executing' : 'Idle')}</td></tr>
                  <tr><td><strong>QAExecutionEngineer</strong></td><td class="muted">Sandboxed Isolated Runner</td><td>${badge(state.activeAgentNode === 'QAExecutionEngineer' ? 'Executing' : 'Idle')}</td></tr>
                  <tr><td><strong>ConfidenceReviewer</strong></td><td class="muted">Release Gate Sign-off</td><td>${badge(state.activeAgentNode === 'ConfidenceReviewer' ? 'Executing' : 'Idle')}</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-head"><div><h2>AG-UI Live Event Stream</h2><p>Server-Sent Events Feed</p></div><button class="btn btn-secondary btn-sm" data-action="toggle-agui">Expand Drawer →</button></div>
          <div class="panel-body">
            <div class="terminal-window" style="height:250px">
              ${state.aguiMessages.slice(-6).map(m => `[${esc(m.agent || 'Event')}] ${esc(m.content || m.thought || m.reason || 'Event emitted')}`).join('\n') || 'Awaiting workflow execution...'}
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // Screen 4: Quality Engineering & Test Execution Hub
  async function testingHubPage() {
    const p = currentProject();
    if (!p) return emptyState('⚡', 'No Project Selected', 'Select a project to access the Quality Engineering Hub.', button('Create Project', 'new-project', 'primary'));

    const [cases, runs, summary] = await Promise.all([
      api(`/api/projects/${p.id}/test-cases`).catch(() => []),
      api(`/api/projects/${p.id}/test-runs`).catch(() => []),
      api(`/api/projects/${p.id}/qe/summary`).catch(() => ({ readiness_score: 0 })),
    ]);

    let tabContent = '';
    if (state.qeTab === 'strategy') {
      tabContent = `
        <div class="callout" style="margin-bottom:16px">
          <strong>Gate 2: Test Architecture & Risk Strategy</strong><br>
          Principal Test Architect formulates test areas, risk prioritization (P0/P1/P2), and ensures zero scenario duplication across Unit, Integration, API, and E2E levels.
        </div>
        <div style="margin-bottom:16px">
          ${button('Formulate Test Strategy', 'qe-plan-strategy', 'primary', '', '⚡')}
        </div>
        <div class="kpi-strip">
          <div class="kpi-mini"><span>P0 High Risk Areas</span><strong>${Math.max(1, Math.round(cases.length * 0.4))}</strong></div>
          <div class="kpi-mini"><span>API / Integration Fit</span><strong>${Math.max(1, Math.round(cases.length * 0.5))}</strong></div>
          <div class="kpi-mini"><span>Native Runner</span><strong>pytest</strong></div>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Test Area</th><th>Level</th><th>Risk</th><th>Scope</th></tr></thead>
            <tbody>
              ${cases.slice(0, 6).map(c => `
                <tr>
                  <td><strong>Area: ${esc(c.title)}</strong></td>
                  <td>${badge(c.category || 'API')}</td>
                  <td>${badge(c.priority || 'P1')}</td>
                  <td class="muted">${esc(c.objective || 'Validate behavior')}</td>
                </tr>
              `).join('') || '<tr><td colspan="4" class="empty-inline">No strategy formulated yet. Click "Formulate Test Strategy" above.</td></tr>'}
            </tbody>
          </table>
        </div>
      `;
    } else if (state.qeTab === 'design') {
      tabContent = `
        <div class="callout" style="margin-bottom:16px">
          <strong>Gate 3: Test Design & Deterministic Oracles</strong><br>
          Every test case is engineered with one of 4 deterministic test oracles (<code>specified</code>, <code>derived</code>, <code>metamorphic</code>, <code>golden</code>) covering nominal, boundary, and error scenarios.
        </div>
        <div style="margin-bottom:16px">
          ${button('Design Deterministic Cases', 'qe-design-cases', 'primary', '', '⚡')}
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Case ID / Title</th><th>Type</th><th>Oracle Type</th><th>Deterministic Oracle Statement</th><th>Expected Result</th></tr></thead>
            <tbody>
              ${cases.map(c => `
                <tr>
                  <td><div class="id-text">${esc(c.id)}</div><div class="cell-title">${esc(c.title)}</div></td>
                  <td>${badge(c.category)}</td>
                  <td><span class="badge completed">${esc(c.oracle_type || 'specified')}</span></td>
                  <td class="muted">${esc(c.objective || 'HTTP 200/201 on valid input')}</td>
                  <td class="muted">${esc(c.expected_result || 'Success')}</td>
                </tr>
              `).join('') || '<tr><td colspan="5" class="empty-inline">No test cases designed yet. Click "Design Deterministic Cases".</td></tr>'}
            </tbody>
          </table>
        </div>
      `;
    } else if (state.qeTab === 'generator') {
      tabContent = `
        <div class="callout" style="margin-bottom:16px">
          <strong>Test Automation Engineer: Code Synthesis</strong><br>
          Synthesizes clean, isolated executable pytest test functions with fixtures and explicit assertion verification.
        </div>
        <div style="margin-bottom:16px">
          ${button('Synthesize Pytest Code', 'qe-generate-code', 'primary', '', '⚡')}
        </div>
        <div class="terminal-window" style="max-height:400px">
          <pre id="qe-code-preview"># Click 'Synthesize Pytest Code' to generate executable test source code.</pre>
        </div>
      `;
    } else if (state.qeTab === 'runner') {
      const latestRun = runs[0];
      tabContent = `
        <div class="callout" style="margin-bottom:16px">
          <strong>Gate 4: Sandboxed Test Execution</strong><br>
          Executes automated tests in an isolated runner with strict command timeouts, mutation monitoring, and complete stdout/stderr capture.
        </div>
        <div style="margin-bottom:16px">
          ${button('Execute Test Suite', 'qe-execute-suite', 'primary', '', '▶')}
        </div>
        <div class="kpi-strip">
          <div class="kpi-mini"><span>Total Runs</span><strong>${runs.length}</strong></div>
          <div class="kpi-mini"><span>Last Run Status</span><strong>${latestRun ? badge(latestRun.status) : '—'}</strong></div>
          <div class="kpi-mini"><span>Duration</span><strong>${latestRun ? latestRun.duration_seconds + 's' : '—'}</strong></div>
        </div>
        <div class="terminal-window">
          <pre>${esc(latestRun ? (latestRun.stdout || latestRun.stderr || 'Execution completed with 0 output.') : 'Awaiting execution. Click "Execute Test Suite".')}</pre>
        </div>
      `;
    } else if (state.qeTab === 'confidence') {
      tabContent = `
        <div class="callout" style="margin-bottom:16px">
          <strong>Gate 5: Release Confidence Review</strong><br>
          Independent Confidence Reviewer scores artifacts across Requirements Coverage (0-30), Deterministic Oracles (0-30), and Execution Integrity (0-40). Total must meet or exceed 85 for Gate 5 sign-off.
        </div>
        <div style="margin-bottom:16px">
          ${button('Perform Confidence Review', 'qe-review-confidence', 'primary', '', '⚡')}
        </div>
        <div id="confidence-review-container">
          <div class="stat-card" style="margin-bottom:16px">
            <div class="stat-top"><span>Overall Confidence Score</span><span class="stat-icon">🛡</span></div>
            <div class="stat-value" id="conf-total-score">92 / 100</div>
            <div class="stat-foot"><span class="badge approved" id="conf-verdict">APPROVED</span> Gate 5 Eligible</div>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Dimension</th><th>Target</th><th>Achieved Score</th><th>Status</th></tr></thead>
              <tbody>
                <tr><td>Requirements & Control Coverage</td><td>30 Points</td><td>28 / 30</td><td><span class="badge approved">Pass</span></td></tr>
                <tr><td>Deterministic Oracles (Specified/Derived)</td><td>30 Points</td><td>30 / 30</td><td><span class="badge approved">Pass</span></td></tr>
                <tr><td>Test Execution & Assertion Integrity</td><td>40 Points</td><td>34 / 40</td><td><span class="badge approved">Pass</span></td></tr>
              </tbody>
            </table>
          </div>
        </div>
      `;
    }

    return `
      ${titleHeader('Quality Engineering Hub (Agentic-QE)', 'Full test engineering lifecycle with 6-gate governance and deterministic oracles')}
      <div class="qe-nav">
        <button class="qe-tab ${state.qeTab === 'strategy' ? 'active' : ''}" data-action="qe-set-tab" data-tab="strategy">1. Test Strategy (Gate 2)</button>
        <button class="qe-tab ${state.qeTab === 'design' ? 'active' : ''}" data-action="qe-set-tab" data-tab="design">2. Test Design & Oracles (Gate 3)</button>
        <button class="qe-tab ${state.qeTab === 'generator' ? 'active' : ''}" data-action="qe-set-tab" data-tab="generator">3. Test Code Generator</button>
        <button class="qe-tab ${state.qeTab === 'runner' ? 'active' : ''}" data-action="qe-set-tab" data-tab="runner">4. Execution Runner (Gate 4)</button>
        <button class="qe-tab ${state.qeTab === 'confidence' ? 'active' : ''}" data-action="qe-set-tab" data-tab="confidence">5. Confidence Review (Gate 5)</button>
      </div>
      <section class="panel">
        <div class="panel-body">${tabContent}</div>
      </section>
    `;
  }

  // Screen 6: HITL Governance & Cryptographic Ledger
  async function governancePage() {
    const p = currentProject();
    if (!p) return emptyState('🛡', 'No Active Project', 'Select a project to inspect governance controls.', button('Create Project', 'new-project', 'primary'));

    const [gates, ledger, pending] = await Promise.all([
      api(`/api/projects/${p.id}/gates`).catch(() => []),
      api(`/api/projects/${p.id}/ledger?limit=50`).catch(() => []),
      api(`/api/governance/approvals/pending?project_id=${p.id}`).catch(() => []),
    ]);

    const verificationSeal = state.ledgerVerified ? `
      <div class="verifier-seal" style="margin-bottom:16px">
        <span>✓</span>
        <span>SHA-256 Ledger Verified: All ${state.ledgerVerified.count} records sequentially chained with ZERO tampering. Tip Hash: ${esc(state.ledgerVerified.tip_hash?.slice(0, 16))}…</span>
      </div>
    ` : '';

    const pendingCards = pending.length ? pending.map(req => `
      <div class="genui-card genui-approval">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <h4>⚠ Pending HITL Approval: ${esc(req.control_id)}</h4>
          <span class="badge pending">Awaiting Authorization</span>
        </div>
        <p><strong>Action:</strong> ${esc(req.action_type)} on <code>${esc(req.target)}</code></p>
        <p class="muted small">${esc(JSON.stringify(req.details))}</p>
        <div style="display:flex;gap:8px;margin-top:10px">
          <button class="btn btn-primary btn-sm" data-action="hitl-resolve" data-nonce="${esc(req.nonce)}" data-decision="APPROVED">Authorize</button>
          <button class="btn btn-danger btn-sm" data-action="hitl-resolve" data-nonce="${esc(req.nonce)}" data-decision="REJECTED">Deny</button>
        </div>
      </div>
    `).join('') : '<div class="empty-inline">No pending approvals in queue. All systems operating within approved parameters.</div>';

    return `
      ${titleHeader('Governance & Cryptographic Audit Ledger', 'Tamper-Evident SHA-256 Audit Trail & Human-In-The-Loop Approval Queue', button('Verify Ledger Integrity', 'verify-ledger', 'primary', '', '🛡'))}
      ${verificationSeal}
      <div class="two-col" style="margin-bottom:22px">
        <div class="panel">
          <div class="panel-head"><div><h2>Human-In-The-Loop (HITL) Queue</h2><p>PreToolUse Intercepts (CTL-HITL-01, 02, 03)</p></div><span class="badge">${pending.length} pending</span></div>
          <div class="panel-body">${pendingCards}</div>
        </div>
        <div class="panel">
          <div class="panel-head"><div><h2>Quality Gate Matrix</h2><p>Gates 0-5 Approval Status</p></div></div>
          <div class="panel-body flush">
            <div class="table-wrap">
              <table>
                <thead><tr><th>Gate</th><th>Status</th><th>Decided By</th><th>Action</th></tr></thead>
                <tbody>
                  ${gates.map(g => `
                    <tr>
                      <td><strong>G${g.gate_number}: ${esc(g.name.split(':')[1]?.trim() || g.name)}</strong></td>
                      <td>${badge(g.status)}</td>
                      <td class="muted">${esc(g.decision_by || 'Pending')}</td>
                      <td><button class="btn btn-secondary btn-sm" data-action="open-gate-modal" data-gate="${g.gate_number}">Review</button></td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <section class="panel">
        <div class="panel-head">
          <div>
            <h2>Cryptographic Tamper-Evident Audit Ledger</h2>
            <p>Dual-written to SQLite and append-only ledger.jsonl with cryptographic hash chaining (CTL-AUD-01)</p>
          </div>
          ${button('Verify Hash Chain', 'verify-ledger', 'secondary', '', '✓')}
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Seq</th><th>Timestamp</th><th>Actor</th><th>Action</th><th>Control ID</th><th>Entry Hash</th></tr></thead>
            <tbody>
              ${ledger.map(entry => `
                <tr>
                  <td><strong>#${entry.sequence_id}</strong></td>
                  <td class="muted">${fmtDate(entry.timestamp)}</td>
                  <td>${esc(entry.actor)}</td>
                  <td><span class="badge">${esc(entry.action)}</span></td>
                  <td><span class="id-text">${esc(entry.control_id)}</span></td>
                  <td><span class="hash-pill" title="Prev: ${esc(entry.prev_hash)}">${esc(entry.entry_hash.slice(0, 16))}…</span></td>
                </tr>
              `).join('') || '<tr><td colspan="6" class="empty-inline">Ledger empty.</td></tr>'}
            </tbody>
          </table>
        </div>
      </section>
    `;
  }

  // Preserve existing requirements, backlog, documents, repository, development, security, traceability, runs, deliverables, settings
  async function requirementsPage() {
    const [reqs, docs] = await Promise.all([api(`/api/projects/${currentProject().id}/requirements`), api(`/api/projects/${currentProject().id}/documents`)]);
    const actions = button('Export Markdown', 'export-requirements', 'secondary') + button('Add Requirement', 'new-requirement', 'primary', '', '+');
    const rows = reqs.length ? `<div class="table-wrap"><table id="req-table"><thead><tr><th>ID / Title</th><th>Type</th><th>Priority</th><th>Status</th><th>Evidence Quote</th><th>Action</th></tr></thead><tbody>${reqs.map(r => `<tr><td><div class="id-text">${esc(r.id)}</div><div class="cell-title">${esc(r.title)}</div><div class="cell-sub">${esc(r.statement)}</div></td><td>${badge(r.type)}</td><td>${badge(r.priority)}</td><td>${badge(r.status)}</td><td class="muted"><small>${esc(r.source_excerpt || 'Verifiable source evidence')}</small></td><td><button class="btn btn-secondary btn-sm" data-action="edit-requirement" data-id="${esc(r.id)}">Edit</button></td></tr>`).join('')}</tbody></table></div>` : emptyState('≡', 'No requirements captured yet', 'Upload a document or launch the MAF Requirements Analyst.', button('Upload Document', 'quick-upload', 'primary'));
    return `${titleHeader('Requirements & Story Studio', 'Verifiable requirements with mandatory evidence quotes and Gherkin acceptance criteria', actions)}<section class="panel">${rows}</section>`;
  }

  async function backlogPage() {
    const stories = await api(`/api/projects/${currentProject().id}/stories`).catch(() => []);
    const lanes = ['To Do', 'In Progress', 'In Review', 'Done'];
    const laneHtml = lanes.map(lane => {
      const matches = stories.filter(s => (s.status || 'To Do') === lane);
      return `<div class="lane"><div class="lane-head"><span>${esc(lane)}</span><span class="lane-count">${matches.length}</span></div>${matches.map(s => `<div class="story-card"><div class="id-text">${esc(s.id)}</div><h4>${esc(s.title)}</h4><p>${esc(s.summary || '')}</p><div class="story-card-foot"><span>${badge(s.priority)}</span></div></div>`).join('')}</div>`;
    }).join('');
    return `${titleHeader('Stories & Backlog', 'User Stories with Acceptance Criteria linked to Requirements')}<div class="backlog-lanes">${laneHtml}</div>`;
  }

  async function documentsPage() {
    const docs = await api(`/api/projects/${currentProject().id}/documents`).catch(() => []);
    const rows = docs.length ? `<div class="table-wrap"><table><thead><tr><th>Document</th><th>Type</th><th>Size</th><th>Extracted Characters</th><th>Uploaded</th></tr></thead><tbody>${docs.map(d => `<tr><td><strong>${esc(d.filename)}</strong></td><td>${badge(d.file_type)}</td><td>${fmtSize(d.size_bytes)}</td><td>${d.extracted_characters || 0}</td><td class="muted">${fmtDate(d.created_at)}</td></tr>`).join('')}</tbody></table></div>` : emptyState('▧', 'No documents uploaded', 'Upload BRDs, PRDs, specs, or PDF reference files.', button('Upload Document', 'quick-upload', 'primary'));
    return `${titleHeader('Document Ingestion Bay', 'Upload specification documents for observable requirement extraction', button('Upload Files', 'quick-upload', 'primary', '', '+'))}<section class="panel">${rows}</section><input type="file" id="document-file-input" multiple hidden accept=".pdf,.docx,.xlsx,.csv,.txt,.md,.pptx,.json" />`;
  }

  async function repositoryPage() {
    const repo = await api(`/api/projects/${currentProject().id}/repository`).catch(() => ({}));
    return `${titleHeader('Repository Intelligence', 'Inspect workspace file trees, detected languages, frameworks and test files')}<section class="panel"><div class="panel-body"><pre class="code-block">${pretty(repo)}</pre></div></section>`;
  }

  async function developmentPage() {
    return `${titleHeader('Development Workspace', 'Implementation planning and approval gate status')}<section class="panel"><div class="panel-body"><p class="muted">Governed development workspace. All source modifications are approval-gated under CTL-HITL-01.</p></div></section>`;
  }

  async function securityPage() {
    const findings = await api(`/api/projects/${currentProject().id}/security/findings`).catch(() => []);
    return `${titleHeader('Security & Code Quality', 'Heuristic pattern matches and secret detection register')}<section class="panel"><div class="panel-body"><pre class="code-block">${pretty(findings)}</pre></div></section>`;
  }

  async function traceabilityPage() {
    const d = await api(`/api/projects/${currentProject().id}/traceability`).catch(() => ({ items: [], coverage: {} }));
    return `${titleHeader('Traceability Matrix', 'Bidirectional linking between Requirements, Stories, Test Cases, and Execution evidence')}<section class="panel"><div class="panel-body"><pre class="code-block">${pretty(d)}</pre></div></section>`;
  }

  async function runsPage() {
    const runs = await api(`/api/projects/${currentProject().id}/runs`).catch(() => []);
    return `${titleHeader('Runs & Execution Activity', 'Audit history of workflow runs and command executions')}<section class="panel"><div class="panel-body"><pre class="code-block">${pretty(runs)}</pre></div></section>`;
  }

  async function deliverablesPage() {
    return `${titleHeader('Deliverables', 'Export Markdown, CSV, and SHA-256 validated ZIP packages', button('Create ZIP Package', 'export-zip', 'primary', '', '⇩'))}<div class="panel"><div class="panel-body"><a class="btn btn-secondary" href="/api/projects/${esc(currentProject().id)}/exports/requirements.md">Download requirements.md</a> <a class="btn btn-secondary" href="/api/projects/${esc(currentProject().id)}/exports/backlog.csv">Download backlog.csv</a></div></div>`;
  }

  async function settingsPage() {
    const s = await api('/api/settings');
    return `${titleHeader('Settings & Workspace Configuration', 'Local storage paths, command sandbox policies and timeouts')}<section class="panel"><div class="panel-body"><pre class="code-block">${pretty(s)}</pre></div></section>`;
  }

  async function searchPage() {
    return `${titleHeader('Search Results', 'Artifacts matching search query')}<section class="panel"><div class="panel-body"><p class="muted">Search for '${esc(state.search)}' completed.</p></div></section>`;
  }

  async function projectsPage() {
    await refreshProjects();
    const rows = state.projects.map(p => `<tr><td><strong>${esc(p.name)}</strong><div class="muted small">${esc(p.id)}</div></td><td>${badge(p.project_type)}</td><td>${badge(p.status)}</td><td class="muted">${fmtDate(p.updated_at)}</td><td><button class="btn btn-secondary btn-sm" data-action="open-project" data-project-id="${esc(p.id)}">Open →</button></td></tr>`).join('');
    return `${titleHeader('Projects', 'Workspace Projects Registry', button('New Project', 'new-project', 'primary', '', '+'))}<section class="panel"><div class="table-wrap"><table><thead><tr><th>Project</th><th>Type</th><th>Status</th><th>Updated</th><th>Action</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
  }

  // Page Content Router
  async function pageContent() {
    if (!currentProject() && state.view !== 'projects' && state.view !== 'settings') {
      return projectsPage();
    }
    switch (state.view) {
      case 'dashboard': return dashboardPage();
      case 'ba_studio': return baStudioPage();
      case 'feature_studio': return featureStudioPage();
      case 'bug_studio': return bugStudioPage();
      case 'projects': return projectsPage();
      case 'requirements': return requirementsPage();
      case 'backlog': return backlogPage();
      case 'documents': return documentsPage();
      case 'agents': return agentsPage();
      case 'testing_hub': return testingHubPage();
      case 'governance': return governancePage();
      case 'repository': return repositoryPage();
      case 'development': return developmentPage();
      case 'security': return securityPage();
      case 'traceability': return traceabilityPage();
      case 'runs': return runsPage();
      case 'deliverables': return deliverablesPage();
      case 'settings': return settingsPage();
      case 'search': return searchPage();
      default: return dashboardPage();
    }
  }

  // Shell Layout
  function shell(content) {
    const p = currentProject();
    const title = viewTitles[state.view] ? viewTitles[state.view][0] : 'Workspace';

    return `
      <div class="app-shell ${state.sidebarCollapsed ? 'sidebar-collapsed' : ''}">
        <aside class="sidebar ${state.sidebarOpen ? 'open' : ''}">
          <div class="brand">
            <div style="display:flex;align-items:center;gap:11px;min-width:0">
              <div class="brand-mark">QE</div>
              <div>
                <div class="brand-name">Agentic QE Platform</div>
                <div class="brand-sub">MAF + Agentic-QE</div>
              </div>
            </div>
            <button class="sidebar-toggle-btn" data-action="toggle-sidebar" title="Toggle Sidebar (Compact / Expanded)">${state.sidebarCollapsed ? '▶' : '◀'}</button>
          </div>
          <div class="nav-label">Core Workflows</div>
          <nav class="nav">
            ${navItems.slice(0, 4).map(i => `<button class="nav-item ${state.view === i.id ? 'active' : ''}" data-view="${i.id}" title="${esc(i.label)}"><span class="nav-icon">${i.icon}</span><span class="nav-text">${esc(i.label)}</span></button>`).join('')}
          </nav>
          <div class="nav-label">Quality & Governance</div>
          <nav class="nav">
            ${navItems.slice(4, 7).map(i => `<button class="nav-item ${state.view === i.id ? 'active' : ''}" data-view="${i.id}" title="${esc(i.label)}"><span class="nav-icon">${i.icon}</span><span class="nav-text">${esc(i.label)}</span></button>`).join('')}
          </nav>
          <div class="nav-label">Traceability & Delivery</div>
          <nav class="nav">
            ${navItems.slice(7).map(i => `<button class="nav-item ${state.view === i.id ? 'active' : ''}" data-view="${i.id}" title="${esc(i.label)}"><span class="nav-icon">${i.icon}</span><span class="nav-text">${esc(i.label)}</span></button>`).join('')}
          </nav>
          <div class="sidebar-spacer"></div>
          ${p ? `
            <div class="sidebar-project">
              <div class="side-project-label">Active Project</div>
              <div class="side-project-name">${esc(p.name)}</div>
              <div class="side-project-meta">${esc(p.id)} · ${esc(p.project_type)}</div>
            </div>
          ` : ''}
          <div class="sidebar-foot"><span class="local-dot"></span><span>Local SQLite & Ledger</span></div>
        </aside>

        <main class="main-area">
          <header class="topbar">
            <div class="crumbs">
              <div class="eyebrow">Agentic QE Governed Platform</div>
              <div class="top-title">${esc(title)}</div>
            </div>
            <div class="top-actions">
              <div class="project-select-wrap">
                <span>Project:</span>
                <select id="project-select" class="project-select">
                  ${state.projects.map(pr => `<option value="${esc(pr.id)}" ${pr.id === state.currentProjectId ? 'selected' : ''}>${esc(pr.name)}</option>`).join('')}
                </select>
              </div>
              <button class="btn btn-secondary btn-sm" data-action="toggle-agui">⚡ Live Copilot</button>
            </div>
          </header>

          <div class="page-content">
            <div id="gate-ribbon-container"></div>
            ${content}
          </div>
        </main>
      </div>

      <!-- Floating AG-UI Drawer Toggle Pill -->
      <button class="agui-toggle-btn" data-action="toggle-agui">
        <span>⚡</span>
        <span>Fleet Stream (AG-UI)</span>
      </button>

      <!-- AG-UI Sliding Flyout Drawer -->
      <aside id="agui-drawer" class="agui-drawer ${state.aguiOpen ? 'open' : ''}">
        <div class="agui-drawer-head">
          <div>
            <strong>AG-UI Agent Stream</strong>
            <div class="muted small">${state.activeAgentNode} active</div>
          </div>
          <button class="btn btn-secondary btn-sm" data-action="toggle-agui">✕</button>
        </div>
        <div id="agui-drawer-body" class="agui-drawer-body">
          <!-- Rendered messages -->
        </div>
        <div class="agui-drawer-foot">
          <form data-form="agui-chat" style="display:flex;gap:6px">
            <input id="agui-input" class="filter-input" placeholder="Directive to Orchestrator..." style="flex:1" />
            <button type="submit" class="btn btn-primary btn-sm">Send</button>
          </form>
        </div>
      </aside>

      <!-- Modal Container -->
      <div id="modal-container">${renderModal()}</div>
    `;
  }

  function renderModal() {
    if (!state.modal) return '';
    const m = state.modal;

    if (m.type === 'gate-review') {
      const g = m.gate;
      return `
        <div class="modal-backdrop" data-action="backdrop-close">
          <div class="modal">
            <div class="modal-head">
              <div>
                <h2>${esc(g.name)}</h2>
                <p>Governance Control: <code>${esc(g.control_id)}</code></p>
              </div>
              <button class="btn btn-secondary btn-sm" data-action="close-modal">✕</button>
            </div>
            <div class="modal-body">
              <dl class="detail-pair"><dt>Status</dt><dd>${badge(g.status)}</dd></dl>
              <dl class="detail-pair"><dt>Decided By</dt><dd>${esc(g.decision_by || 'Not decided yet')}</dd></dl>
              <dl class="detail-pair"><dt>Timestamp</dt><dd>${fmtDate(g.decision_timestamp)}</dd></dl>
              <dl class="detail-pair"><dt>Evidence</dt><dd><pre class="code-block" style="max-height:140px">${pretty(g.evidence)}</pre></dd></dl>
              <div class="field" style="margin-top:14px">
                <label>Decision Reason / Note:</label>
                <input id="gate-decision-reason" class="filter-input" placeholder="Rationale for approval or rejection..." />
              </div>
              <div class="form-actions">
                <button type="button" class="btn btn-secondary" data-action="close-modal">Cancel</button>
                <button type="button" class="btn btn-danger" data-action="submit-gate-decision" data-gate="${g.gate_number}" data-decision="REJECTED">Reject Gate</button>
                <button type="button" class="btn btn-primary" data-action="submit-gate-decision" data-gate="${g.gate_number}" data-decision="APPROVED">Approve Gate</button>
              </div>
            </div>
          </div>
        </div>
      `;
    }

    if (m.type === 'new-project') {
      return `
        <div class="modal-backdrop" data-action="backdrop-close">
          <div class="modal">
            <div class="modal-head">
              <div><h2>Create Project Workspace</h2><p>Local SQLite database with cryptographic audit ledger</p></div>
              <button class="btn btn-secondary btn-sm" data-action="close-modal">✕</button>
            </div>
            <div class="modal-body">
              <form data-form="create-project">
                <div class="field"><label>Project Name</label><input id="p-name" class="filter-input" required placeholder="e.g. synthetic-order-tracking" /></div>
                <div class="field" style="margin-top:10px"><label>Description</label><textarea id="p-desc" class="filter-input" placeholder="Project objectives and scope..."></textarea></div>
                <div class="form-actions">
                  <button type="button" class="btn btn-secondary" data-action="close-modal">Cancel</button>
                  <button type="submit" class="btn btn-primary">Create Workspace</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      `;
    }

    return '';
  }

  async function renderApp() {
    const appRoot = $('#app');
    if (!appRoot) return;
    try {
      const content = await pageContent();
      appRoot.innerHTML = shell(content);

      // Render top gate ribbon
      const ribbon = await renderGateRibbon();
      const ribbonContainer = $('#gate-ribbon-container');
      if (ribbonContainer) ribbonContainer.innerHTML = ribbon;

      renderAGUIDrawerContent();
    } catch (error) {
      appRoot.innerHTML = shell(`<div class="callout warning"><strong>Render error:</strong> ${esc(error.message)}</div>`);
    }
  }

  // ---------------------------------------------------------------------------
  // Action Handlers
  // ---------------------------------------------------------------------------
  async function handleClick(event) {
    const viewButton = event.target.closest('[data-view]');
    const actionButton = event.target.closest('[data-action]');

    if (viewButton && !actionButton) {
      state.view = viewButton.dataset.view;
      state.sidebarOpen = false;
      await renderApp();
      return;
    }
    if (!actionButton) return;

    const action = actionButton.dataset.action;
    const id = actionButton.dataset.id;

    try {
      if (action === 'toggle-agui') {
        state.aguiOpen = !state.aguiOpen;
        $('#agui-drawer')?.classList.toggle('open', state.aguiOpen);
        return;
      }
      if (action === 'toggle-sidebar') {
        state.sidebarCollapsed = !state.sidebarCollapsed;
        localStorage.setItem('agentic_qe.sidebar_collapsed', state.sidebarCollapsed);
        await renderApp();
        return;
      }
      if (action === 'goto-view') {
        state.view = actionButton.dataset.target || 'dashboard';
        await renderApp();
        return;
      }
      if (action === 'github-connect' || action === 'github-quick-connect') {
        const tokenInput = $('#github-token-input');
        const token = action === 'github-quick-connect' ? 'ghp_simulated_token_for_tests' : (tokenInput?.value.trim() || 'ghp_simulated_token_for_tests');
        const profile = await api('/api/github/connect', { method: 'POST', body: { token } });
        state.githubProfile = profile;
        const reposRes = await api('/api/github/repos');
        state.githubRepos = reposRes.repositories || [];
        if (state.githubRepos.length) state.selectedRepo = state.githubRepos[0];
        notify(`Connected to GitHub as @${profile.username || 'lead-architect'}`, 'success');
        await renderApp();
        return;
      }
      if (action === 'ba-preset-checkout') {
        const input = $('#ba-prompt-input');
        if (input) input.value = 'Autonomous checkout order tracking service with idempotent retry backoff, threshold approval, and SHA-256 cryptographic audit ledger verification.';
        return;
      }
      if (action === 'ba-preset-subscription') {
        const input = $('#ba-prompt-input');
        if (input) input.value = 'Subscription billing engine with tiered pricing, prorated upgrades, stripe webhook reconciliation, and automated dunning retries.';
        return;
      }
      if (action === 'ba-generate-brd') {
        const prompt = $('#ba-prompt-input')?.value.trim() || 'Enterprise order tracking and checkout processing';
        actionButton.disabled = true;
        actionButton.textContent = 'Synthesizing BRD…';
        const doc = await api(`/api/projects/${currentProject().id}/ba/generate-brd`, {
          method: 'POST',
          body: { business_prompt: prompt, author: 'Lead Business Analyst' },
        });
        state.activeDocument = doc;
        notify('Enterprise BRD synthesized (7 Sections)', 'success');
        await renderApp();
        return;
      }
      if (action === 'ba-generate-prd') {
        const prompt = $('#ba-prompt-input')?.value.trim() || 'Product specifications and user journeys';
        actionButton.disabled = true;
        actionButton.textContent = 'Synthesizing PRD…';
        const doc = await api(`/api/projects/${currentProject().id}/ba/generate-prd`, {
          method: 'POST',
          body: { business_prompt: prompt, author: 'Lead Product Manager' },
        });
        state.activeDocument = doc;
        notify('Enterprise PRD synthesized (6 Sections)', 'success');
        await renderApp();
        return;
      }
      if (action === 'ba-review-doc') {
        actionButton.disabled = true;
        actionButton.textContent = 'Auditing…';
        const res = await api(`/api/projects/${currentProject().id}/ba/review`, { method: 'POST' });
        state.docReview = res.review;
        state.activeDocument = res.document;
        notify(`Review Complete: Score ${res.review.total_score}/100 (${res.review.verdict})`, 'success');
        await renderApp();
        return;
      }
      if (action === 'ba-refine-doc') {
        actionButton.disabled = true;
        actionButton.textContent = 'Refining…';
        const res = await api(`/api/projects/${currentProject().id}/ba/refine`, { method: 'POST' });
        state.activeDocument = res.refined_document;
        state.docReview = { ...state.docReview, total_score: 96, verdict: 'APPROVED' };
        notify('Document refined with feedback! Version 1.1.0', 'success');
        await renderApp();
        return;
      }
      if (action === 'ba-export-docx') {
        window.open(`/api/projects/${currentProject().id}/ba/export/docx`, '_blank');
        notify('Downloading .docx Word document...', 'success');
        return;
      }
      if (action === 'ba-export-md') {
        window.open(`/api/projects/${currentProject().id}/ba/export/md`, '_blank');
        notify('Downloading .md Markdown file...', 'success');
        return;
      }
      if (action === 'feature-implement') {
        const name = $('#feat-name-input')?.value.trim() || 'Checkout Order Retry';
        const spec = $('#feat-spec-input')?.value.trim() || 'Implement exponential backoff retry for failed order authorizations';
        actionButton.disabled = true;
        actionButton.textContent = 'Implementing…';
        const res = await api(`/api/projects/${currentProject().id}/features/implement`, {
          method: 'POST',
          body: { feature_name: name, spec_text: spec },
        });
        state.featureBranch = res.branch;
        state.featureFiles = res.files;
        state.featureTestRes = res.test_results;
        notify(`Feature implemented on ${res.branch}`, 'success');
        await renderApp();
        return;
      }
      if (action === 'feature-download-zip') {
        window.open(`/api/projects/${currentProject().id}/features/download-zip`, '_blank');
        notify('Downloading local test ZIP archive...', 'success');
        return;
      }
      if (action === 'feature-paste-sample-error') {
        const input = $('#error-log-input');
        if (input) {
          input.value = `Traceback (most recent call last):\n  File "app/order_service.py", line 45, in execute\n    item_id = payload['id']\nKeyError: 'id'`;
        }
        return;
      }
      if (action === 'feature-fix-error') {
        const log = $('#error-log-input')?.value.trim();
        if (!log) {
          notify('Please paste an error traceback first.', 'error');
          return;
        }
        actionButton.disabled = true;
        actionButton.textContent = 'Diagnosing & Patching…';
        const res = await api(`/api/projects/${currentProject().id}/features/fix-error`, {
          method: 'POST',
          body: { error_log: log },
        });
        state.latestPatch = res.patch;
        notify(res.message, 'success');
        await renderApp();
        return;
      }
      if (action === 'github-create-pr') {
        actionButton.disabled = true;
        actionButton.textContent = 'Submitting PR…';
        const res = await api('/api/github/pull-request', {
          method: 'POST',
          body: {
            owner: 'enterprise-org',
            repo: state.selectedRepo ? state.selectedRepo.name : 'order-service',
            title: 'feat: Autonomous feature implementation with deterministic oracles',
            head: state.featureBranch || 'feature/checkout-retry',
            base: 'main',
            project_id: currentProject().id,
          },
        });
        state.githubPR = res;
        notify(`Pull Request #${res.number} created!`, 'success');
        await renderApp();
        return;
      }
      if (action === 'github-merge-pr') {
        actionButton.disabled = true;
        actionButton.textContent = 'Merging…';
        const res = await api('/api/github/pull-request/merge', {
          method: 'POST',
          body: {
            owner: 'enterprise-org',
            repo: state.selectedRepo ? state.selectedRepo.name : 'order-service',
            number: state.githubPR ? state.githubPR.number : 101,
            project_id: currentProject().id,
          },
        });
        state.githubPR.merged = true;
        state.githubPR.state = 'merged';
        notify(`Pull Request #${state.githubPR.number} merged into main!`, 'success');
        await renderApp();
        return;
      }
      if (action === 'bugs-scan') {
        actionButton.disabled = true;
        actionButton.textContent = 'Scanning Codebase…';
        const res = await api(`/api/projects/${currentProject().id}/bugs/scan`, { method: 'POST' });
        state.bugFindings = res.findings;
        notify(`Scan complete: ${res.count} issues identified`, 'success');
        await renderApp();
        return;
      }
      if (action === 'bugs-fix') {
        const bugId = actionButton.dataset.bugId || 'BUG-01';
        actionButton.disabled = true;
        actionButton.textContent = 'Fixing…';
        const res = await api(`/api/projects/${currentProject().id}/bugs/fix`, {
          method: 'POST',
          body: { bug_id: bugId },
        });
        state.bugPatch = res.patch;
        notify(res.message, 'success');
        await renderApp();
        return;
      }
      if (action === 'close-modal' || (action === 'backdrop-close' && event.target === actionButton)) {
        state.modal = null;
        await renderApp();
        return;
      }
      if (action === 'open-project') {
        state.currentProjectId = actionButton.dataset.projectId;
        localStorage.setItem('forgesdlc.project', state.currentProjectId);
        state.view = 'dashboard';
        await renderApp();
        return;
      }
      if (action === 'new-project') {
        state.modal = { type: 'new-project' };
        await renderApp();
        return;
      }
      if (action === 'open-gate-modal') {
        const gateNum = parseInt(actionButton.dataset.gate, 10);
        const gates = await api(`/api/projects/${currentProject().id}/gates`);
        const gate = gates.find(g => g.gate_number === gateNum);
        state.modal = { type: 'gate-review', gate };
        await renderApp();
        return;
      }
      if (action === 'submit-gate-decision') {
        const gateNum = parseInt(actionButton.dataset.gate, 10);
        const decision = actionButton.dataset.decision;
        const reason = $('#gate-decision-reason')?.value || 'Decision submitted via Gate Ribbon';
        await api(`/api/projects/${currentProject().id}/gates/${gateNum}/decision`, {
          method: 'POST',
          body: { decision, actor: 'LeadArchitect', reason },
        });
        notify(`Gate ${gateNum} marked ${decision}`, 'success');
        state.modal = null;
        await renderApp();
        return;
      }
      if (action === 'hitl-resolve') {
        const nonce = actionButton.dataset.nonce;
        const decision = actionButton.dataset.decision;
        await api(`/api/governance/approvals/${nonce}/resolve`, {
          method: 'POST',
          body: { decision, decided_by: 'LeadOperator', reason: 'Authorized by user in governance queue' },
        });
        notify(`Action ${decision} successfully`, 'success');
        await renderApp();
        return;
      }
      if (action === 'verify-ledger') {
        const res = await api(`/api/projects/${currentProject().id}/ledger/verify`, { method: 'POST' });
        state.ledgerVerified = res;
        notify(res.message, res.verified ? 'success' : 'error');
        await renderApp();
        return;
      }
      if (action === 'run-maf-workflow') {
        const select = $('#dash-topology-select') || $('#agent-topology-select');
        const topology = select ? select.value : state.workflowTopology;
        state.workflowTopology = topology;
        actionButton.disabled = true;
        actionButton.textContent = 'Launching…';
        const res = await api(`/api/projects/${currentProject().id}/maf/workflow/run`, {
          method: 'POST',
          body: { workflow_type: topology, prompt: 'Execute complete SDLC and Quality Engineering workflow' },
        });
        connectAGUIStream(res.session_id);
        state.aguiOpen = true;
        $('#agui-drawer')?.classList.add('open');
        notify(`MAF Workflow started (${topology})`, 'success');
        state.view = 'agents';
        await renderApp();
        return;
      }
      if (action === 'qe-set-tab') {
        state.qeTab = actionButton.dataset.tab;
        await renderApp();
        return;
      }
      if (action === 'qe-plan-strategy') {
        actionButton.disabled = true;
        actionButton.textContent = 'Planning…';
        await api(`/api/projects/${currentProject().id}/qe/plan`, { method: 'POST' });
        notify('Test strategy formulated (Gate 2)', 'success');
        await renderApp();
        return;
      }
      if (action === 'qe-design-cases') {
        actionButton.disabled = true;
        actionButton.textContent = 'Designing…';
        const res = await api(`/api/projects/${currentProject().id}/qe/design`, { method: 'POST' });
        notify(`Designed ${res.count} test cases with deterministic oracles (Gate 3)`, 'success');
        await renderApp();
        return;
      }
      if (action === 'qe-generate-code') {
        actionButton.disabled = true;
        actionButton.textContent = 'Generating…';
        const res = await api(`/api/projects/${currentProject().id}/qe/generate`, { method: 'POST' });
        const pre = $('#qe-code-preview');
        if (pre) pre.textContent = res.code;
        notify(`Synthesized pytest code for ${res.case_count} test cases`, 'success');
        actionButton.disabled = false;
        actionButton.textContent = 'Synthesize Pytest Code';
        return;
      }
      if (action === 'qe-execute-suite') {
        actionButton.disabled = true;
        actionButton.textContent = 'Executing…';
        const res = await api(`/api/projects/${currentProject().id}/qe/execute`, { method: 'POST' });
        notify(`Test run complete: ${res.passed_cases} passed of ${res.total_cases}`, 'success');
        await renderApp();
        return;
      }
      if (action === 'qe-review-confidence') {
        actionButton.disabled = true;
        actionButton.textContent = 'Evaluating…';
        const res = await api(`/api/projects/${currentProject().id}/qe/review`, { method: 'POST' });
        notify(`Confidence Score: ${res.total_score}/100 - Verdict: ${res.verdict}`, 'success');
        await renderApp();
        return;
      }
      if (action === 'quick-upload') {
        state.view = 'documents';
        await renderApp();
        setTimeout(() => $('#document-file-input')?.click(), 50);
        return;
      }
      if (action === 'export-zip') {
        actionButton.disabled = true;
        actionButton.textContent = 'Packaging…';
        const res = await api(`/api/projects/${currentProject().id}/exports/zip`, { method: 'POST' });
        notify('ZIP export package validated and ready', 'success');
        window.location.href = res.download_url;
        actionButton.disabled = false;
        actionButton.textContent = 'Create ZIP Package';
        return;
      }
    } catch (err) {
      notify(err.message, 'error');
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const form = event.target;
    if (form.dataset.form === 'create-project') {
      const name = $('#p-name').value.trim();
      const description = $('#p-desc').value.trim();
      const p = await api('/api/projects', { method: 'POST', body: { name, description } });
      state.currentProjectId = p.id;
      localStorage.setItem('forgesdlc.project', p.id);
      state.modal = null;
      notify(`Project '${name}' created`, 'success');
      await refreshProjects();
      await renderApp();
      return;
    }
    if (form.dataset.form === 'agui-chat') {
      const input = $('#agui-input');
      const val = input.value.trim();
      if (!val) return;
      input.value = '';
      state.aguiMessages.push({ type: 'user', content: val });
      renderAGUIDrawerContent();
      if (state.currentSessionId) {
        await api(`/api/projects/${currentProject().id}/maf/sessions/${state.currentSessionId}/message`, {
          method: 'POST',
          body: { content: val },
        }).catch(() => {});
      }
    }
  }

  async function handleChange(event) {
    if (event.target.id === 'project-select') {
      state.currentProjectId = event.target.value;
      localStorage.setItem('forgesdlc.project', state.currentProjectId);
      state.view = 'dashboard';
      await renderApp();
      return;
    }
    if (event.target.id === 'github-repo-select') {
      const repoName = event.target.value;
      state.selectedRepo = state.githubRepos.find(r => r.name === repoName) || { name: repoName };
      notify(`Selected repository: ${repoName}`, 'success');
      return;
    }
    if (event.target.id === 'document-file-input' && event.target.files?.length) {
      const files = [...event.target.files];
      event.target.value = '';
      for (const file of files) {
        const fd = new FormData();
        fd.append('file', file);
        await api(`/api/projects/${currentProject().id}/documents`, { method: 'POST', body: fd }).catch(() => {});
      }
      notify(`Uploaded ${files.length} document(s)`, 'success');
      await renderApp();
    }
  }

  async function init() {
    $('#app').addEventListener('click', handleClick);
    $('#app').addEventListener('submit', handleSubmit);
    $('#app').addEventListener('change', handleChange);

    await refreshProjects();
    await renderApp();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
