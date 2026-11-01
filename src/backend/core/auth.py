"""Accounts and access. The admin login comes from .env. Users are created by the admin.

Passwords are salted scrypt hashes, usernames are encrypted at rest, and sessions are stored only as hashes.
Nothing here logs a username or password: audit records use the account's id.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone

from backend.core import ledger, models
from backend.core.errors import AllowanceError  # noqa: F401 - re-exported; callers use auth.AllowanceError
from backend.core.security import decrypt, encrypt, encryption_key, register_secret
from backend.db import db, new_id, now, row, rows

ADMIN_ID = "admin"
COOKIE = "aqe_session"
SESSION_HOURS = int(os.environ.get("ATLAS_SESSION_HOURS", "12"))
IDLE_MINUTES = int(os.environ.get("ATLAS_SESSION_IDLE_MINUTES", "480"))
ROLES = ("qe_lead", "ba", "developer", "viewer")
ROLE_NAMES = {"admin": "administrator", "qe_lead": "QE lead", "ba": "BA", "developer": "developer", "viewer": "viewer"}
MAX_FAILURES = 5
LOCK_SECONDS = 300
EVAL_PROJECT = "prj_agent_evals"

current_user: ContextVar[dict | None] = ContextVar("current_user", default=None)
_failures: dict[str, tuple[int, float]] = {}  # ponytail: one process. Move to the database before running several instances
_failures_lock = threading.Lock()


def clock() -> datetime:
    return datetime.now(timezone.utc)  # tests replace this to move time


class AuthError(ValueError):
    pass


class Forbidden(AuthError):
    """The signed-in account is known but its role does not allow this. Answered 403 with the message."""


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
        con.execute("INSERT INTO sessions VALUES (?,?,?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), subject, expires, now(), clock().isoformat(timespec="seconds")))
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
        seen = clock()
        last = datetime.fromisoformat(session["last_seen"]) if session["last_seen"] else seen
        if session["expires_at"] < now() or seen - last > timedelta(minutes=IDLE_MINUTES):
            con.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))
            return None
        if not session["last_seen"] or seen - last >= timedelta(seconds=60):  # ponytail: written once a minute, so a busy page does not write on every request
            con.execute("UPDATE sessions SET last_seen=? WHERE token_hash=?", (seen.isoformat(timespec="seconds"), digest))
        if session["user_id"] == ADMIN_ID:
            return {"id": ADMIN_ID, "role": "admin", "account_role": "admin"}
        account = row(con.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)))
        if not account or _inactive_reason(account):
            con.execute("DELETE FROM sessions WHERE user_id=?", (session["user_id"],))
            return None
    return {"id": account["id"], "role": "user", "account_role": account["role"]}


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
    """Everything the account started, whichever project it ran in."""
    return models.used(user_id)


def _public(account: dict) -> dict:
    uid = account["id"]
    limits = models.limits(uid)
    return {"id": uid, "username": decrypt(account["username_enc"].encode()), "role": "user", "account_role": account["role"], "model": account["model"], "models": models.ticked(uid), "token_limit": account["token_limit"], "tokens_used": tokens_used(uid),
            "limits": {p: next((i["tokens"] for i in limits if not i["model"] and i["period"] == p), None) for p in models.PERIODS}, "model_limits": [i for i in limits if i["model"]],
            "usage": models.usage(uid), "model_usage": {i["model"]: models.used(uid, models.bounds(i["period"])[0], i["model"]) for i in limits if i["model"]},
            "active_from": account["active_from"], "active_until": account["active_until"], "enabled": bool(account["enabled"]), "status": _inactive_reason(account) or "Active", "created_at": account["created_at"]}


def describe(user: dict) -> dict:
    if user["role"] == "admin":
        return {"id": ADMIN_ID, "username": _admin_login()[0], "role": "admin", "account_role": "admin", "model": "", "models": [], "token_limit": None, "tokens_used": tokens_used(ADMIN_ID), "limits": {}, "model_limits": [], "usage": None,
                "active_from": None, "active_until": None, "enabled": True, "status": "Active"}
    with db() as con:
        return _public(row(con.execute("SELECT * FROM users WHERE id=?", (user["id"],))))


def check_role(role: str) -> None:
    if role not in ROLES:
        raise AuthError(f"A role is one of: {', '.join(ROLES)}")


def check_password_rules(password: str) -> None:
    if len(password) < 10:
        raise AuthError("Passwords need at least 10 characters")


def _check_dates(active_from: str | None, active_until: str | None) -> None:
    if active_from and active_until and active_until < active_from:
        raise AuthError("The end date is before the start date")


def create_user(username: str, password: str, model: str = "", token_limit: int | None = None, active_from: str | None = None, active_until: str | None = None, allowed_models: list[str] | None = None, role: str = "developer") -> dict:
    username = username.strip()
    check_role(role)
    if not re.fullmatch(r"[\w.@-]{3,60}", username):
        raise AuthError("Usernames need 3 to 60 letters, numbers, dots, dashes, or @")
    if username.lower() == _admin_login()[0]:
        raise AuthError("That username is not available")
    check_password_rules(password)
    _check_dates(active_from, active_until)
    allowed_models = allowed_models if allowed_models is not None else ([model.strip()] if model.strip() else [])
    try:
        model = models.check_allowed(allowed_models, model.strip())
    except ValueError as exc:
        raise AuthError(str(exc)) from exc
    with db() as con:
        if con.execute("SELECT 1 FROM users WHERE username_lookup=?", (_lookup(username),)).fetchone():
            raise AuthError("That username is not available")
        user_id = new_id("usr")
        con.execute("INSERT INTO users (id, username_lookup, username_enc, password_hash, model, token_limit, active_from, active_until, enabled, created_at, updated_at, role) VALUES (?,?,?,?,?,?,?,?,1,?,?,?)",
                    (user_id, _lookup(username), encrypt(username).decode(), hash_password(password), model.strip(), token_limit, active_from or None, active_until or None, now(), now(), role))
    models.set_allowed(user_id, allowed_models, model)
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
    current_user_record = get_user(user_id)
    fields = {k: changes[k] for k in ("model", "token_limit", "active_from", "active_until", "enabled", "role") if k in changes}
    if "role" in fields:
        check_role(fields["role"])
    if "models" in changes or "model" in changes:  # the default is always one of the ticked models
        names = changes["models"] if "models" in changes else current_user_record["models"]
        wanted = changes["model"] if "model" in changes else (current_user_record["model"] if current_user_record["model"] in names else "")
        try:
            fields["model"] = models.check_allowed(names, wanted)
        except ValueError as exc:
            raise AuthError(str(exc)) from exc
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
    try:
        if "models" in changes:
            models.set_allowed(user_id, changes["models"], fields["model"])
        if "limits" in changes or "model_limits" in changes:
            models.set_limits(user_id, changes.get("limits"), changes.get("model_limits"))
    except (ValueError, KeyError, TypeError) as exc:
        raise AuthError(f"Limits or models not saved: {exc}") from exc
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


def _account(user_id: str | None) -> dict | None:
    """The limited account for an id, or None for the administrator and for work with no account behind it."""
    if not user_id or user_id == ADMIN_ID:
        return None
    with db() as con:
        return row(con.execute("SELECT * FROM users WHERE id=?", (user_id,)))


def acting_user(project_id: str, run_id: str | None = None) -> str | None:
    """Whose tokens a call spends: the account that started the run, else the signed-in account, else the project's owner."""
    if run_id:
        with db() as con:
            found = con.execute("SELECT user_id FROM runs WHERE id=?", (run_id,)).fetchone()
        if found and found[0]:
            return found[0]
    if user := current_user.get():
        return user["id"]
    owner = _owner(project_id)
    return owner["id"] if owner else None


