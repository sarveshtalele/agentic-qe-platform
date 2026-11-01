"""Workflows, one file each. A file registers its definition in engine.REGISTRY, so adding a workflow means adding a file."""
from __future__ import annotations

import importlib
import pkgutil

for _module in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_module.name}")

from backend.maf.workflows.ba import Review  # noqa: E402
from backend.maf.workflows.bug_scan import ReviewFindings  # noqa: E402
from backend.maf.workflows.edits import ChangeSet, Edit, apply_edits, guarded_apply  # noqa: E402
from backend.maf.workflows.qe import GeneratedSuite  # noqa: E402

__all__ = ["ChangeSet", "Edit", "GeneratedSuite", "Review", "ReviewFindings", "apply_edits", "guarded_apply"]
