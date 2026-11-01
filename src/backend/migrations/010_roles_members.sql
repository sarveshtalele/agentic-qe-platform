-- Account roles, project members, and the session idle clock. Existing users become developers, who can do what every user could before.
ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'developer' CHECK (role IN ('qe_lead','ba','developer','viewer'));
ALTER TABLE sessions ADD COLUMN last_seen TEXT;
CREATE TABLE project_members (
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, user_id TEXT NOT NULL REFERENCES users(id),
  role TEXT NOT NULL CHECK (role IN ('qe_lead','ba','developer','viewer')), added_by TEXT NOT NULL, created_at TEXT NOT NULL,
  PRIMARY KEY (project_id, user_id)
);
CREATE INDEX idx_members_user ON project_members(user_id);