def check_allowance(project_id: str, user_id: str | None = None, model: str = "") -> None:
    """Dates, the overall allocation, then the daily, weekly, monthly, and per-model limits, for the account that is spending."""
    account = _account(user_id or acting_user(project_id))
    if not account:
        return
    if reason := _inactive_reason(account):
        raise AllowanceError(f"{reason}. Ask your administrator")
    if account["token_limit"] is not None and tokens_used(account["id"]) >= account["token_limit"]:
        raise AllowanceError(f"This account has used its allocation of {account['token_limit']:,} tokens. Ask your administrator")
    if problem := models.limit_problem(account["id"], model):
        raise problem


def permit_model(user_id: str | None, name: str) -> str:
    """The one place a model is allowed or refused: the run form, chat, an agent's model, and the default all end here. A refusal is logged by account id."""
    account = _account(user_id)
    if account:
        allowed = models.allowed(account["id"])
        if not allowed:
            _event(account["id"], "model.refused:none")
            raise AllowanceError("No models are allowed for this account. Ask your administrator to tick at least one model for you")
        if name not in allowed:
            _event(account["id"], f"model.refused:{name}")
            raise AllowanceError(f"The model {name or '(none)'} is not allowed for this account. Choose one of: {', '.join(allowed)}. Or ask your administrator", model=name)
    elif models.is_disabled(name):
        raise AllowanceError(f"The model {name} is switched off in Settings")
    return name


