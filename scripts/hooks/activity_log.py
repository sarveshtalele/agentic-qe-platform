#!/usr/bin/env python3
"""Append timestamped activity to progress.md. Stdlib only; works on Windows, macOS, Linux.

Hook use:     activity_log.py pre|post|fail|prompt|stop   (Claude Code JSON on stdin)
Manual use:   activity_log.py decision "why we chose X"
A logging failure never blocks the tool call, so all errors exit 0.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROGRESS = Path(__file__).resolve().parents[2] / "progress.md"
HEADER = "# Progress and activity log\n\nWritten by `scripts/hooks/activity_log.py`. Times are local.\n\n| Time | Event | Detail |\n|---|---|---|\n"
SECRET = re.compile(r"(sk-[\w-]{8,}|gh[pousr]_\w{8,}|github_pat_\w{8,}|(?i:(?:api[_-]?key|token|password|secret)\s*[=:]\s*)\S+)")


def clean(text: str, limit: int = 160) -> str:
    text = SECRET.sub("[redacted]", " ".join(str(text).split()))
    text = text.replace("|", "\\|")
    return text[: limit - 1] + "…" if len(text) > limit else text


def describe(payload: dict) -> str:
    name = payload.get("tool_name", "")
    data = payload.get("tool_input") or {}
    target = (
        data.get("description")
        or data.get("file_path")
        or data.get("command")
        or data.get("query")
        or data.get("url")
        or ""
    )
    return f"{name}: {target}" if target else name


def entry(event: str, payload: dict, argv: list[str]) -> tuple[str, str] | None:
    if event == "decision":
        return "DECISION", " ".join(argv)
    if event == "pre":
        return "before", describe(payload)
    if event == "post":
        return "after", describe(payload)
    if event == "fail":
        return "failed", f"{describe(payload)} {payload.get('error', '')}"
    if event == "prompt":
        return "user", payload.get("prompt", "")
    if event == "stop":
        return "turn end", ""
    return None


def main() -> None:
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    payload: dict = {}
    if event != "decision" and not sys.stdin.isatty():
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    row = entry(event, payload, sys.argv[2:])
    if not row:
        return
    if not PROGRESS.exists():
        PROGRESS.write_text(HEADER, encoding="utf-8")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with PROGRESS.open("a", encoding="utf-8") as handle:
        handle.write(f"| {stamp} | {row[0]} | {clean(row[1])} |\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - logging must never break the session
        pass
