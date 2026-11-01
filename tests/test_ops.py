"""Phase 2, second half: observability paging, one active run, daily JSON logs, run file removal."""
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from fastapi.testclient import TestClient

from backend import config
from backend.app import app
from backend.core import logs
from backend.db import db, new_id, now
from backend.maf import llm
from tests.scripted_client import ScriptedClient
from tests.test_api_workflows import client, make_user, project, sign_in, unique  # noqa: F401 - fixtures


def seed_log(project_id, run_id, n):
    """n records in four sources, all in the same few seconds so the ordering has many ties."""
    with db() as con:
        con.execute("INSERT OR IGNORE INTO runs (id, project_id, workflow, status, input, state, started_at) VALUES (?,?,'qe','completed','{}','{}',?)", (run_id, project_id, "2030-01-01T00:00:00+00:00"))
        for i in range(n):
            ts = f"2030-01-01T00:00:{i % 7:02d}+00:00"
            con.execute("INSERT INTO agent_calls (agent, project_id, run_id, source, prompt_ref, tokens_in, tokens_out, latency_ms, status, error, created_at) VALUES ('qa',?,?,'run','p@1',1,2,3,?,?,?)",
                        (project_id, run_id, "ok" if i % 5 else "error", "" if i % 5 else "boom", ts))
            con.execute("INSERT INTO tool_calls (agent, project_id, run_id, source, tool, kind, arguments, latency_ms, status, created_at) VALUES ('qa',?,?,'run','grep',?,'{}',1,'ok',?)", (project_id, run_id, "mcp" if i % 4 == 0 else "function", ts))
            con.execute("INSERT INTO guardrail_events (agent, project_id, run_id, kind, action, detail, created_at) VALUES ('qa',?,?,'injection','blocked','x',?)", (project_id, run_id, ts))
            con.execute("INSERT INTO run_events (run_id, seq, type, stage, message, ts) VALUES (?,?,?,?,?,?)", (run_id, 1000 + i, "approved" if i % 3 == 0 else "log", "plan", f"step {i}", ts))


def pages(http, query, limit):
    got, before = [], ""
    while True:
        page = http.get(f"/api/observability?{query}&limit={limit}" + (f"&before={before}" if before else "")).json()
        got.append(page)
        if not page["next"]:
            return got
        before = page["next"]


def test_observability_pages_have_no_duplicates_or_gaps_and_filters_hold_across_pages(client, project):
    mine = f"run_{unique()}"
    seed_log(project["id"], mine, 40)
    everything = client.get(f"/api/observability?project_id={project['id']}&limit=2000").json()
    keys = lambda got: [i["key"] for p in got for i in p["items"]]
    paged = pages(client, f"project_id={project['id']}", 25)
    assert len(paged) > 5 and all(len(p["items"]) == 25 for p in paged[:-1])
    assert len(keys(paged)) == len(set(keys(paged))) == everything["total"] == len(everything["items"]), "no duplicates and no gaps"
    assert keys(paged) == keys([everything]), "pages join up into the same order as one big read"
    assert all(p["total"] == everything["total"] and p["counts"] == everything["counts"] for p in paged), "totals do not change as pages load"
    stamps = [i["ts"] for p in paged for i in p["items"]]
    assert stamps == sorted(stamps, reverse=True)
    for kind in ("agent", "tool", "mcp", "approval", "workflow", "guardrail", "audit"):
        want = [i["key"] for i in everything["items"] if i["kind"] == kind]
        got = pages(client, f"project_id={project['id']}&kind={kind}", 7)
        assert want and keys(got) == want and all(i["kind"] == kind for p in got for i in p["items"]), kind
    got = pages(client, f"project_id={project['id']}&run_id={mine}&q=step", 9)
    assert len(got) > 1 and all("step" in i["message"] and i["run_id"] == mine for p in got for i in p["items"]) and len(set(keys(got))) == len(keys(got)) == 40
    assert client.get(f"/api/observability?project_id={project['id']}&before=not-a-key").status_code == 422


def test_another_users_rows_never_appear_on_any_page(client, project):
    name = unique()
    make_user(client, name)
    other, _ = sign_in(name)
    theirs = other.post("/api/projects", json={"name": "Theirs", "description": ""}).json()
    seed_log(project["id"], f"run_{unique()}", 30)
    seed_log(theirs["id"], f"run_{unique()}", 30)
    for query in ("", f"project_id={project['id']}", f"project_id={theirs['id']}", "kind=agent", "q=boom", "kind=audit"):
        got = pages(other, query, 11)
        items = [i for p in got for i in p["items"]]
        assert all(i["project_id"] == theirs["id"] for i in items), query
        assert all(r["project_id"] == theirs["id"] for p in got for r in p["runs"]) and all(i["project_id"] == theirs["id"] for p in got for i in p["integrity"])
        assert len({i["key"] for i in items}) == len(items)
    seen = pages(other, "", 500)[0]
    assert seen["total"] == client.get(f"/api/observability?project_id={theirs['id']}&limit=1").json()["total"] and seen["counts"]["agent"] == 30
    assert pages(other, f"project_id={project['id']}", 500)[0]["total"] == 0