def model_for(project_id: str, agent_key: str = "", run_id: str | None = None, user_id: str | None = None, choice: str = "") -> str:
    """Which model a call uses, first match wins: this run's or chat's choice, the agent's model, the user's default, the system default. Always checked."""
    user_id = user_id or acting_user(project_id, run_id)
    account = _account(user_id)
    if run_id and not choice:
        with db() as con:
            found = con.execute("SELECT model FROM runs WHERE id=?", (run_id,)).fetchone()
        choice = found[0] if found else ""
    from backend.maf import llm  # late: llm imports the database layer only, but this keeps core free of maf at import time

    name = choice or models.agent_model(agent_key) or (account["model"] if account else "") or models.system_default(llm.current()["model"])
    if not name and not account:
        return ""  # nothing configured: the client then says so
    return permit_model(user_id, name)


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
ADMIN_ONLY = re.compile(r"^/api/(users|connections|logs|auth/events|models|usage)(/|$)|^/api/agents/guardrail-events$|^/api/projects/[^/]+/(repo/local|transfer)$")
ADMIN_WRITES = re.compile(r"^/api/(settings|prompts|agents|evals)(/|$)")
OWNER_ONLY = re.compile(r"^/api/projects/[^/]+/members(/|$)")  # also the admin
OWNER_DELETE = re.compile(r"^/api/projects/[^/]+$")
# Signed-in users with no project in the path. A path in none of these lists is refused, so a new route has to be added here or above.
SESSION_ONLY = re.compile(r"^(/agui/[^/]+|/api/(auth/(me|logout)|account/password|chat/agents|approvals|documents|findings|projects|observability(/errors|/export)?|templates(/upload|/[^/]+)?"
                          r"|prompts(/[^/]+)?|agents(/[^/]+)?|evals(/[^/]+)?|settings/(llm|models|timezone|gate-roles)))$")
VIEWER_MAY_WRITE = re.compile(r"^/api/(auth/logout|account/password)$")  # a viewer can still sign out and change their own password
WRITES = {"POST", "PUT", "PATCH", "DELETE"}


def rule_of(path: str) -> str | None:
    """Which rule covers a path: admin, owned, session, or None when no rule does."""
    if ADMIN_ONLY.search(path):
        return "admin"
    if any(p.match(path) for p, _ in OWNED_PATHS):
        return "owned"
    if ADMIN_WRITES.search(path) or SESSION_ONLY.match(path):
        return "session"
    return None


def _member_role(project_id: str, user_id: str) -> str | None:
    with db() as con:
        found = con.execute("SELECT role FROM project_members WHERE project_id=? AND user_id=?", (project_id, user_id)).fetchone()
    return found[0] if found else None


