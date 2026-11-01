from __future__ import annotations

import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .ledger import AuditLedger


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class HITLManager:
    """
    Manages interactive Human-In-The-Loop approval gates (CTL-HITL-01, CTL-HITL-02, CTL-HITL-03).
    """

    def __init__(self, db_conn: sqlite3.Connection, ledger: AuditLedger):
        self.conn = db_conn
        self.ledger = ledger
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approval_requests (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                control_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                target TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'PENDING',
                nonce TEXT NOT NULL UNIQUE,
                decided_by TEXT,
                decision_reason TEXT,
                created_at TEXT NOT NULL,
                resolved_at TEXT
            );
            """
        )
        self.conn.commit()

    def create_request(
        self,
        session_id: str,
        project_id: str,
        control_id: str,
        action_type: str,
        target: str,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Creates a pending HITL approval request with an unguessable one-time nonce."""
        req_id = str(uuid.uuid4())
        nonce = secrets.token_hex(16)
        now = now_iso()
        details_str = json.dumps(details)

        self.conn.execute(
            """
            INSERT INTO approval_requests (id, session_id, project_id, control_id, action_type, target, details_json, status, nonce, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
            """,
            (req_id, session_id, project_id, control_id, action_type, target, details_str, nonce, now),
        )
        self.conn.commit()

        # Audit log creation
        self.ledger.append(
            project_id=project_id,
            actor="System:HITLManager",
            action="APPROVAL_REQUESTED",
            control_id=control_id,
            details={
                "request_id": req_id,
                "session_id": session_id,
                "action_type": action_type,
                "target": target,
                "details": details,
            },
            timestamp=now,
        )

        return {
            "id": req_id,
            "session_id": session_id,
            "project_id": project_id,
            "control_id": control_id,
            "action_type": action_type,
            "target": target,
            "details": details,
            "status": "PENDING",
            "nonce": nonce,
            "created_at": now,
        }

    def resolve_request(
        self,
        nonce: str,
        decision: str,  # APPROVED | REJECTED
        decided_by: str,
        reason: str = "",
    ) -> Dict[str, Any]:
        """Resolves an approval request using its one-time nonce."""
        row = self.conn.execute(
            "SELECT * FROM approval_requests WHERE nonce = ?",
            (nonce,),
        ).fetchone()

        if not row:
            raise ValueError("Invalid or unknown approval nonce.")

        if row["status"] != "PENDING":
            raise ValueError(f"Approval request already resolved as {row['status']}.")

        decision_upper = decision.upper()
        if decision_upper not in {"APPROVED", "REJECTED"}:
            raise ValueError("Decision must be 'APPROVED' or 'REJECTED'.")

        now = now_iso()
        self.conn.execute(
            """
            UPDATE approval_requests
            SET status = ?, decided_by = ?, decision_reason = ?, resolved_at = ?
            WHERE nonce = ?
            """,
            (decision_upper, decided_by, reason, now, nonce),
        )
        self.conn.commit()

        # Audit log resolution
        self.ledger.append(
            project_id=row["project_id"],
            actor=decided_by,
            action=f"APPROVAL_{decision_upper}",
            control_id=row["control_id"],
            details={
                "request_id": row["id"],
                "session_id": row["session_id"],
                "action_type": row["action_type"],
                "target": row["target"],
                "decision": decision_upper,
                "reason": reason,
            },
            timestamp=now,
        )

        return {
            "id": row["id"],
            "session_id": row["session_id"],
            "project_id": row["project_id"],
            "control_id": row["control_id"],
            "status": decision_upper,
            "decided_by": decided_by,
            "reason": reason,
            "resolved_at": now,
        }

    def get_pending(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM approval_requests WHERE status = 'PENDING'"
        params = []
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        query += " ORDER BY created_at DESC"

        rows = self.conn.execute(query, tuple(params)).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r["id"],
                "session_id": r["session_id"],
                "project_id": r["project_id"],
                "control_id": r["control_id"],
                "action_type": r["action_type"],
                "target": r["target"],
                "details": json.loads(r["details_json"]),
                "status": r["status"],
                "nonce": r["nonce"],
                "created_at": r["created_at"],
            })
        return out
