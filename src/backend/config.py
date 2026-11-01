"""Paths and environment. ATLAS_DATA_DIR lets tests run against a throwaway store."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.environ.get("ATLAS_DATA_DIR", ROOT / "data")).resolve()
WORKSPACES = Path(os.environ.get("ATLAS_WORKSPACES", DATA_DIR / "projects")).resolve()
DB_PATH = DATA_DIR / "atlas.sqlite3"
CHECKPOINTS = DATA_DIR / "checkpoints"
PROMPTS_DIR = ROOT / "prompts"
TEMPLATES_DIR = ROOT / "templates"
MAX_UPLOAD_BYTES = int(os.environ.get("ATLAS_MAX_UPLOAD_MB", "200")) * 1024 * 1024
RUN_TOKEN_LIMIT = int(os.environ.get("ATLAS_RUN_TOKEN_LIMIT", "600000"))
MODEL_TIMEOUT = int(os.environ.get("ATLAS_MODEL_TIMEOUT", "180"))
MODEL_CONCURRENCY = int(os.environ.get("ATLAS_MODEL_CONCURRENCY", "4"))
# WAL needs shared memory, which network storage such as Azure App Service /home lacks. Use DELETE there.
SQLITE_JOURNAL = os.environ.get("ATLAS_SQLITE_JOURNAL", "WAL").upper()
ALLOWED_ORIGINS = {
    o.strip()
    for o in os.environ.get("ATLAS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
}

for path in (DATA_DIR, WORKSPACES, CHECKPOINTS):
    path.mkdir(parents=True, exist_ok=True)


def project_dir(project_id: str) -> Path:
    return WORKSPACES / project_id


def repo_dir(project_id: str) -> Path:
    return project_dir(project_id) / "repo"