def project_role(project_id: str | None, user: dict | None = None) -> str | None:
    """'admin', 'owner', the member's role, or None when the project is not theirs to see."""
    user = user or current_user.get()
    if not user:
        return None
    if user["role"] == "admin":
        return "admin"
    if not project_id or project_id == EVAL_PROJECT:
        return None
    with db() as con:
        found = con.execute("SELECT owner_id FROM projects WHERE id=?", (project_id,)).fetchone()
    if not found:
        return None
    return "owner" if found[0] == user["id"] else _member_role(project_id, user["id"])


def can_see_project(project_id: str | None, user: dict | None = None) -> bool:
    return project_role(project_id, user) is not None


def can_write(project_id: str | None, user: dict | None = None) -> bool:
    """The lesser of the account role and the member role: a viewer on either side cannot write."""
    user = user or current_user.get()
    role = project_role(project_id, user)
    return bool(role) and user["account_role"] != "viewer" and role != "viewer"


def gate_roles() -> dict[int, list[str]]:
    """Gate number to the roles that may sign it. A gate with no entry may be signed by any role that can write."""
    with db() as con:
        found = con.execute("SELECT value FROM settings WHERE key='gate_roles'").fetchone()
    stored = json.loads(found[0]) if found and found[0] else {}
    return {int(g): list(r) for g, r in stored.items() if r}


def set_gate_roles(mapping: dict) -> dict[int, list[str]]:
    clean = {}
    for gate, names in mapping.items():
        if str(gate) not in {str(n) for n in range(6)}:
            raise AuthError(f"Unknown gate {gate}. Gates are 0 to 5")
        if bad := [n for n in names if n not in ROLES or n == "viewer"]:
            raise AuthError(f"{', '.join(bad)} cannot sign a gate. Use: {', '.join(r for r in ROLES if r != 'viewer')}")
        if names:
            clean[str(int(gate))] = list(dict.fromkeys(names))
    with db() as con:
        con.execute("INSERT OR REPLACE INTO settings VALUES ('gate_roles', ?)", (json.dumps(clean),))
    _event(signer(), "gate_roles.changed")
    return gate_roles()


def gate_signing_problem(project_id: str, gate: int, user: dict | None = None) -> str:
    """Empty when the signed-in account may sign this gate; otherwise the refusal, naming the roles needed. The admin may always sign."""
    user = user or current_user.get()
    role = project_role(project_id, user)
    if role == "admin":
        return ""
    if not can_write(project_id, user):
        return "Your role cannot approve here. A viewer can read but never sign"
    needed = gate_roles().get(gate)
    if not needed:
        return ""
    held = [user["account_role"]] + ([_member_role(project_id, user["id"])] if role not in {"owner", "admin"} else [])
    if all(r in needed for r in held):
        return ""
    return f"Gate G{gate} can be signed only by: {', '.join(ROLE_NAMES[r] for r in needed)}. You hold: {', '.join(ROLE_NAMES[r] for r in dict.fromkeys(held))}"


def require_gate_signer(project_id: str, gate: int) -> None:
    if problem := gate_signing_problem(project_id, gate):
        raise Forbidden(problem)


def access_problem(method: str, path: str, user: dict) -> tuple[int, str] | None:
    """Returns the status and message to refuse with. Someone else's item answers 404, so its existence is not revealed."""
    if user["role"] == "admin":
        return None
    write = method in WRITES
    if ADMIN_ONLY.search(path) or (write and ADMIN_WRITES.search(path)):
        return 403, "Only an administrator can do this"
    if write and user["account_role"] == "viewer" and not VIEWER_MAY_WRITE.match(path):
        return 403, "Your role is viewer. A viewer can read but not start, change, or approve anything"
    for pattern, query in OWNED_PATHS:
        if match := pattern.match(path):
            with db() as con:
                found = con.execute(query, (match.group(1),)).fetchone()
            role = project_role(found[0], user) if found else None
            if not role:
                return 404, "Not found"
            if (OWNER_ONLY.match(path) or (method == "DELETE" and OWNER_DELETE.match(path))) and role != "owner":
                return 403, "Only the project owner or an administrator can do this"
            if write and role == "viewer":
                return 403, "Your role in this project is viewer. A viewer can read but not start, change, or approve anything"
            return None
    return None if rule_of(path) else (403, "This path has no access rule")


