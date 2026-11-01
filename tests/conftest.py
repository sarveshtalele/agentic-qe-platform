"""Every test run uses a throwaway data directory. The app's real data is never touched."""
import os
import tempfile

_store = tempfile.mkdtemp(prefix="atlas-test-")
os.environ["ATLAS_DATA_DIR"] = _store
os.environ["ATLAS_WORKSPACES"] = os.path.join(_store, "projects")
os.environ.setdefault("ATLAS_SECRET_KEY", "test-only-key")

from backend import db as database  # noqa: E402
from backend.core import files, prompts  # noqa: E402

database.migrate()
prompts.seed()
files.seed_templates()
