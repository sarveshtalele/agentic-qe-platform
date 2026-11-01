-- Plugin skills on MAF: which skills each model call used, and the live tool check stored per model.
-- agent_calls.skills is JSON: [{"name", "version", "sha256", "refs"}]. Empty for a call that used no skill.
ALTER TABLE agent_calls ADD COLUMN skills TEXT NOT NULL DEFAULT '';
-- tools_status is '' (not checked), 'passed', or 'failed'. tools_max_tokens is the output limit the check used.
ALTER TABLE models ADD COLUMN tools_status TEXT NOT NULL DEFAULT '';
ALTER TABLE models ADD COLUMN tools_reason TEXT NOT NULL DEFAULT '';
ALTER TABLE models ADD COLUMN tools_checked_at TEXT;
ALTER TABLE models ADD COLUMN tools_max_tokens INTEGER;
