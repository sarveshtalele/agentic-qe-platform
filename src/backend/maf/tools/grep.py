"""The grep agent tool."""
from __future__ import annotations

import re
from typing import Annotated

from agent_framework import tool
from pydantic import Field

from backend.core.security import redact
from backend.repos import scan


def build(base):
    @tool(name="grep", description="Search repository text files with a regular expression. Returns file:line matches.")
    def grep(
        pattern: Annotated[str, Field(description="Python regular expression")],
        path_contains: Annotated[str, Field(description="Only search paths containing this")] = "",
    ) -> str:
        if not base.exists():
            return "No repository connected."
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            return f"Invalid regex: {exc}"
        hits: list[str] = []
        for file in scan.iter_files(base):
            relative = file.relative_to(base).as_posix()
            if path_contains.lower() not in relative.lower():
                continue
            for number, line in enumerate(scan._read(file).splitlines(), 1):
                if compiled.search(line):
                    hits.append(f"{relative}:{number}: {line.strip()[:200]}")
                    if len(hits) >= 200:
                        return redact("\n".join(hits)) + "\n… truncated"
        return redact("\n".join(hits)) or "No matches."

    return grep
