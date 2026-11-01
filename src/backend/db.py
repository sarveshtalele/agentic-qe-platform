"""SQLite access: one short connection per unit of work, numbered SQL migrations via user_version."""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from backend.config import DB_PATH, SQLITE_JOURNAL

MIGRATIONS = Path(__file__).parent / "migrations"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        with con:
            yield con
    finally:
        con.close()


def rows(cursor) -> list[dict]:
    return [dict(r) for r in cursor.fetchall()]


def row(cursor) -> dict | None:
    found = cursor.fetchone()
    return dict(found) if found else None


def migrate() -> None:
    with db() as con:
        con.execute(f"PRAGMA journal_mode={SQLITE_JOURNAL}")
        current = con.execute("PRAGMA user_version").fetchone()[0]
        for path in sorted(MIGRATIONS.glob("*.sql")):
            number = int(path.name.split("_")[0])
            if number > current:
                con.executescript(path.read_text(encoding="utf-8"))
                con.execute(f"PRAGMA user_version={number}")
