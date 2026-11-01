"""The read_file agent tool."""
from __future__ import annotations

from typing import Annotated

from agent_framework import tool
from pydantic import Field

from backend.core.security import redact, safe_path


def build(base):
    @tool(name="read_file", description="Read a repository text file with line numbers.")
    def read_file(
        path: Annotated[str, Field(description="Path relative to the repository root")],
        start_line: Annotated[int, Field(description="First line, 1-based")] = 1,
        max_lines: Annotated[int, Field(description="Maximum lines to return")] = 300,
    ) -> str:
        try:
            target = safe_path(base, path)
        except ValueError as exc:
            return f"Refused: {exc}"
        if not target.is_file():
            return f"Not a file: {path}"
        try:
            lines = target.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            return f"Binary file: {path}"
        begin = max(start_line, 1) - 1
        chunk = lines[begin : begin + min(max_lines, 800)]
        return redact("\n".join(f"{begin + i + 1}: {line}" for i, line in enumerate(chunk))) + f"\n[{len(lines)} lines total]"

    return read_file