# ---- one active run -----------------------------------------------------------

def insert_run(project_id, workflow, status):
    run_id = new_id("run")
    with db() as con:
        con.execute("INSERT INTO runs (id, project_id, workflow, status, input, state, started_at) VALUES (?,?,?,?,'{}','{}',?)", (run_id, project_id, workflow, status, now()))
    return run_id


def test_a_second_run_of_the_same_kind_answers_409_naming_the_active_run(client, project):
    llm.set_client_override(ScriptedClient([("x", "ok")]))
    other_project = client.post("/api/projects", json={"name": "Other", "description": ""}).json()
    for state in ("running", "waiting_approval"):
        active = insert_run(project["id"], "bug_scan", state)
        refused = client.post(f"/api/projects/{project['id']}/runs", json={"workflow": "bug_scan"})
        body = refused.json()
        assert refused.status_code == 409 and active in body["message"] and f"/projects/{project['id']}/runs/{active}" in body["message"] and body["code"] is None
        with db() as con:
            con.execute("UPDATE runs SET status='completed' WHERE id=?", (active,))
    insert_run(project["id"], "qe", "running")  # another kind, and another project, are not blocked
    assert client.post(f"/api/projects/{other_project['id']}/runs", json={"workflow": "bug_scan"}).status_code != 409
    assert client.post(f"/api/projects/{project['id']}/runs", json={"workflow": "bug_scan"}).status_code != 409, "a finished run frees the slot"


def test_concurrent_starts_cannot_both_win(client, project):
    llm.set_client_override(ScriptedClient([("x", "ok")]))
    gate = threading.Barrier(8)

    def go(_):
        gate.wait()
        return client.post(f"/api/projects/{project['id']}/runs", json={"workflow": "bug_scan"}).status_code

    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(go, range(8)))
    assert codes.count(201) == 1 and codes.count(409) == 7, codes
    with db() as con:
        assert con.execute("SELECT COUNT(*) FROM runs WHERE project_id=? AND workflow='bug_scan'", (project["id"],)).fetchone()[0] == 1


def test_retry_cannot_take_the_slot_of_a_newer_run(client, project):
    llm.set_client_override(ScriptedClient([("x", "ok")]))
    failed = insert_run(project["id"], "bug_scan", "failed")
    newer = insert_run(project["id"], "bug_scan", "waiting_approval")
    refused = client.post(f"/api/runs/{failed}/retry")
    assert refused.status_code == 409 and newer in refused.json()["message"]
    assert client.get(f"/api/runs/{failed}").json()["status"] == "failed"


# ---- structured log files ------------------------------------------------------

def read_lines():
    path = logs.file_for(logs.today())
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def test_requests_and_errors_are_logged_without_secrets_bodies_queries_or_usernames(client, project):
    secret = "sk-" + "Qx7" * 12
    password = "Pw-" + unique("p")
    name = unique("someone")
    client.post("/api/auth/login", json={"username": name, "password": password})  # a failed sign-in with a body
    client.get(f"/api/projects/{project['id']}?token={secret}&password={password}")
    client.post(f"/api/projects/{project['id']}/documents", json={"kind": "brd", "title": f"password={password} key {secret}", "content": "# T\n"})
    logging.getLogger("aqe.engine").error("run failed with api_key=%s and password=%s", secret, password, extra={"fields": {"run_id": "run_1", "stage": "design", "agent": "qa", "error_id": "err_1"}})
    text = logs.file_for(logs.today()).read_text(encoding="utf-8")
    assert secret not in text and password not in text and name not in text
    lines = read_lines()
    request = next(line for line in lines if line.get("path") == f"/api/projects/{project['id']}")
    assert request["method"] == "GET" and request["status"] == 200 and request["user_id"] == "admin" and request["request_id"].startswith("req_") and request["duration_ms"] >= 0
    assert "token" not in json.dumps(request) and "query" not in request
    failure = next(line for line in lines if line["level"] == "ERROR" and line.get("run_id") == "run_1")
    assert failure["stage"] == "design" and failure["agent"] == "qa" and failure["error_id"] == "err_1"
    assert all(line["logger"] == "aqe.request" or line["level"] in {"WARNING", "ERROR", "CRITICAL"} for line in lines), "other loggers write only warnings and errors"


def test_retention_removes_only_old_log_files_by_the_date_in_their_name():
    config.LOGS.mkdir(parents=True, exist_ok=True)
    today = logs.today()
    old, edge, fresh = (config.LOGS / f"app-{(today - timedelta(days=d)).isoformat()}.jsonl" for d in (31, 30, 1))
    other = [config.LOGS / "notes.txt", config.LOGS / "app-2020-01-01.jsonl.bak", config.LOGS / "keep-2020-01-01.jsonl"]
    for path in (old, edge, fresh, *other):
        path.write_text("x")
    os.utime(fresh, (0, 0))  # modification time is ignored: only the name counts
    assert logs.prune(30, today) == [old.name]
    assert not old.exists() and edge.exists() and fresh.exists() and all(p.exists() for p in other)


