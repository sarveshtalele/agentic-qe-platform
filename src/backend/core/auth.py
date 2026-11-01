"""Accounts and access. The admin login comes from .env. Users are created by the admin.

Passwords are salted scrypt hashes, usernames are encrypted at rest, and sessions are stored only as hashes.
Nothing here logs a username or password: audit records use the account's id.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone

from backend.core.errors import AllowanceError  # noqa: F401 - re-exported; callers use auth.AllowanceError
from backend.core.security import decrypt, encrypt, encryption_key, register_secret
from backend.db import db, new_id, now, row, rows

ADMIN_ID = "admin"
COOKIE = "aqe_session"
SESSION_HOURS = int(os.environ.get("ATLAS_SESSION_HOURS", "12"))
MAX_FAILURES = 5
LOCK_SECONDS = 300
EVAL_PROJECT = "prj_agent_evals"

current_user: ContextVar[dict | None] = ContextVar("current_user", default=None)
_failures: dict[str, tuple[int, float]] = {}  # ponytail: one process. Move to the database before running several instances
_failures_lock = threading.Lock()


class AuthError(ValueError):
    pass


def _admin_login() -> tuple[str, str]:
    username, password = os.environ.get("ATLAS_ADMIN_USERNAME", ""), os.environ.get("ATLAS_ADMIN_PASSWORD", "")
    register_secret(password)
    return username.strip().lower(), password


def admin_configured() -> bool:
    return all(_admin_login())


def _lookup(username: str) -> str:
    return hmac.new(encryption_key(), username.strip().lower().encode(), hashlib.sha256).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"scrypt${salt.hex()}${hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1).hex()}"


def _verify_password(password: str, stored: str) -> bool:
    _, salt, digest = stored.split("$")
    return hmac.compare_digest(hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1).hex(), digest)


_DUMMY_HASH = hash_password(secrets.token_hex(8))


def _event(subject: str, event: str) -> None:
    with db() as con:
        con.execute("INSERT INTO auth_events (subject, event, created_at) VALUES (?,?,?)", (subject, event, now()))


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _inactive_reason(user: dict) -> str:
    if not user["enabled"]:
        return "This account is disabled"
    if user["active_from"] and _today() < user["active_from"]:
        return f"This account starts on {user['active_from']}"
    if user["active_until"] and _today() > user["active_until"]:
        return f"This account ended on {user['active_until']}"
    return ""


def login(username: str, password: str) -> str:
    """Returns a session token. Every failure gives the same message, so it does not reveal which accounts exist."""
    key = _lookup(username)
    with _failures_lock:
        count, until = _failures.get(key, (0, 0.0))
        if count >= MAX_FAILURES and time.time() < until:
            raise AuthError("Too many attempts. Try again in a few minutes")
    admin_name, admin_password = _admin_login()
    account = None
    if admin_name and admin_password and hmac.compare_digest(username.strip().lower().encode(), admin_name.encode()):
        ok = hmac.compare_digest(password.encode(), admin_password.encode())
        subject = ADMIN_ID
    else:
        with db() as con:
            account = row(con.execute("SELECT * FROM users WHERE username_lookup=?", (key,)))
        ok = _verify_password(password, account["password_hash"] if account else _DUMMY_HASH) and bool(account)
        subject = account["id"] if account else "unknown"
    if not ok:
        with _failures_lock:
            _failures[key] = (count + 1, time.time() + LOCK_SECONDS)
        _event(subject, "login.failed")
        raise AuthError("The username or password is not correct")
    if account and (reason := _inactive_reason(account)):
        _event(subject, "login.refused")
        raise AuthError(reason)
    with _failures_lock:
        _failures.pop(key, None)
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)).isoformat(timespec="seconds")
    with db() as con:
        con.execute("INSERT INTO sessions VALUES (?,?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), subject, expires, now()))
    _event(subject, "login")
    return token


def logout(token: str) -> None:
    with db() as con:
        con.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))


def session_user(token: str | None) -> dict | None:
    if not token:
        return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    with db() as con:
        session = row(con.execute("SELECT * FROM sessions WHERE token_hash=?", (digest,)))
        if not session:
            return None
        if session["expires_at"] < now():
            con.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))
            return None
        if session["user_id"] == ADMIN_ID:
            return {"id": ADMIN_ID, "role": "admin"}
        account = row(con.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)))
        if not account or _inactive_reason(account):
            con.execute("DELETE FROM sessions WHERE user_id=?", (session["user_id"],))
            return None
    return {"id": account["id"], "role": "user"}


def signer() -> str:
    """The signed-in account's id: the only identity written to the ledger, gates, and versions. Never taken from a request body."""
    user = current_user.get()
    if not user:
        raise AuthError("Sign in first")
    return user["id"]


