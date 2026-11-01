from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def compute_entry_hash(
    prev_hash: str,
    sequence_id: int,
    timestamp: str,
    actor: str,
    action: str,
    control_id: str,
    payload_str: str,
) -> str:
    """
    Computes immutable SHA-256 hash of a ledger block (CTL-AUD-01).
    """
    payload = f"{prev_hash}|{sequence_id}|{timestamp}|{actor}|{action}|{control_id}|{payload_str}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AuditLedger:
    """
    Cryptographic Tamper-Evident Ledger dual-writing to SQLite and append-only ledger.jsonl.
    """

    def __init__(self, db_conn: sqlite3.Connection, ledger_path: Path):
        self.conn = db_conn
        self.ledger_path = ledger_path
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        table_exists = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_ledger'").fetchone()
        if table_exists:
            info = self.conn.execute("PRAGMA table_info(audit_ledger)").fetchall()
            pks = [r for r in info if r[5] > 0]
            if len(pks) == 1 and pks[0][1] == "sequence_id":
                self.conn.execute("ALTER TABLE audit_ledger RENAME TO audit_ledger_old")
                self.conn.execute(
                    """
                    CREATE TABLE audit_ledger (
                        project_id TEXT NOT NULL,
                        sequence_id INTEGER NOT NULL,
                        timestamp TEXT NOT NULL,
                        actor TEXT NOT NULL,
                        action TEXT NOT NULL,
                        control_id TEXT NOT NULL,
                        details_json TEXT NOT NULL DEFAULT '{}',
                        prev_hash TEXT NOT NULL,
                        entry_hash TEXT NOT NULL,
                        PRIMARY KEY(project_id, sequence_id)
                    );
                    """
                )
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO audit_ledger (project_id, sequence_id, timestamp, actor, action, control_id, details_json, prev_hash, entry_hash)
                    SELECT project_id, sequence_id, timestamp, actor, action, control_id, details_json, prev_hash, entry_hash FROM audit_ledger_old
                    """
                )
                self.conn.execute("DROP TABLE audit_ledger_old")
                self.conn.commit()
                return

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_ledger (
                project_id TEXT NOT NULL,
                sequence_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                control_id TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                prev_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL,
                PRIMARY KEY(project_id, sequence_id)
            );
            """
        )
        self.conn.commit()

    def get_latest_hash(self, project_id: str) -> Tuple[int, str]:
        row = self.conn.execute(
            "SELECT sequence_id, entry_hash FROM audit_ledger WHERE project_id = ? ORDER BY sequence_id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        if row:
            return row["sequence_id"], row["entry_hash"]
        return 0, GENESIS_HASH

    def append(
        self,
        project_id: str,
        actor: str,
        action: str,
        control_id: str,
        details: Dict[str, Any],
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        ts = timestamp or now_iso()
        last_seq, prev_hash = self.get_latest_hash(project_id)
        next_seq = last_seq + 1

        details_str = json.dumps(details, sort_keys=True, separators=(",", ":"))
        entry_hash = compute_entry_hash(
            prev_hash=prev_hash,
            sequence_id=next_seq,
            timestamp=ts,
            actor=actor,
            action=action,
            control_id=control_id,
            payload_str=details_str,
        )

        # 1. Insert into SQLite
        self.conn.execute(
            """
            INSERT INTO audit_ledger (project_id, sequence_id, timestamp, actor, action, control_id, details_json, prev_hash, entry_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, next_seq, ts, actor, action, control_id, details_str, prev_hash, entry_hash),
        )
        self.conn.commit()

        # 2. Append to ledger.jsonl
        record = {
            "sequence_id": next_seq,
            "project_id": project_id,
            "timestamp": ts,
            "actor": actor,
            "action": action,
            "control_id": control_id,
            "details": details,
            "prev_hash": prev_hash,
            "entry_hash": entry_hash,
        }
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")

        return record

    def get_entries(self, project_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM audit_ledger WHERE project_id = ? ORDER BY sequence_id DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        out = []
        for r in rows:
            out.append({
                "sequence_id": r["sequence_id"],
                "project_id": r["project_id"],
                "timestamp": r["timestamp"],
                "actor": r["actor"],
                "action": r["action"],
                "control_id": r["control_id"],
                "details": json.loads(r["details_json"]),
                "prev_hash": r["prev_hash"],
                "entry_hash": r["entry_hash"],
            })
        return out

    def verify_integrity(self, project_id: str) -> Dict[str, Any]:
        """
        Cryptographically verifies the entire SHA-256 chain from genesis block to tip (CTL-AUD-01).
        """
        rows = self.conn.execute(
            "SELECT * FROM audit_ledger WHERE project_id = ? ORDER BY sequence_id ASC",
            (project_id,),
        ).fetchall()

        if not rows:
            return {"verified": True, "count": 0, "message": "No records in audit ledger yet."}

        expected_prev = GENESIS_HASH
        for idx, r in enumerate(rows, start=1):
            seq = r["sequence_id"]
            if seq != idx:
                return {
                    "verified": False,
                    "flaw_at_seq": seq,
                    "reason": f"Sequence break: expected {idx}, got {seq}",
                }
            if r["prev_hash"] != expected_prev:
                return {
                    "verified": False,
                    "flaw_at_seq": seq,
                    "reason": f"Broken hash chain at sequence {seq}: prev_hash mismatch",
                }
            recalculated = compute_entry_hash(
                prev_hash=r["prev_hash"],
                sequence_id=seq,
                timestamp=r["timestamp"],
                actor=r["actor"],
                action=r["action"],
                control_id=r["control_id"],
                payload_str=r["details_json"],
            )
            if recalculated != r["entry_hash"]:
                return {
                    "verified": False,
                    "flaw_at_seq": seq,
                    "reason": f"Hash signature invalid at sequence {seq}: recomputed {recalculated} != stored {r['entry_hash']}",
                }
            expected_prev = r["entry_hash"]

        return {
            "verified": True,
            "count": len(rows),
            "tip_hash": expected_prev,
            "message": f"Cryptographic integrity verified: all {len(rows)} records sequentially hashed with 0 tampering.",
        }
