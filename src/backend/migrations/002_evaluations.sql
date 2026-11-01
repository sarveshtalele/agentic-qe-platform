CREATE TABLE evaluations (
  id TEXT PRIMARY KEY, agent TEXT NOT NULL, prompt_ref TEXT NOT NULL, passed INTEGER NOT NULL,
  total INTEGER NOT NULL, results TEXT NOT NULL, created_at TEXT NOT NULL
);
