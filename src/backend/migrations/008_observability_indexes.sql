-- Indexes for paging the Observability log in SQL: each source is read newest first, by project or run.
CREATE INDEX IF NOT EXISTS idx_run_events_ts ON run_events(ts);
CREATE INDEX IF NOT EXISTS idx_agent_calls_ts ON agent_calls(created_at);
CREATE INDEX IF NOT EXISTS idx_agent_calls_project ON agent_calls(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_calls_run ON agent_calls(run_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_ts ON tool_calls(created_at);
CREATE INDEX IF NOT EXISTS idx_guardrail_ts ON guardrail_events(created_at);
CREATE INDEX IF NOT EXISTS idx_guardrail_project ON guardrail_events(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_guardrail_run ON guardrail_events(run_id);
CREATE INDEX IF NOT EXISTS idx_ledger_ts ON ledger(ts);
-- The one-active-run check looks up a project's running or waiting runs of one kind.
CREATE INDEX IF NOT EXISTS idx_runs_active ON runs(project_id, workflow) WHERE status IN ('running','waiting_approval');