def test_only_an_admin_downloads_logs_and_only_for_a_real_date(client):
    client.get("/api/projects")
    name = unique()
    make_user(client, name)
    other, _ = sign_in(name)
    day = logs.today().isoformat()
    assert other.get("/api/logs").status_code == 403 and other.get(f"/api/logs?date={day}").status_code == 403
    assert TestClient(app).get(f"/api/logs?date={day}").status_code == 401
    got = client.get(f"/api/logs?date={day}")
    assert got.status_code == 200 and "attachment" in got.headers["content-disposition"] and json.loads(got.text.splitlines()[0])["level"]
    for bad in ("../../etc/passwd", "2026-13-01", "2026-02-30", "20261101", "yesterday", "2026-1-1"):
        assert client.get("/api/logs", params={"date": bad}).status_code == 422, bad
    assert client.get("/api/logs?date=1999-01-01").status_code == 404


# ---- run files go with the project ---------------------------------------------

def test_deleting_a_project_removes_its_run_folders_and_nothing_else(client, project):
    keep = client.post("/api/projects", json={"name": "Keep", "description": ""}).json()
    gone, kept = insert_run(project["id"], "qe", "failed"), insert_run(keep["id"], "qe", "failed")
    for run_id in (gone, kept):
        folder = config.RUNS / run_id / "failures"
        folder.mkdir(parents=True)
        (folder / "err-reply.txt").write_text("reply")
    stranger = config.RUNS / "run_not_in_any_project"
    stranger.mkdir()
    assert client.delete(f"/api/projects/{project['id']}").status_code == 204
    assert not (config.RUNS / gone).exists()
    assert (config.RUNS / kept / "failures" / "err-reply.txt").exists() and stranger.exists()


# ---- error groups on the Observability Errors tab ------------------------------

def insert_failure(run_id, code, agent, message, created_at, stack=""):
    with db() as con:
        con.execute("INSERT INTO run_failures (id, run_id, code, message, action, retryable, agent, stack, created_at) VALUES (?,?,?,?,'Retry the stage.',0,?,?,?)",
                    (new_id("fail"), run_id, code, message, agent, stack, created_at))


def test_error_groups_count_by_code_and_agent_show_latest_message_and_never_the_stack(client, project):
    run = insert_run(project["id"], "qe", "failed")
    insert_failure(run, "AQE-MODEL-001", "qa", "first", "2030-01-01T00:00:01+00:00", stack="SECRET-STACK-TRACE")
    insert_failure(run, "AQE-MODEL-001", "qa", "second", "2030-01-01T00:00:02+00:00", stack="SECRET-STACK-TRACE")
    insert_failure(run, "AQE-MODEL-001", "designer", "other agent", "2030-01-01T00:00:03+00:00")
    insert_failure(run, "AQE-REPO-001", "", "clone failed", "2030-01-01T00:00:00+00:00")
    got = client.get(f"/api/observability/errors?project_id={project['id']}")
    assert got.status_code == 200 and "SECRET-STACK-TRACE" not in got.text
    body = got.json()
    assert body["total"] == 4 and all("stack" not in g for g in body["groups"])
    assert [(g["code"], g["agent"], g["count"], g["latest_message"]) for g in body["groups"]] == [
        ("AQE-MODEL-001", "designer", 1, "other agent"),
        ("AQE-MODEL-001", "qa", 2, "second"),
        ("AQE-REPO-001", "", 1, "clone failed"),
    ]
    assert client.get(f"/api/observability/errors?project_id={project['id']}&q=x").status_code == 200


def test_error_groups_are_empty_for_a_project_with_no_failures_and_for_other_users(client, project):
    name = unique()
    make_user(client, name)
    other, _ = sign_in(name)
    theirs = other.post("/api/projects", json={"name": "Theirs", "description": ""}).json()
    assert other.get(f"/api/observability/errors?project_id={project['id']}").json() == {"total": 0, "groups": []}
    insert_failure(insert_run(project["id"], "qe", "failed"), "AQE-TEST-001", "", "mine", "2030-01-02T00:00:00+00:00")
    assert other.get("/api/observability/errors").json() == {"total": 0, "groups": []}, "another user's failure is not shown"
    insert_failure(insert_run(theirs["id"], "qe", "failed"), "AQE-TEST-001", "", "theirs", "2030-01-02T00:00:00+00:00")
    seen = other.get("/api/observability/errors").json()
    assert seen["total"] == 1 and seen["groups"][0]["latest_message"] == "theirs"
    assert other.get(f"/api/observability/errors?project_id={project['id']}").json()["total"] == 0
    assert client.get(f"/api/observability/errors?project_id={project['id']}").json()["total"] >= 1
