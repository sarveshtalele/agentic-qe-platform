CREATE TABLE agent_settings (
  agent TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1, max_tokens INTEGER,
  updated_by TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL
);
CREATE TABLE guardrail_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT NOT NULL, project_id TEXT, run_id TEXT,
  kind TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE agent_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT NOT NULL, project_id TEXT, run_id TEXT, source TEXT NOT NULL,
  prompt_ref TEXT NOT NULL, tokens_in INTEGER NOT NULL DEFAULT 0, tokens_out INTEGER NOT NULL DEFAULT 0,
  latency_ms INTEGER NOT NULL DEFAULT 0, tool_calls INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL,
  error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE INDEX idx_agent_calls_agent ON agent_calls(agent, created_at);
CREATE INDEX idx_guardrail_agent ON guardrail_events(agent, created_at);
