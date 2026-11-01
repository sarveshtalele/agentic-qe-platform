-- One row per metric per agent per eval run (source 'eval') or per real agent call (source 'live').
-- status: measured, n/a (does not apply to the agent), not_measured (not run, or the tool is missing), failed (the metric could not run), inconclusive.
-- value is NULL unless status is measured. labels_reviewed is NULL when no answer key was used.
CREATE TABLE evaluation_metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT, eval_id TEXT NOT NULL DEFAULT '', batch TEXT NOT NULL DEFAULT '', agent TEXT NOT NULL, prompt_ref TEXT NOT NULL,
  metric TEXT NOT NULL, value REAL, status TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', n INTEGER NOT NULL DEFAULT 0,
  judge_model TEXT NOT NULL DEFAULT '', self_graded INTEGER NOT NULL DEFAULT 0, labels_reviewed INTEGER, tokens INTEGER NOT NULL DEFAULT 0,
  detail TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'eval', agent_call_id INTEGER, benchmark TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE INDEX idx_evalmetrics_agent ON evaluation_metrics(agent, prompt_ref, metric);
CREATE INDEX idx_evalmetrics_batch ON evaluation_metrics(batch);
