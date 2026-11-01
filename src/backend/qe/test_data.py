"""Deterministic test data. Port of the generating-test-data skill's synthesize-data.ts, with its shapes unchanged.

No real personal data: addresses are @example.com, tokens are obviously fake, and e-mail or ID-like numbers in a case's own data are masked.
No model call is made here, so the stage costs no tokens.
"""
from __future__ import annotations

import json
import re

from backend.core.security import redact

FIXTURE_LIMIT = 40_000  # characters of fixtures.json
MAX_SAFE_INTEGER = 2**53 - 1
ROLES = ("admin", "customer", "viewer")


def synthesize_user(role: str = "customer", valid: bool = True) -> dict:
    if not valid:
        return {"id": "invalid-id", "email": "not-an-email", "role": "unauthorized-role"}
    return {"id": f"usr_{role}_001", "email": f"testuser_{role}@example.com", "role": role}


def boundary_payload(kind: str) -> dict:
    if kind == "string":
        return {"empty": "", "whitespaceOnly": "   \t\n  ", "maxLength1024": "A" * 1024, "specialCharacters": "<script>alert('xss')</script>' OR 1=1; -- 🚀 漢字", "unicodeEmoji": "🔥💻🧪🎯✨"}
    if kind == "number":
        return {"zero": 0, "negativeOne": -1, "minSafeInteger": -MAX_SAFE_INTEGER, "maxSafeInteger": MAX_SAFE_INTEGER, "floatingPointPrecision": 0.1 + 0.2}
    if kind == "json":
        return {"emptyObject": {}, "emptyArray": [], "deeplyNested": {"l1": {"l2": {"l3": {"l4": {"value": "deep"}}}}}, "nullFields": {"name": None, "count": None}}
    raise ValueError(f"unknown boundary type '{kind}'")


def pagination(items: list, page_size: int = 10, page_index: int = 0) -> dict:
    if page_size < 1:
        raise ValueError("page_size must be at least 1")
    start = page_index * page_size
    total_pages = -(-len(items) // page_size)
    return {"items": items[start:start + page_size], "pageIndex": page_index, "pageSize": page_size, "totalItems": len(items), "totalPages": total_pages,
            "hasNextPage": page_index < total_pages - 1, "hasPrevPage": page_index > 0}


def auth_headers(role: str = "customer", valid: bool = True) -> dict:
    if not valid:
        return {"Authorization": "Bearer invalid_or_expired_token", "X-User-Role": "anonymous", "Content-Type": "application/json"}
    return {"Authorization": f"Bearer mock_jwt_token_for_{role}", "X-User-Role": role, "Content-Type": "application/json"}


def synthesize(spec: dict) -> dict:
    """The skill's CLI as a function: {"kind": "user|boundary|pagination|auth", ...}."""
    kind = spec.get("kind")
    if kind == "user":
        return synthesize_user(spec.get("role", "customer"), spec.get("valid", True))
    if kind == "boundary":
        return boundary_payload(spec.get("type", ""))
    if kind == "pagination":
        return pagination(spec.get("items", []), spec.get("pageSize", 10), spec.get("pageIndex", 0))
    if kind == "auth":
        return auth_headers(spec.get("role", "customer"), spec.get("valid", True))
    raise ValueError(f"unknown kind '{kind}'")


EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ID_NUMBER = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b(?:\d[ -]?){13,19}\b")


def mask(text: str) -> str:
    """ponytail: three patterns (secrets via redact, e-mail addresses, SSN-like and card-like numbers). Names and addresses are not recognised."""
    text = EMAIL.sub("masked@example.com", redact(text or ""))
    return ID_NUMBER.sub("0000-MASKED", text)


def _kinds(case: dict) -> list[str]:
    """Which shared datasets a case uses, from its type and wording. A case with none still gets its own data."""
    text = f"{case.get('scenario', '')} {case.get('test_data', '')} {' '.join(case.get('steps', []))} {case.get('expected_result', '')}".lower()
    kinds = []
    if "boundary" in case.get("type", "").lower() or re.search(r"\b(empty|maximum|minimum|overflow|zero|negative|too long|special character|unicode)\b", text):
        kinds += ["boundary.string", "boundary.number"] if re.search(r"\b(string|text|name|empty|special|unicode|long)\b", text) else ["boundary.number"]
    if re.search(r"\b(auth|token|login|password|permission|unauthori[sz]ed|forbidden|role)\b", text):
        kinds.append("auth")
    if re.search(r"\b(user|customer|admin|account|profile)\b", text):
        kinds.append("users")
    if re.search(r"\b(page|pagination|paginate|offset|limit)\b", text):
        kinds.append("pagination")
    if re.search(r"\b(json|payload|body|null)\b", text):
        kinds.append("boundary.json")
    return list(dict.fromkeys(kinds))


def build_fixtures(cases: list[dict]) -> dict:
    """fixtures.json: shared datasets once, and a short entry per case saying which it uses and its own (masked) data."""
    used = {k for c in cases for k in _kinds(c)}
    shared: dict = {}
    if "users" in used:
        shared["users"] = {f"{role}{'' if ok else 'Invalid'}": synthesize_user(role, ok) for role in ROLES for ok in (True, False) if ok or role == "customer"}
    if "auth" in used:
        shared["auth"] = {"valid": auth_headers("customer"), "admin": auth_headers("admin"), "invalid": auth_headers("customer", False)}
    for kind in ("string", "number", "json"):
        if f"boundary.{kind}" in used:
            shared.setdefault("boundary", {})[kind] = boundary_payload(kind)
    if "pagination" in used:
        shared["pagination"] = {"firstPage": pagination([f"item-{n}" for n in range(1, 26)], 10, 0), "lastPage": pagination([f"item-{n}" for n in range(1, 26)], 10, 2), "empty": pagination([], 10, 0)}
    entries = {c["id"]: {"data": mask(c.get("test_data", ""))[:500], "uses": _kinds(c)} for c in cases if c.get("test_data") or _kinds(c)}
    fixtures = {"datasets": shared, "cases": entries}
    while len(json.dumps(fixtures)) > FIXTURE_LIMIT and shared:  # bounded: the bulky shared sets go first
        shared.pop(max(shared, key=lambda k: len(json.dumps(shared[k]))))
        fixtures["truncated"] = True
    return fixtures
