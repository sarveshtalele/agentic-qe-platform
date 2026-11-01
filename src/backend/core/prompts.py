"""Versioned agent prompts. prompts/*.md seed v1; every edit is a new immutable version in the DB."""
from __future__ import annotations

from backend.config import PROMPTS_DIR
from backend.core.security import sha256
from backend.db import db, now, row, rows


def seed() -> None:
    """Add repo prompt files as new versions when their content changes. Never rewrites history."""
    with db() as con:
        for path in sorted(PROMPTS_DIR.glob("*.md")):
            agent, body = path.stem, path.read_text(encoding="utf-8").strip()
            digest = sha256(body)
            if con.execute("SELECT 1 FROM prompts WHERE agent=? AND sha256=?", (agent, digest)).fetchone():
                continue
            version = con.execute("SELECT COALESCE(MAX(version),0)+1 FROM prompts WHERE agent=?", (agent,)).fetchone()[0]
            con.execute("UPDATE prompts SET active=0 WHERE agent=?", (agent,))
            con.execute("INSERT INTO prompts VALUES (?,?,?,?,?,?,1,?)", (agent, version, body, digest, f"Seeded from prompts/{path.name}", "repo", now()))


def active(agent: str) -> dict:
    with db() as con:
        found = row(con.execute("SELECT * FROM prompts WHERE agent=? AND active=1", (agent,)))
    if not found:
        raise KeyError(f"No active prompt for agent {agent}")
    return found


def ref(agent: str) -> str:
    current = active(agent)
    return f"{agent}@v{current['version']}:{current['sha256'][:12]}"


def list_all() -> list[dict]:
    with db() as con:
        return rows(con.execute("SELECT agent, version, sha256, note, author, active, created_at FROM prompts ORDER BY agent, version DESC"))


def history(agent: str) -> list[dict]:
    with db() as con:
        return rows(con.execute("SELECT * FROM prompts WHERE agent=? ORDER BY version DESC", (agent,)))


def add_version(agent: str, body: str, note: str, author: str) -> dict:
    with db() as con:
        if not con.execute("SELECT 1 FROM prompts WHERE agent=?", (agent,)).fetchone():
            raise KeyError(agent)
        version = con.execute("SELECT MAX(version)+1 FROM prompts WHERE agent=?", (agent,)).fetchone()[0]
        con.execute("UPDATE prompts SET active=0 WHERE agent=?", (agent,))
        con.execute("INSERT INTO prompts VALUES (?,?,?,?,?,?,1,?)", (agent, version, body.strip(), sha256(body.strip()), note, author, now()))
    return active(agent)


def activate(agent: str, version: int) -> dict:
    with db() as con:
        if not con.execute("SELECT 1 FROM prompts WHERE agent=? AND version=?", (agent, version)).fetchone():
            raise KeyError(f"{agent} v{version}")
        con.execute("UPDATE prompts SET active=(version=?) WHERE agent=?", (version, agent))
    return active(agent)