# ---- members, ownership, and the account's own password ---------------------------

def _id_for(username: str) -> str | None:
    with db() as con:
        found = con.execute("SELECT id FROM users WHERE username_lookup=?", (_lookup(username),)).fetchone()
    return found[0] if found else None


def members(project_id: str) -> list[dict]:
    with db() as con:
        found = rows(con.execute("SELECT user_id, role, created_at FROM project_members WHERE project_id=? ORDER BY created_at", (project_id,)))
    return [{**m, "username": decrypt(_account(m["user_id"])["username_enc"].encode())} for m in found]


def add_member(project_id: str, username: str, role: str) -> dict:
    """The owner types the exact username. The only answers are added, or no such account."""
    check_role(role)
    user_id = _id_for(username)
    with db() as con:
        owner = con.execute("SELECT owner_id FROM projects WHERE id=?", (project_id,)).fetchone()
        if not user_id or (owner and owner[0] == user_id):
            raise KeyError("No account has that username")  # the owner themself gets the same answer, so there is one message
        con.execute("INSERT OR REPLACE INTO project_members VALUES (?,?,?,?,?)", (project_id, user_id, role, signer(), now()))
    ledger.append(project_id, signer(), "member.added", user_id, {"role": role})
    return {"user_id": user_id, "role": role}


def remove_member(project_id: str, user_id: str) -> None:
    with db() as con:
        gone = con.execute("DELETE FROM project_members WHERE project_id=? AND user_id=?", (project_id, user_id)).rowcount
    if not gone:
        raise KeyError(user_id)
    ledger.append(project_id, signer(), "member.removed", user_id)


def transfer_project(project_id: str, username: str) -> dict:
    user_id = _id_for(username)
    if not user_id:
        raise KeyError("No account has that username")
    with db() as con:
        old = con.execute("SELECT owner_id FROM projects WHERE id=?", (project_id,)).fetchone()[0]
        con.execute("UPDATE projects SET owner_id=?, updated_at=? WHERE id=?", (user_id, now(), project_id))
        con.execute("DELETE FROM project_members WHERE project_id=? AND user_id=?", (project_id, user_id))
    ledger.append(project_id, signer(), "project.transferred", user_id, {"from": old, "to": user_id})
    return {"owner_id": user_id}


def change_password(user_id: str, current: str, new: str, keep_token: str | None) -> None:
    """The environment admin's password lives in the environment. Other sessions of this account end; the current one stays."""
    if user_id == ADMIN_ID:
        raise Forbidden("The administrator's password is set in the environment (ATLAS_ADMIN_PASSWORD). Change it there and restart")
    account = _account(user_id)
    with _failures_lock:  # the same lockout as sign-in, so this form cannot be used to guess the password
        count, until = _failures.get(user_id, (0, 0.0))
        if count >= MAX_FAILURES and time.time() < until:
            raise AuthError("Too many attempts. Try again in a few minutes")
    if not _verify_password(current, account["password_hash"]):
        with _failures_lock:
            _failures[user_id] = (count + 1, time.time() + LOCK_SECONDS)
        _event(user_id, "password.change_failed")
        raise AuthError("The current password is not correct")
    check_password_rules(new)
    keep = hashlib.sha256(keep_token.encode()).hexdigest() if keep_token else ""
    with db() as con:
        con.execute("UPDATE users SET password_hash=?, updated_at=? WHERE id=?", (hash_password(new), now(), user_id))
        con.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user_id, keep))
    with _failures_lock:
        _failures.pop(user_id, None)
    _event(user_id, "password.changed")


# ponytail: SQL for "projects this account can see", used where the log is filtered in the database. :owner is the account id.
VISIBLE_PROJECTS = "(owner_id=:owner OR id IN (SELECT project_id FROM project_members WHERE user_id=:owner))"