def display_names(ids: set[str]) -> dict[str, str]:
    """Account id to a name for this viewer. A username is a login detail, so only its owner and the admin see it."""
    viewer = current_user.get() or {}
    names = {}
    for found in ids:
        if found == ADMIN_ID:
            names[found] = "Administrator"
        elif found.startswith("usr_") and (viewer.get("role") == "admin" or viewer.get("id") == found):
            try:
                names[found] = get_user(found)["username"]
            except KeyError:
                pass
    return names


def tokens_used(user_id: str) -> int:
    with db() as con:
        found = con.execute("SELECT COALESCE(SUM(c.tokens_in + c.tokens_out), 0) FROM agent_calls c JOIN projects p ON p.id=c.project_id WHERE p.owner_id=?", (user_id,)).fetchone()
    return found[0]


def _public(account: dict) -> dict:
    return {"id": account["id"], "username": decrypt(account["username_enc"].encode()), "role": "user", "model": account["model"], "token_limit": account["token_limit"], "tokens_used": tokens_used(account["id"]),
            "active_from": account["active_from"], "active_until": account["active_until"], "enabled": bool(account["enabled"]), "status": _inactive_reason(account) or "Active", "created_at": account["created_at"]}


def describe(user: dict) -> dict:
    if user["role"] == "admin":
        return {"id": ADMIN_ID, "username": _admin_login()[0], "role": "admin", "model": "", "token_limit": None, "tokens_used": tokens_used(ADMIN_ID), "active_from": None, "active_until": None, "enabled": True, "status": "Active"}
    with db() as con:
        return _public(row(con.execute("SELECT * FROM users WHERE id=?", (user["id"],))))


def check_password_rules(password: str) -> None:
    if len(password) < 10:
        raise AuthError("Passwords need at least 10 characters")


def _check_dates(active_from: str | None, active_until: str | None) -> None:
    if active_from and active_until and active_until < active_from:
        raise AuthError("The end date is before the start date")


def create_user(username: str, password: str, model: str = "", token_limit: int | None = None, active_from: str | None = None, active_until: str | None = None) -> dict:
    username = username.strip()
    if not re.fullmatch(r"[\w.@-]{3,60}", username):
        raise AuthError("Usernames need 3 to 60 letters, numbers, dots, dashes, or @")
    if username.lower() == _admin_login()[0]:
        raise AuthError("That username is not available")
    check_password_rules(password)
    _check_dates(active_from, active_until)
    with db() as con:
        if con.execute("SELECT 1 FROM users WHERE username_lookup=?", (_lookup(username),)).fetchone():
            raise AuthError("That username is not available")
        user_id = new_id("usr")
        con.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,1,?,?)", (user_id, _lookup(username), encrypt(username).decode(), hash_password(password), model.strip(), token_limit, active_from or None, active_until or None, now(), now()))
    _event(user_id, "user.created")
    return get_user(user_id)


def get_user(user_id: str) -> dict:
    with db() as con:
        account = row(con.execute("SELECT * FROM users WHERE id=?", (user_id,)))
    if not account:
        raise KeyError(user_id)
    return _public(account)


def list_users() -> list[dict]:
    with db() as con:
        return [_public(u) for u in rows(con.execute("SELECT * FROM users ORDER BY created_at DESC"))]


