"""Roles, gate signing, project members, the account page, and the idle timeout. Only the model is ever scripted; none of this needs it."""
import json
import logging
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from backend import db as database
from backend.app import PUBLIC_PATHS, app
from backend.config import DB_PATH
from backend.core import auth
from backend.db import db, new_id, now
from tests.test_api_workflows import USER_PASSWORD, client, make_user, sign_in, unique  # noqa: F401 - fixtures

IDS = ("project_id", "doc_id", "run_id", "finding_id", "approval_id", "thread_id", "memory_id")


def account(admin, role="developer"):
    """A new signed-in account with the role: (client, user record)."""
    name = unique("acct")
    made = make_user(admin, name, role=role)
    other, response = sign_in(name)
    assert response.status_code == 200, response.text
    return other, made


class World:
    """One project owned by `owner`, one item of every kind in it, and an account of each kind around it."""

    def __init__(self, admin):
        self.admin = admin
        self.owner, self.owner_user = account(admin)
        self.project = self.owner.post("/api/projects", json={"name": "Shared"}).json()
        pid = self.project["id"]
        stamp = now()
        self.ids = {"project_id": pid,
                    "doc_id": self.owner.post(f"/api/projects/{pid}/documents", json={"kind": "brd", "title": "D", "content": "# T\n"}).json()["id"],
                    "thread_id": self.owner.post(f"/api/projects/{pid}/chats", json={}).json()["id"],
                    "memory_id": self.owner.post(f"/api/projects/{pid}/memories", json={"content": "note"}).json()["id"],
                    "run_id": new_id("run"), "finding_id": new_id("fnd"), "approval_id": new_id("apr")}
        with db() as con:
            con.execute("INSERT INTO runs (id, project_id, workflow, status, input, started_at) VALUES (?,?,?,?,?,?)", (self.ids["run_id"], pid, "ba", "waiting_approval", "{}", stamp))
            con.execute("INSERT INTO findings (id, project_id, source, rule, severity, title, file, line, evidence, fingerprint, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (self.ids["finding_id"], pid, "scan", "r", "low", "t", "f.py", 1, "e", new_id("fp"), stamp))
            con.execute("INSERT INTO approvals (id, run_id, project_id, gate, title, summary, created_at) VALUES (?,?,?,?,?,?,?)", (self.ids["approval_id"], self.ids["run_id"], pid, None, "T", "S", stamp))
        self.viewer, self.viewer_user = account(admin, "viewer")
        self.dev, self.dev_user = account(admin, "developer")
        self.demoted, self.demoted_user = account(admin, "developer")  # a developer account that is only a viewer in this project
        self.stranger, self.stranger_user = account(admin, "developer")
        self.lead, self.lead_user = account(admin, "qe_lead")
        for who, role in ((self.viewer_user, "developer"), (self.dev_user, "developer"), (self.demoted_user, "viewer"), (self.lead_user, "developer")):
            self.add(who, role)

    def add(self, user, role):
        response = self.owner.post(f"/api/projects/{self.project['id']}/members", json={"username": user["username"], "role": role})
        assert response.status_code == 201, response.text

    def persona(self, name):
        users = {"viewer": self.viewer_user, "developer": self.dev_user, "viewer-member": self.demoted_user, "stranger": self.stranger_user, "owner": self.owner_user}
        if name == "admin":
            return {"id": auth.ADMIN_ID, "role": "admin", "account_role": "admin"}
        return {"id": users[name]["id"], "role": "user", "account_role": users[name]["account_role"]}


@pytest.fixture
def world(client):
    return World(client)


# ---- every route has a rule, and the rule gives the right answer to each kind of person ----

def routes():
    return [(method.upper(), path) for path, methods in app.openapi()["paths"].items() if path.startswith(("/api/", "/agui/")) and path not in PUBLIC_PATHS for method in methods]


def test_every_route_has_an_access_rule():
    missing = [f"{m} {p}" for m, p in routes() if not auth.rule_of(p)]
    assert not missing, f"No access rule for {missing}. Add the path to ADMIN_ONLY, ADMIN_WRITES, OWNED_PATHS, or SESSION_ONLY in core/auth.py"
    assert len(routes()) > 70


def test_a_path_with_no_rule_is_refused_for_everyone_but_the_admin():
    user = {"id": "usr_x", "role": "user", "account_role": "developer"}
    assert auth.access_problem("GET", "/api/brand-new-thing", user)[0] == 403
    assert auth.access_problem("GET", "/api/brand-new-thing", {"id": "admin", "role": "admin", "account_role": "admin"}) is None


ADMIN_ONLY = ("/api/users", "/api/connections", "/api/logs", "/api/auth/events", "/api/models", "/api/usage", "/api/agents/guardrail-events")
ADMIN_WRITE = ("/api/settings", "/api/prompts", "/api/agents", "/api/evals")
VIEWER_MAY_WRITE = ("/api/auth/logout", "/api/account/password")


def expected(persona, method, template):
    """Written out on its own, not read from core/auth.py."""
    write = method != "GET"
    scoped = any("{" + i + "}" in template for i in IDS)
    if persona == "admin":
        return None
    if template.startswith(ADMIN_ONLY) or template.endswith(("/repo/local", "/transfer")):
        return 403
    if write and template.startswith(ADMIN_WRITE):
        return 403
    if write and persona == "viewer" and template not in VIEWER_MAY_WRITE:
        return 403
    if scoped:
        if persona == "stranger":
            return 404
        if persona != "owner" and ("/members" in template or (method == "DELETE" and template == "/api/projects/{project_id}")):
            return 403
        if write and persona == "viewer-member":
            return 403
    return None


@pytest.mark.parametrize("persona", ["viewer", "developer", "viewer-member", "stranger", "owner", "admin"])
def test_access_matrix_over_every_route(world, persona):
    user, wrong = world.persona(persona), []
    for method, template in routes():
        path = re.sub(r"\{(\w+)\}", lambda m: world.ids.get(m.group(1), "1" if m.group(1) in {"gate", "version"} else "x"), template)
        found = auth.access_problem(method, path, user)
        want = expected(persona, method, template)
        if (found[0] if found else None) != want:
            wrong.append((persona, method, template, found, want))
    assert not wrong, wrong


def test_anonymous_gets_401_on_the_new_routes(world):
    from fastapi.testclient import TestClient

    anonymous = TestClient(app)
    pid = world.project["id"]
    for method, url in (("GET", f"/api/projects/{pid}/members"), ("POST", f"/api/projects/{pid}/transfer"), ("POST", "/api/account/password"), ("PUT", "/api/settings/gate-roles")):
        assert anonymous.request(method, url).status_code == 401


def test_viewer_reads_but_cannot_write_and_the_message_names_the_role(world):
    pid = world.project["id"]
    assert world.viewer.get(f"/api/projects/{pid}/overview").status_code == 200
    refused = world.viewer.post(f"/api/projects/{pid}/runs", json={"workflow": "ba", "input": {}})
    assert refused.status_code == 403 and "viewer" in refused.json()["message"]
    assert world.viewer.post("/api/projects", json={"name": "Mine"}).status_code == 403
    assert world.viewer.post(f"/api/approvals/{world.ids['approval_id']}/decide", json={"approved": True}).status_code == 403
    assert world.viewer.post(f"/api/projects/{pid}/gates/0/decision", json={"approved": True}).status_code == 403
    assert world.viewer.post("/api/auth/logout").status_code == 204
    demoted = world.demoted.patch(f"/api/projects/{pid}", json={"description": "x"})
    assert demoted.status_code == 403 and "project is viewer" in demoted.json()["message"].replace("in this ", "")
    assert world.dev.patch(f"/api/projects/{pid}", json={"description": "by a member"}).status_code == 200


# ---- gate roles ----

def test_gate_role_map_allows_and_refuses_by_role(world):
    pid = world.project["id"]
    sign = lambda who, gate: who.post(f"/api/projects/{pid}/gates/{gate}/decision", json={"approved": True})
    assert sign(world.dev, 0).status_code == 200, "with no map, any member who can write may sign"
    assert world.stranger.put("/api/settings/gate-roles", json={"roles": {"5": ["qe_lead"]}}).status_code == 403
    assert world.admin.put("/api/settings/gate-roles", json={"roles": {"9": ["qe_lead"]}}).status_code == 400
    assert world.admin.put("/api/settings/gate-roles", json={"roles": {"5": ["viewer"]}}).status_code == 400
    saved = world.admin.put("/api/settings/gate-roles", json={"roles": {"5": ["qe_lead"], "1": ["ba", "qe_lead"]}})
    assert saved.status_code == 200 and saved.json()["roles"] == {"1": ["ba", "qe_lead"], "5": ["qe_lead"]}
    try:
        refused = sign(world.dev, 5)
        assert refused.status_code == 403 and "QE lead" in refused.json()["message"], refused.text and "G5" in refused.json()["message"]
        assert sign(world.dev, 1).status_code == 403 and "BA" in sign(world.dev, 1).json()["message"]
        assert sign(world.lead, 5).status_code == 403, "a qe_lead account that is only a developer in this project holds the lesser role"
    finally:
        world.admin.put("/api/settings/gate-roles", json={"roles": {}})
    assert world.admin.get("/api/settings/gate-roles").json()["roles"] == {}


def test_a_qe_lead_who_holds_the_role_in_both_places_passes_the_role_check(world):
    pid = world.project["id"]
    world.add(world.lead_user, "qe_lead")  # now qe_lead on the account and in the project
    world.admin.put("/api/settings/gate-roles", json={"roles": {"5": ["qe_lead"]}})
    try:
        passed = world.lead.post(f"/api/projects/{pid}/gates/5/decision", json={"approved": True})
        assert passed.status_code == 400 and "Gate 4 must be approved" in passed.json()["message"]  # past the role check, stopped by order
        assert world.owner.post(f"/api/projects/{pid}/gates/5/decision", json={"approved": True}).status_code == 403  # a developer account owner
        assert world.admin.post(f"/api/projects/{pid}/gates/5/decision", json={"approved": True}).status_code == 400  # the admin is never role-blocked
    finally:
        world.admin.put("/api/settings/gate-roles", json={"roles": {}})


def test_gate_approval_from_a_run_is_checked_by_role_in_the_engine(world):
    pid = world.project["id"]
    with db() as con:
        con.execute("UPDATE approvals SET gate=5 WHERE id=?", (world.ids["approval_id"],))
    world.admin.put("/api/settings/gate-roles", json={"roles": {"5": ["qe_lead"]}})
    try:
        refused = world.dev.post(f"/api/approvals/{world.ids['approval_id']}/decide", json={"approved": True})
        assert refused.status_code == 403 and "QE lead" in refused.json()["message"], refused.text
        assert world.viewer.post(f"/api/approvals/{world.ids['approval_id']}/decide", json={"approved": True}).status_code == 403
    finally:
        world.admin.put("/api/settings/gate-roles", json={"roles": {}})
    with db() as con:
        assert con.execute("SELECT status FROM approvals WHERE id=?", (world.ids["approval_id"],)).fetchone()[0] == "pending"
        assert con.execute("SELECT COUNT(*) FROM gates WHERE project_id=? AND gate=5", (pid,)).fetchone()[0] == 0


# ---- members ----

def test_removed_member_is_refused_at_once_and_members_see_what_they_should(world):
    pid, member = world.project["id"], world.dev
    assert member.get(f"/api/projects/{pid}").json()["my_role"] == "developer"
    assert pid in [p["id"] for p in member.get("/api/projects").json()]
    assert world.ids["finding_id"] in [f["id"] for f in member.get("/api/findings").json()]
    assert world.ids["approval_id"] in [a["id"] for a in member.get("/api/approvals").json()]
    assert world.ids["doc_id"] in [d["id"] for d in member.get("/api/documents").json()]
    assert world.ids["run_id"] in json.dumps(member.get(f"/api/projects/{pid}/runs").json())
    from backend.maf import observability

    assert world.ids["run_id"] in json.dumps(observability.query(None, None, "", "", 300, "", world.dev_user["id"]), default=str)
    assert member.get("/api/observability/errors").status_code == 200
    assert member.get(f"/api/projects/{pid}/members").status_code == 403, "a member does not see the other members' usernames"
    assert member.post(f"/api/projects/{pid}/members", json={"username": world.stranger_user["username"], "role": "developer"}).status_code == 403
    assert world.owner.get(f"/api/projects/{pid}/members").status_code == 200

    assert world.owner.delete(f"/api/projects/{pid}/members/{world.dev_user['id']}").status_code == 204
    for url in (f"/api/projects/{pid}", f"/api/runs/{world.ids['run_id']}", f"/api/documents/{world.ids['doc_id']}", f"/api/chats/{world.ids['thread_id']}", f"/api/projects/{pid}/overview"):
        assert member.get(url).status_code == 404, url
    assert pid not in [p["id"] for p in member.get("/api/projects").json()]
    assert world.ids["finding_id"] not in [f["id"] for f in member.get("/api/findings").json()]
    assert world.ids["approval_id"] not in [a["id"] for a in member.get("/api/approvals").json()]
    assert world.ids["run_id"] not in json.dumps(observability.query(None, None, "", "", 300, "", world.dev_user["id"]), default=str)
    assert member.post(f"/agui/project-copilot", json={"threadId": world.ids["thread_id"], "messages": []}).status_code == 404


def test_adding_members_answers_only_added_or_not_found(world):
    pid = world.project["id"]
    path = f"/api/projects/{pid}/members"
    missing = world.owner.post(path, json={"username": "nobody.at.all", "role": "developer"})
    own = world.owner.post(path, json={"username": world.owner_user["username"], "role": "developer"})
    admin_name = world.owner.post(path, json={"username": "qa-admin", "role": "developer"})
    assert missing.status_code == own.status_code == admin_name.status_code == 404
    assert missing.json()["message"] == own.json()["message"] == admin_name.json()["message"]
    assert world.owner.post(path, json={"username": world.stranger_user["username"], "role": "owner"}).status_code == 400
    listed = world.owner.get(path).json()
    assert {m["username"] for m in listed} >= {world.dev_user["username"]} and not {world.stranger_user["username"]} & {m["username"] for m in listed}
    assert world.stranger.get("/api/users").status_code == 403, "no list of users for non-admins"
    assert world.owner.delete(f"{path}/{world.stranger_user['id']}").status_code == 404


def test_a_viewer_account_cannot_write_even_as_an_owner_or_developer_member(world):
    pid = world.project["id"]
    assert world.viewer.get(f"/api/projects/{pid}/chats").status_code == 200
    assert world.viewer.post(f"/api/projects/{pid}/chats", json={}).status_code == 403
    assert world.viewer.post(f"/agui/project-copilot", json={"threadId": world.ids["thread_id"], "messages": []}).status_code == 403


def test_transfer_is_admin_only_and_written_to_a_valid_ledger(world):
    pid = world.project["id"]
    assert world.owner.post(f"/api/projects/{pid}/transfer", json={"username": world.dev_user["username"]}).status_code == 403
    assert world.admin.post(f"/api/projects/{pid}/transfer", json={"username": "nobody.at.all"}).status_code == 404
    moved = world.admin.post(f"/api/projects/{pid}/transfer", json={"username": world.dev_user["username"]})
    assert moved.status_code == 200 and moved.json()["owner_id"] == world.dev_user["id"]
    assert world.owner.get(f"/api/projects/{pid}").status_code == 404, "the old owner loses it"
    assert world.dev.get(f"/api/projects/{pid}").json()["my_role"] == "owner"
    with db() as con:
        assert con.execute("SELECT COUNT(*) FROM project_members WHERE project_id=? AND user_id=?", (pid, world.dev_user["id"])).fetchone()[0] == 0
    ledger = world.admin.get(f"/api/projects/{pid}/ledger").json()
    entry = next(e for e in ledger["entries"] if e["action"] == "project.transferred")
    assert entry["actor"] == auth.ADMIN_ID and entry["target"] == world.dev_user["id"] and ledger["verification"]["valid"]


# ---- account page ----

def test_password_change_works_ends_other_sessions_and_leaves_no_trace(world, caplog):
    name, fresh = unique("changer"), secrets.token_hex(8) + "Zz9!"
    made = make_user(world.admin, name)
    first, _ = sign_in(name)
    second, _ = sign_in(name)
    bad = first.post("/api/account/password", json={"current_password": "wrong-password-1", "new_password": fresh})
    assert bad.status_code == 400 and "current password" in bad.json()["message"]
    assert first.post("/api/account/password", json={"current_password": USER_PASSWORD, "new_password": "short"}).status_code == 400
    with caplog.at_level(logging.DEBUG):
        assert first.post("/api/account/password", json={"current_password": USER_PASSWORD, "new_password": fresh}).status_code == 204
    assert first.get("/api/auth/me").status_code == 200, "the session that changed it stays"
    assert second.get("/api/auth/me").status_code == 401, "other sessions end"
    assert sign_in(name, USER_PASSWORD)[1].status_code == 401
    assert sign_in(name, fresh)[1].status_code == 200
    assert fresh not in caplog.text and USER_PASSWORD not in caplog.text
    with db() as con:
        dump = "\n".join(con.iterdump())
        events = [dict(r) for r in con.execute("SELECT subject, event FROM auth_events WHERE event LIKE 'password.%'")]
    assert fresh not in dump and USER_PASSWORD not in dump and name not in dump
    assert {"subject": made["id"], "event": "password.changed"} in events and {"subject": made["id"], "event": "password.change_failed"} in events


def test_the_environment_admin_cannot_change_its_password_here(world):
    refused = world.admin.post("/api/account/password", json={"current_password": "whatever-it-is", "new_password": "another-long-password"})
    assert refused.status_code == 403 and "environment" in refused.json()["message"]


def test_account_page_data_and_roles_on_the_users_api(world):
    mine = world.dev.get("/api/auth/me").json()
    assert mine["account_role"] == "developer" and "models" in mine and "limits" in mine and "usage" in mine
    changed = world.admin.patch(f"/api/users/{world.stranger_user['id']}", json={"role": "ba"})
    assert changed.status_code == 200 and changed.json()["account_role"] == "ba"
    assert world.admin.patch(f"/api/users/{world.stranger_user['id']}", json={"role": "owner"}).status_code == 400
    assert world.admin.post("/api/users", json={"username": unique("nr"), "password": USER_PASSWORD, "role": "king"}).status_code == 400


# ---- idle timeout ----

def test_session_ends_after_idle_minutes_with_an_injected_clock(world, monkeypatch):
    name = unique("idle")
    make_user(world.admin, name)
    token = auth.login(name, USER_PASSWORD)
    start = datetime.now(timezone.utc)
    at = lambda minutes, seconds=0: monkeypatch.setattr(auth, "clock", lambda: start + timedelta(minutes=minutes, seconds=seconds))
    seen = lambda: sqlite3.connect(DB_PATH).execute("SELECT last_seen FROM sessions WHERE token_hash=?", (__import__("hashlib").sha256(token.encode()).hexdigest(),)).fetchone()
    at(0, 30)
    first = seen()
    assert auth.session_user(token) and seen() == first, "a request within a minute does not write"
    at(100)
    assert auth.session_user(token) and seen() != first, "later it does"
    at(100 + auth.IDLE_MINUTES - 1)
    assert auth.session_user(token)
    at(100 + 2 * auth.IDLE_MINUTES)
    assert auth.session_user(token) is None and seen() is None, "idle too long: gone, and deleted"


# ---- upgrade from phase 2 ----

def test_migration_010_keeps_users_and_sessions_from_a_phase_2_database(tmp_path, monkeypatch):
    path = tmp_path / "phase2.sqlite3"
    monkeypatch.setattr(database, "DB_PATH", path)
    con = sqlite3.connect(path)
    for sql in sorted(database.MIGRATIONS.glob("*.sql")):
        if int(sql.name.split("_")[0]) <= 9:
            con.executescript(sql.read_text(encoding="utf-8"))
    con.execute("PRAGMA user_version=9")
    stamp, later = database.now(), (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(timespec="seconds")
    con.execute("INSERT INTO users (id, username_lookup, username_enc, password_hash, enabled, created_at, updated_at) VALUES ('usr_old','k','e','h',1,?,?)", (stamp, stamp))
    con.execute("INSERT INTO projects (id, name, created_at, updated_at, owner_id) VALUES ('p1','P',?,?,'usr_old')", (stamp, stamp))
    con.execute("INSERT INTO sessions VALUES ('tok','usr_old',?,?)", (later, stamp))
    con.commit()
    con.close()

    database.migrate()
    con = sqlite3.connect(path)
    assert con.execute("SELECT role FROM users WHERE id='usr_old'").fetchone()[0] == "developer"
    assert con.execute("SELECT COUNT(*) FROM project_members").fetchone()[0] == 0
    assert con.execute("PRAGMA user_version").fetchone()[0] == len(list(database.MIGRATIONS.glob("*.sql")))
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE users SET role='king'")
    con.close()
    old = {"id": "usr_old", "role": "user", "account_role": "developer"}
    assert auth.can_write("p1", old) and auth.project_role("p1", old) == "owner", "the old owner keeps everything"
    import hashlib

    con = sqlite3.connect(path)
    con.execute("UPDATE sessions SET token_hash=? WHERE token_hash='tok'", (hashlib.sha256(b"old-token").hexdigest(),))
    con.commit()
    con.close()
    assert auth.session_user("old-token")["account_role"] == "developer", "a session with no last_seen still works and gets one"
