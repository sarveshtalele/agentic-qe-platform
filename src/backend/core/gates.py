"""Quality gates G0-G5. Sequential approval, HMAC-signed records, human signer required."""
from __future__ import annotations

from backend.core import ledger
from backend.core.security import sign, verify_signature
from backend.db import db, now, rows

GATES = {
    0: ("Intake", "Scope, mode and read-only boundaries"),
    1: ("Requirements", "Requirements and stories with evidence"),
    2: ("Plan", "Risk-ranked test strategy"),
    3: ("Design", "Test cases with deterministic oracles"),
    4: ("Generate", "Generated test source reviewed"),
    5: ("Release", "Executed evidence signed off"),
}


# the gate that rests on each kind of document, so editing an approved one reopens that gate and every later gate
DOC_GATE = {"discovery": 1, "requirements": 1, "test_plan": 2, "test_cases": 3, "test_code": 4, "release": 5}


class GateOrderError(ValueError):
    pass


def _message(project_id: str, gate: int, status: str, by: str, stamp: str) -> str:
    return f"{project_id}|{gate}|{status}|{by}|{stamp}"


def status(project_id: str) -> list[dict]:
    with db() as con:
        stored = {r["gate"]: r for r in rows(con.execute("SELECT * FROM gates WHERE project_id=?", (project_id,)))}
    result = []
    for number, (name, description) in GATES.items():
        record = stored.get(number)
        result.append({
            "gate": number, "name": name, "description": description,
            "status": record["status"] if record else "pending",
            "decided_by": record["decided_by"] if record else None,
            "decided_at": record["decided_at"] if record else None,
            "reason": record["reason"] if record else "",
            "signature_valid": verify_signature(
                _message(project_id, number, record["status"], record["decided_by"], record["decided_at"]), record["signature"]
            ) if record else None,
        })
    return result


def is_approved(project_id: str, gate: int) -> bool:
    return next(g for g in status(project_id) if g["gate"] == gate)["status"] == "approved"


def decide(project_id: str, gate: int, approved: bool, by: str, reason: str = "", run_id: str | None = None) -> None:
    if gate not in GATES:
        raise GateOrderError(f"Unknown gate {gate}")
    if not by.strip():
        raise GateOrderError("A named human signer is required")
    if approved and gate > 0 and not is_approved(project_id, gate - 1):
        raise GateOrderError(f"Gate {gate - 1} must be approved before gate {gate}")
    state = "approved" if approved else "rejected"
    stamp = now()
    with db() as con:
        con.execute(
            "INSERT OR REPLACE INTO gates VALUES (?,?,?,?,?,?,?,?)",
            (project_id, gate, state, by, reason, run_id, sign(_message(project_id, gate, state, by, stamp)), stamp),
        )
        if not approved:  # later approvals rested on this gate, so they no longer hold
            con.execute("DELETE FROM gates WHERE project_id=? AND gate>?", (project_id, gate))
    ledger.append(project_id, by, f"gate.{state}", f"G{gate}", {"reason": reason, "run_id": run_id})


def would_reopen(project_id: str, kind: str) -> list[int]:
    """The gates an edit of a document of this kind would reopen: its gate and every later one that holds a decision, when its own gate is approved."""
    gate = DOC_GATE.get(kind)
    if gate is None or not is_approved(project_id, gate):
        return []
    return [g["gate"] for g in status(project_id) if g["gate"] >= gate and g["decided_by"]]


def reopen_for_document(project_id: str, kind: str, by: str, doc_id: str, cause: str) -> list[int]:
    """Editing an approved document: its gate and the later ones return to pending. Each earlier decision, with its signer and signature, stays in the ledger."""
    reopened = would_reopen(project_id, kind)
    if not reopened:
        return []
    with db() as con:
        before = {r["gate"]: r for r in rows(con.execute("SELECT * FROM gates WHERE project_id=? AND gate>=?", (project_id, min(reopened))))}
        con.execute("DELETE FROM gates WHERE project_id=? AND gate>=?", (project_id, min(reopened)))
    for number in reopened:
        old = before.get(number, {})
        ledger.append(project_id, by, "gate.reopened", f"G{number}", {"cause": cause, "document": doc_id, "kind": kind, "was": old.get("status"), "decided_by": old.get("decided_by"),
                                                                   "decided_at": old.get("decided_at"), "signature": old.get("signature"), "run_id": old.get("run_id")})
    return reopened
