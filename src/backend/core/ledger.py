"""Tamper-evident audit ledger: each entry hashes the previous entry, per project."""
from __future__ import annotations

import json

from backend.core.security import redact, sha256
from backend.db import db, now, rows

GENESIS = "0" * 64


def _digest(prev: str, seq: int, ts: str, actor: str, action: str, target: str, data: str) -> str:
    return sha256("|".join((prev, str(seq), ts, actor, action, target, data)))


def append(project_id: str, actor: str, action: str, target: str = "", data: dict | None = None) -> None:
    payload = redact(json.dumps(data or {}, sort_keys=True, default=str))
    stamp = now()
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        last = con.execute("SELECT seq, hash FROM ledger WHERE project_id=? ORDER BY seq DESC LIMIT 1", (project_id,)).fetchone()
        seq, prev = (last["seq"] + 1, last["hash"]) if last else (1, GENESIS)
        con.execute(
            "INSERT INTO ledger VALUES (?,?,?,?,?,?,?,?,?)",
            (project_id, seq, stamp, actor, action, target, payload, prev, _digest(prev, seq, stamp, actor, action, target, payload)),
        )


def entries(project_id: str, limit: int = 500) -> list[dict]:
    with db() as con:
        return rows(con.execute("SELECT * FROM ledger WHERE project_id=? ORDER BY seq DESC LIMIT ?", (project_id, limit)))


def verify(project_id: str) -> dict:
    with db() as con:
        chain = rows(con.execute("SELECT * FROM ledger WHERE project_id=? ORDER BY seq", (project_id,)))
    prev, expected_seq = GENESIS, 1
    for e in chain:
        digest = _digest(prev, e["seq"], e["ts"], e["actor"], e["action"], e["target"], e["data"])
        if e["seq"] != expected_seq or e["prev_hash"] != prev or e["hash"] != digest:
            return {"valid": False, "entries": len(chain), "broken_at": e["seq"]}
        prev, expected_seq = e["hash"], expected_seq + 1
    return {"valid": True, "entries": len(chain), "broken_at": None}
