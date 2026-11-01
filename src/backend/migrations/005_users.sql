-- Accounts. Usernames are stored encrypted with a keyed hash for lookup, and passwords as salted scrypt hashes.
CREATE TABLE users (
  id TEXT PRIMARY KEY, username_lookup TEXT NOT NULL UNIQUE, username_enc TEXT NOT NULL, password_hash TEXT NOT NULL,
  model TEXT NOT NULL DEFAULT '', token_limit INTEGER, active_from TEXT, active_until TEXT,
  enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE sessions (
  token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE auth_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT NOT NULL, event TEXT NOT NULL, created_at TEXT NOT NULL
);
ALTER TABLE projects ADD COLUMN owner_id TEXT;
CREATE INDEX idx_projects_owner ON projects(owner_id);
