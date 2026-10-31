from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .ledger import AuditLedger

GATE_NAMES = {
    0: "Gate 0: Discovery & Context Validation",
    1: "Gate 1: Requirements Baseline Approval",
    2: "Gate 2: Test Architecture & Risk Strategy",
    3: "Gate 3: Test Design & Deterministic Oracles",
    4: "Gate 4: Sandboxed Test Execution",
    5: "Gate 5: Release Sign-off & Confidence Score",
}

GATE_CONTROLS = {
    0: "CTL-GATE-00",
    1: "CTL-GATE-01",
    2: "CTL-GATE-02",
    3: "CTL-GATE-03",
    4: "CTL-GATE-04",
    5: "CTL-GATE-05",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class GateController:
    """
    Manages the 6-Gate SDLC Quality Lifecycle (Gates 0-5) enforcing sequential prerequisites.
    """

    def __init__(self, db_conn: sqlite3.Connection, ledger: AuditLedger):
        self.conn = db_conn
        self.ledger = ledger
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quality_gates (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                gate_number INTEGER NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                decision_by TEXT NOT NULL DEFAULT '',
                decision_reason TEXT NOT NULL DEFAULT '',
                decision_timestamp TEXT,
                evidence_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, gate_number)
            );
            """
        )
        self.conn.commit()

    def initialize_project_gates(self, project_id: str) -> None:
        """Initializes all 6 quality gates for a project in PENDING status if not already present."""
        now = now_iso()
        for gate_num, name in GATE_NAMES.items():
            gate_id = str(uuid.uuid4())
            self.conn.execute(
                """
                INSERT OR IGNORE INTO quality_gates (id, project_id, gate_number, name, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'PENDING', ?, ?)
                """,
                (gate_id, project_id, gate_num, name, now, now),
            )
        self.conn.commit()

    def get_gates(self, project_id: str) -> List[Dict[str, Any]]:
        self.initialize_project_gates(project_id)
        rows = self.conn.execute(
            "SELECT * FROM quality_gates WHERE project_id = ? ORDER BY gate_number ASC",
            (project_id,),
        ).fetchall()
        gates = []
        for r in rows:
            gates.append({
                "id": r["id"],
                "project_id": r["project_id"],
                "gate_number": r["gate_number"],
                "name": r["name"],
                "control_id": GATE_CONTROLS.get(r["gate_number"], "CTL-GATE"),
                "status": r["status"],
                "decision_by": r["decision_by"],
                "decision_reason": r["decision_reason"],
                "decision_timestamp": r["decision_timestamp"],
                "evidence": json.loads(r["evidence_json"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            })
        return gates

    def record_decision(
        self,
        project_id: str,
        gate_number: int,
        decision: str,  # APPROVED | REJECTED | IN_PROGRESS
        actor: str,
        reason: str = "",
        evidence: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Records a human or agent gate transition, verifying sequential gate progression.
        """
        if gate_number not in GATE_NAMES:
            raise ValueError(f"Invalid gate number {gate_number}. Must be 0 through 5.")

        decision = decision.upper()
        if decision not in {"APPROVED", "REJECTED", "IN_PROGRESS", "PENDING"}:
            raise ValueError(f"Invalid decision '{decision}'.")

        self.initialize_project_gates(project_id)

        # Sequential Prerequisite Check: To APPROVE Gate N, Gate N-1 must already be APPROVED
        if decision == "APPROVED" and gate_number > 0 and not force:
            prev_row = self.conn.execute(
                "SELECT status FROM quality_gates WHERE project_id = ? AND gate_number = ?",
                (project_id, gate_number - 1),
            ).fetchone()
            if not prev_row or prev_row["status"] != "APPROVED":
                raise ValueError(
                    f"Prerequisite failure: Gate {gate_number - 1} must be APPROVED before Gate {gate_number} can be approved."
                )

        now = now_iso()
        ev_json = json.dumps(evidence or {})
        control_id = GATE_CONTROLS[gate_number]

        self.conn.execute(
            """
            UPDATE quality_gates
            SET status = ?, decision_by = ?, decision_reason = ?, decision_timestamp = ?, evidence_json = ?, updated_at = ?
            WHERE project_id = ? AND gate_number = ?
            """,
            (decision, actor, reason, now, ev_json, now, project_id, gate_number),
        )
        self.conn.commit()

        # Record to immutable cryptographic audit ledger (CTL-AUD-01)
        self.ledger.append(
            project_id=project_id,
            actor=actor,
            action=f"GATE_{decision}",
            control_id=control_id,
            details={
                "gate_number": gate_number,
                "gate_name": GATE_NAMES[gate_number],
                "decision": decision,
                "reason": reason,
                "evidence": evidence or {},
            },
            timestamp=now,
        )

        return {
            "project_id": project_id,
            "gate_number": gate_number,
            "gate_name": GATE_NAMES[gate_number],
            "control_id": control_id,
            "status": decision,
            "actor": actor,
            "reason": reason,
            "timestamp": now,
        }
