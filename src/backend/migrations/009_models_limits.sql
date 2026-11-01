-- Several models on one endpoint, who may use which, and token limits per period.
CREATE TABLE models (
  name TEXT PRIMARY KEY, label TEXT NOT NULL DEFAULT '', enabled INTEGER NOT NULL DEFAULT 1,
  is_default INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE user_models (
  user_id TEXT NOT NULL, model TEXT NOT NULL, PRIMARY KEY (user_id, model)
);
-- model '' is a limit across all models
CREATE TABLE user_limits (
  user_id TEXT NOT NULL, model TEXT NOT NULL DEFAULT '', period TEXT NOT NULL CHECK (period IN ('day','week','month')),
  tokens INTEGER NOT NULL CHECK (tokens >= 0), PRIMARY KEY (user_id, model, period)
);

ALTER TABLE agent_settings ADD COLUMN model TEXT NOT NULL DEFAULT '';
ALTER TABLE chat_threads ADD COLUMN model TEXT NOT NULL DEFAULT '';
ALTER TABLE runs ADD COLUMN user_id TEXT;
ALTER TABLE runs ADD COLUMN model TEXT NOT NULL DEFAULT '';
ALTER TABLE agent_calls ADD COLUMN model TEXT NOT NULL DEFAULT '';
ALTER TABLE agent_calls ADD COLUMN user_id TEXT;

-- calls and runs made before this migration belong to the project's owner; the model they used was not recorded
UPDATE agent_calls SET user_id = CASE WHEN project_id = 'prj_agent_evals' THEN 'admin' ELSE (SELECT owner_id FROM projects WHERE projects.id = agent_calls.project_id) END;
UPDATE runs SET user_id = (SELECT owner_id FROM projects WHERE projects.id = runs.project_id);
CREATE INDEX idx_agent_calls_user ON agent_calls(user_id, created_at);
CREATE INDEX idx_agent_calls_user_model ON agent_calls(user_id, model, created_at);

-- the configured model becomes the default, so existing setups keep working
INSERT OR IGNORE INTO models (name, label, enabled, is_default, created_at)
  SELECT value, value, 1, 1, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now') FROM settings WHERE key = 'llm_model' AND value <> '';
-- each user keeps the model they had; users on the system default keep that
INSERT OR IGNORE INTO models (name, label, enabled, is_default, created_at)
  SELECT DISTINCT model, model, 1, 0, strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now') FROM users WHERE model <> '';
INSERT OR IGNORE INTO user_models (user_id, model) SELECT id, model FROM users WHERE model <> '';
INSERT OR IGNORE INTO user_models (user_id, model) SELECT u.id, m.name FROM users u, models m WHERE u.model = '' AND m.is_default = 1;
