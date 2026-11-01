-- Every tool call an agent makes, in workflows and chat. kind is function or mcp.
CREATE TABLE tool_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT NOT NULL, project_id TEXT, run_id TEXT, source TEXT NOT NULL,
  tool TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'function', arguments TEXT NOT NULL DEFAULT '{}',
  latency_ms INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE INDEX idx_tool_calls_project ON tool_calls(project_id, created_at);
CREATE INDEX idx_tool_calls_run ON tool_calls(run_id);