def update_user(user_id: str, changes: dict) -> dict:
    """Changes only the fields given. A new password or a disabled account ends that user's sessions."""
    get_user(user_id)
    fields = {k: changes[k] for k in ("model", "token_limit", "active_from", "active_until", "enabled") if k in changes}
    if changes.get("password"):
        check_password_rules(changes["password"])
        fields["password_hash"] = hash_password(changes["password"])
    with db() as con:
        current = row(con.execute("SELECT active_from, active_until FROM users WHERE id=?", (user_id,)))
        _check_dates(fields.get("active_from", current["active_from"]), fields.get("active_until", current["active_until"]))
        for name, value in fields.items():
            stored = int(value) if name == "enabled" else (value or None) if name in {"active_from", "active_until"} else value
            con.execute(f"UPDATE users SET {name}=?, updated_at=? WHERE id=?", (stored, now(), user_id))  # names come from the fixed list above
        if "password_hash" in fields or fields.get("enabled") is False:
            con.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    _event(user_id, "user.updated")
    return get_user(user_id)


def recent_events(limit: int = 50) -> list[dict]:
    with db() as con:
        return rows(con.execute("SELECT * FROM auth_events ORDER BY id DESC LIMIT ?", (limit,)))


# ---- what a project's work may use ---------------------------------------------

def _owner(project_id: str) -> dict | None:
    with db() as con:
        found = con.execute("SELECT owner_id FROM projects WHERE id=?", (project_id,)).fetchone()
        if not found or not found[0] or found[0] == ADMIN_ID:
            return None
        return row(con.execute("SELECT * FROM users WHERE id=?", (found[0],)))


def check_allowance(project_id: str) -> None:
    """Runs and chats belong to the project's owner, so background work is limited the same way as a page request."""
    owner = _owner(project_id)
    if not owner:
        return
    if reason := _inactive_reason(owner):
        raise AllowanceError(f"{reason}. Ask your administrator")
    if owner["token_limit"] is not None and tokens_used(owner["id"]) >= owner["token_limit"]:
        raise AllowanceError(f"This account has used its allocation of {owner['token_limit']:,} tokens. Ask your administrator")


def current_user_model() -> str:
    user = current_user.get()
    if not user or user["role"] == "admin":
        return ""
    with db() as con:
        found = con.execute("SELECT model FROM users WHERE id=?", (user["id"],)).fetchone()
    return found[0] if found else ""


def model_for(project_id: str) -> str:
    owner = _owner(project_id)
    return owner["model"] if owner else ""


# ---- who may reach what ---------------------------------------------------------

OWNED_PATHS = [
    (re.compile(r"^/api/projects/([^/]+)"), "SELECT id AS project_id FROM projects WHERE id=?"),
    (re.compile(r"^/api/documents/([^/]+)"), "SELECT project_id FROM documents WHERE id=?"),
    (re.compile(r"^/api/runs/([^/]+)"), "SELECT project_id FROM runs WHERE id=?"),
    (re.compile(r"^/api/findings/([^/]+)"), "SELECT project_id FROM findings WHERE id=?"),
    (re.compile(r"^/api/approvals/([^/]+)"), "SELECT project_id FROM approvals WHERE id=?"),
    (re.compile(r"^/api/chats/([^/]+)"), "SELECT project_id FROM chat_threads WHERE id=?"),
    (re.compile(r"^/api/memories/([^/]+)"), "SELECT project_id FROM memories WHERE id=?"),
]
ADMIN_ONLY = re.compile(r"^/api/(users|connections|logs|auth/events)(/|$)|^/api/agents/guardrail-events$|^/api/projects/[^/]+/repo/local$")
ADMIN_WRITES = re.compile(r"^/api/(settings|prompts|agents|evals)(/|$)")


def can_see_project(project_id: str | None, user: dict | None = None) -> bool:
    user = user or current_user.get()
    if not user:
        return False
    if user["role"] == "admin":
        return True
    if not project_id or project_id == EVAL_PROJECT:
        return False
    with db() as con:
        found = con.execute("SELECT owner_id FROM projects WHERE id=?", (project_id,)).fetchone()
    return bool(found) and found[0] == user["id"]


def access_problem(method: str, path: str, user: dict) -> int | None:
    """Returns the status to refuse with. Someone else's item answers 404, so its existence is not revealed."""
    if user["role"] == "admin":
        return None
    if ADMIN_ONLY.search(path) or (method not in {"GET", "HEAD"} and ADMIN_WRITES.search(path)):
        return 403
    for pattern, query in OWNED_PATHS:
        if match := pattern.match(path):
            with db() as con:
                found = con.execute(query, (match.group(1),)).fetchone()
            return None if found and can_see_project(found[0], user) else 404
    return None
