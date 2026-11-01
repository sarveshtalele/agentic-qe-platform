CREATE TABLE projects (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE credentials (
  id TEXT PRIMARY KEY, provider TEXT NOT NULL, label TEXT NOT NULL, login TEXT NOT NULL DEFAULT '',
  secret BLOB NOT NULL, scopes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE repo_sources (
  project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, url TEXT NOT NULL DEFAULT '', ref TEXT NOT NULL DEFAULT '',
  credential_id TEXT, commit_sha TEXT NOT NULL DEFAULT '', analysis TEXT NOT NULL DEFAULT '{}',
  scanned_at TEXT NOT NULL
);
CREATE TABLE sources (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  filename TEXT NOT NULL, sha256 TEXT NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL,
  UNIQUE(project_id, sha256)
);
CREATE TABLE templates (
  id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL, builtin INTEGER NOT NULL DEFAULT 0,
  sha256 TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE documents (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
  current_version INTEGER NOT NULL DEFAULT 0, parent_id TEXT, template_id TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE document_versions (
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE, version INTEGER NOT NULL,
  content TEXT NOT NULL, data TEXT NOT NULL DEFAULT 'null', sha256 TEXT NOT NULL, author TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '', prompt_ref TEXT NOT NULL DEFAULT '', run_id TEXT, created_at TEXT NOT NULL,
  PRIMARY KEY (document_id, version)
);
CREATE TABLE prompts (
  agent TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL, sha256 TEXT NOT NULL,
  note TEXT NOT NULL DEFAULT '', author TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
  PRIMARY KEY (agent, version)
);
CREATE TABLE runs (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  workflow TEXT NOT NULL, status TEXT NOT NULL, input TEXT NOT NULL, state TEXT NOT NULL DEFAULT '{}',
  error TEXT NOT NULL DEFAULT '', tokens_in INTEGER NOT NULL DEFAULT 0, tokens_out INTEGER NOT NULL DEFAULT 0,
  started_at TEXT NOT NULL, ended_at TEXT
);
CREATE TABLE run_events (
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE, seq INTEGER NOT NULL,
  type TEXT NOT NULL, stage TEXT NOT NULL DEFAULT '', message TEXT NOT NULL DEFAULT '',
  data TEXT NOT NULL DEFAULT '{}', ts TEXT NOT NULL, PRIMARY KEY (run_id, seq)
);
CREATE TABLE approvals (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, gate INTEGER, title TEXT NOT NULL,
  summary TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'pending',
  decided_by TEXT, feedback TEXT, created_at TEXT NOT NULL, decided_at TEXT
);
CREATE TABLE gates (
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, gate INTEGER NOT NULL,
  status TEXT NOT NULL, decided_by TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', run_id TEXT,
  signature TEXT NOT NULL, decided_at TEXT NOT NULL, PRIMARY KEY (project_id, gate)
);
CREATE TABLE ledger (
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, seq INTEGER NOT NULL, ts TEXT NOT NULL,
  actor TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL DEFAULT '', data TEXT NOT NULL DEFAULT '{}',
  prev_hash TEXT NOT NULL, hash TEXT NOT NULL, PRIMARY KEY (project_id, seq)
);
CREATE TABLE findings (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, run_id TEXT,
  source TEXT NOT NULL, rule TEXT NOT NULL, severity TEXT NOT NULL, title TEXT NOT NULL, file TEXT NOT NULL,
  line INTEGER NOT NULL, evidence TEXT NOT NULL, explanation TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open', fingerprint TEXT NOT NULL, created_at TEXT NOT NULL,
  UNIQUE(project_id, fingerprint)
);
CREATE TABLE chat_threads (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title TEXT NOT NULL, agent TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE chat_messages (
  thread_id TEXT NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE, seq INTEGER NOT NULL, id TEXT NOT NULL,
  role TEXT NOT NULL, content TEXT NOT NULL, agent TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
  PRIMARY KEY (thread_id, seq)
);
CREATE TABLE memories (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  content TEXT NOT NULL, source TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE INDEX idx_documents_project ON documents(project_id, kind);
CREATE INDEX idx_runs_project ON runs(project_id, started_at);
CREATE INDEX idx_threads_project ON chat_threads(project_id, updated_at);
