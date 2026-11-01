-- One diagnostic record per failed stage. Every text column is redacted before it is written.
-- The whole rejected model reply is a file under data/runs/<run_id>/failures/, named in reply_file, never a column.
CREATE TABLE IF NOT EXISTS run_failures (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  code TEXT NOT NULL, message TEXT NOT NULL, action TEXT NOT NULL, retryable INTEGER NOT NULL DEFAULT 0,
  stage TEXT NOT NULL DEFAULT '', agent TEXT NOT NULL DEFAULT '', attempt INTEGER, prompt_ref TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '',
  finish_reason TEXT NOT NULL DEFAULT '', tokens_in INTEGER, tokens_out INTEGER, duration_ms INTEGER,
  parse_pos INTEGER, parse_context TEXT NOT NULL DEFAULT '', technical TEXT NOT NULL DEFAULT '', reply_file TEXT NOT NULL DEFAULT '',
  stack TEXT NOT NULL DEFAULT '', provider_status INTEGER, provider_request_id TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_run_failures_run ON run_failures(run_id, created_at);
