"""Models per account, the order a call picks one, and daily, weekly, monthly, and per-model token limits. Only the model is scripted."""
import asyncio
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from backend import config
from backend import db as database
from backend.core import auth, models
from backend.db import db, now, rows
from backend.maf import llm
from tests.scripted_client import ScriptedClient
from tests.test_api_workflows import GOOD_REVIEW, USER_PASSWORD, client, make_user, pending, project, rules, sign_in, unique, upload_repo, wait_run  # noqa: F401 - fixtures
from tests.test_errors import IDS, Designer, qe_client  # noqa: F401

BA_BRIEF = {"brief": "Password reset link that expires in 30 minutes", "template_id": "builtin_brd", "title": "Reset BRD"}


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


def at(monkeypatch, text: str) -> None:
    monkeypatch.setattr(models, "clock", lambda: utc(text))


class As:
    """A signed-in user on the admin's test client. Background runs need that client's event loop, which a client opened without `with` closes after each request."""

    def __init__(self, admin, name):
        other, response = sign_in(name)
        assert response.status_code == 200, response.text
        self.admin, self.token = admin, other.cookies.get(auth.COOKIE)

    @contextmanager
    def _swapped(self):
        keep = self.admin.cookies.get(auth.COOKIE)
        self.admin.cookies.clear()
        self.admin.cookies.set(auth.COOKIE, self.token, domain="testserver.local", path="/")
        try:
            yield self.admin
        finally:
            self.admin.cookies.clear()
            self.admin.cookies.set(auth.COOKIE, keep, domain="testserver.local", path="/")

    def __getattr__(self, method):
        def call(*args, **kwargs):
            with self._swapped() as c:
                return getattr(c, method)(*args, **kwargs)

        return call

    @contextmanager
    def stream(self, *args, **kwargs):
        with self._swapped() as c, c.stream(*args, **kwargs) as response:
            yield response


def listed(*names):
    for name in names:
        models.add(name, enabled=True)


def account(client, models_=("m-a",), **extra):
    """A signed-in user with the given models ticked and the first as default. Returns (user record, client, project)."""
    listed(*models_)
    name = unique()
    user = make_user(client, name, models=list(models_), model=models_[0], **extra)
    other = As(client, name)
    return user, other, other.post("/api/projects", json={"name": "Mine", "description": ""}).json()


def spend(user_id, tokens, model="m-a", created_at=None, project_id=None):
    with db() as con:
        con.execute("INSERT INTO agent_calls (agent, project_id, source, prompt_ref, tokens_in, tokens_out, latency_ms, tool_calls, status, created_at, model, user_id) VALUES ('project-copilot', ?, 'chat', 'x', ?, 0, 1, 0, 'ok', ?, ?, ?)",
                    (project_id, tokens, created_at or now(), model, user_id))


def used_models(run_id):
    with db() as con:
        return {r["agent"]: r["model"] for r in rows(con.execute("SELECT DISTINCT agent, model FROM agent_calls WHERE run_id=?", (run_id,)))}


def events_of(user_id):
    with db() as con:
        return [r["event"] for r in rows(con.execute("SELECT event FROM auth_events WHERE subject=?", (user_id,)))]


def ba_through_intake(c, run_id, statuses=("waiting_approval", "completed", "failed")):
    """Intake asks for a person's approval before any agent works, so the model calls start after it."""
    run = wait_run(c, run_id)
    c.post(f"/api/approvals/{pending(run)['id']}/decide", json={"approved": True})
    return wait_run(c, run_id, statuses)


def start_ba(c, project, **extra):
    return c.post(f"/api/projects/{project['id']}/runs", json={"workflow": "ba", "input": BA_BRIEF, **extra})


# ---- the list, ticks, and refusals ------------------------------------------------------

def test_a_model_the_user_was_not_given_is_refused_by_run_chat_and_agent_and_logged_by_account_id(client):
    llm.set_client_override(ScriptedClient(rules()))
    user, mine, project = account(client, ("m-a",))
    listed("m-other")
    refused = start_ba(mine, project, model="m-other")
    assert refused.status_code == 403 and refused.json()["code"] == "AQE-ALLOW-001" and "m-other" in refused.json()["message"]
    thread = mine.post(f"/api/projects/{project['id']}/chats", json={"agent": "project-copilot"}).json()
    assert mine.patch(f"/api/chats/{thread['id']}", json={"model": "m-other"}).status_code == 403, "the chat picker is checked on the server too"
    assert mine.post(f"/api/projects/{project['id']}/chats", json={"agent": "project-copilot", "model": "m-other"}).status_code == 403
    assert events_of(user["id"]).count("model.refused:m-other") == 3 and "qa-admin" not in json.dumps(events_of(user["id"]))
    assert mine.patch(f"/api/chats/{thread['id']}", json={"model": "m-a"}).json()["model"] == "m-a"
    # the admin can still point an agent at a model the user lacks, and then that user's work with that agent is refused, not quietly switched
    assert client.put("/api/agents/business-analyst/settings", json={"enabled": True, "max_tokens": None, "reason": "test", "model": "m-other"}).status_code == 200
    run = ba_through_intake(mine, start_ba(mine, project).json()["id"])
    assert run["status"] == "failed" and run["failure"]["code"] == "AQE-ALLOW-001" and "m-other" in run["failure"]["message"]
    client.put("/api/agents/business-analyst/settings", json={"enabled": True, "max_tokens": None, "reason": "", "model": ""})


def test_a_user_with_no_model_ticked_cannot_run_or_chat(client):
    llm.set_client_override(ScriptedClient(rules()))
    name = unique()
    make_user(client, name, models=[])
    mine = As(client, name)
    project = mine.post("/api/projects", json={"name": "None", "description": ""}).json()
    refused = start_ba(mine, project)
    assert refused.status_code == 403 and refused.json()["code"] == "AQE-ALLOW-001" and "No models are allowed" in refused.json()["message"]
    with pytest.raises(auth.AllowanceError, match="No models are allowed"):
        asyncio.run(_text(project["id"], "business-analyst", mine.get("/api/auth/me").json()["id"]))


async def _text(project_id, agent, user_id):
    from backend.maf.runtime import AgentCall

    auth.current_user.set({"id": user_id, "role": "user"})
    call = AgentCall(None, project_id, agent)
    return await call.text("hello")


def test_the_default_must_be_one_of_the_ticked_models_and_a_blank_one_becomes_the_first(client):
    listed("m-a", "m-b")
    name = unique()
    user = make_user(client, name, models=["m-a", "m-b"], model="m-b")
    assert user["models"] == ["m-a", "m-b"] and user["model"] == "m-b"
    assert client.patch(f"/api/users/{user['id']}", json={"model": "m-zzz"}).status_code == 400
    assert client.patch(f"/api/users/{user['id']}", json={"models": ["m-a"]}).json()["model"] == "m-a", "unticking the default moves it to a ticked model"
    assert client.patch(f"/api/users/{user['id']}", json={"models": ["m-a"], "model": "m-b"}).status_code == 400
    assert client.patch(f"/api/users/{user['id']}", json={"models": ["not-listed"]}).status_code == 400


def test_switching_a_model_off_removes_it_for_everyone_and_the_wildcard_is_never_a_model(client):
    user, mine, project = account(client, ("m-a", "m-off"))
    assert mine.get("/api/settings/models").json()["models"] == ["m-a", "m-off"]
    client.patch("/api/models", json={"name": "m-off", "enabled": False})
    assert mine.get("/api/settings/models").json()["models"] == ["m-a"]
    assert start_ba(mine, project, model="m-off").status_code == 403
    assert client.post("/api/models", json={"name": "*"}).status_code == 400
    assert client.patch("/api/models", json={"name": "m-off", "is_default": True}).status_code == 400, "a switched-off model cannot be the default"
    assert mine.get("/api/models").status_code == 403 and mine.post("/api/models", json={"name": "x"}).status_code == 403


def test_load_from_proxy_drops_the_wildcard_enables_nothing_and_test_reports_an_empty_answer(client, monkeypatch):
    payloads = {"/models": {"data": [{"id": "*"}, {"id": "openai/*"}, {"id": "proxy-a"}, {"id": "proxy-b"}, {"id": "proxy-a"}]},
                "/chat/completions": {"choices": [{"message": {"content": ""}, "finish_reason": "length"}], "usage": {"prompt_tokens": 5, "completion_tokens": 200}}}

    class Reply:
        status_code, text = 200, ""

        def __init__(self, body):
            self.body = body

        def json(self):
            return self.body

    class Fake:
        def __init__(self, **_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def get(self, url, **_):
            return Reply(payloads["/models"])

        async def post(self, url, **_):
            return Reply(payloads["/chat/completions"])

    monkeypatch.setattr(llm.httpx, "AsyncClient", Fake)
    monkeypatch.setattr(llm, "current", lambda: {"base_url": "https://proxy.test/v1", "model": "proxy-a", "api_key": "key-123456789"})
    loaded = client.post("/api/models/load").json()
    assert loaded["listed"] == 2 and sorted(loaded["added"]) == ["proxy-a", "proxy-b"]
    by_name = {m["name"]: m for m in loaded["models"]}
    assert "*" not in by_name and not by_name["proxy-a"]["enabled"] and not by_name["proxy-b"]["enabled"], "listing does not mean it works"
    tested = client.post("/api/settings/llm/test", json={"model": "proxy-a"}).json()
    assert tested["ok"] is False and "answered with nothing" in tested["error"] and tested["tokens"] == 205
    payloads["/chat/completions"] = {"choices": [{"message": {"content": "PONG"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}
    assert client.post("/api/settings/llm/test", json={"model": "proxy-a"}).json()["ok"] is True


# ---- which model a call uses ---------------------------------------------------------------

def test_model_order_is_run_then_agent_then_user_then_system_and_each_call_records_it(client):
    llm.set_client_override(ScriptedClient(rules()))
    listed("m-run", "m-agent", "m-user", "m-system")
    models.update("m-system", {"is_default": True})
    name = unique()
    user = make_user(client, name, models=["m-run", "m-agent", "m-user"], model="m-user")
    mine = As(client, name)
    assert client.put("/api/agents/business-analyst/settings", json={"enabled": True, "max_tokens": None, "reason": "cheaper", "model": "m-agent"}).status_code == 200

    def fresh():
        return mine.post("/api/projects", json={"name": "Order", "description": ""}).json()

    first = start_ba(mine, fresh(), model="m-run").json()
    ba_through_intake(mine, first["id"])
    assert used_models(first["id"]) == {"business-analyst": "m-run", "confidence-reviewer": "m-run"}, "the run's choice beats the agent's model"
    second = start_ba(mine, fresh()).json()
    ba_through_intake(mine, second["id"])
    assert used_models(second["id"]) == {"business-analyst": "m-agent", "confidence-reviewer": "m-user"}, "the agent's model, else the user's default"
    third = start_ba(client, client.post("/api/projects", json={"name": "Admin", "description": ""}).json()).json()
    ba_through_intake(client, third["id"])
    assert used_models(third["id"]) == {"business-analyst": "m-agent", "confidence-reviewer": "m-system"}, "the admin has no default of their own, so the system default applies"
    with db() as con:
        owners = {r["user_id"] for r in rows(con.execute("SELECT DISTINCT user_id FROM agent_calls WHERE run_id IN (?,?)", (first["id"], second["id"])))}
    assert owners == {user["id"]}
    client.put("/api/agents/business-analyst/settings", json={"enabled": True, "max_tokens": None, "reason": "", "model": ""})


def test_an_agent_cannot_be_pointed_at_a_model_that_is_not_enabled(client):
    models.add("m-off-agent")
    refused = client.put("/api/agents/business-analyst/settings", json={"enabled": True, "max_tokens": None, "reason": "x", "model": "m-off-agent"})
    assert refused.status_code == 400 and "enabled" in refused.json()["message"]


# ---- limits --------------------------------------------------------------------------------

@pytest.mark.parametrize("period,row_at,still_blocked,free_at,word", [
    ("day", "2026-11-04T09:00:00+00:00", "2026-11-04T18:00:00+00:00", "2026-11-04T19:00:00+00:00", "daily"),     # Kolkata midnight is 18:30 UTC
    ("week", "2026-11-04T09:00:00+00:00", "2026-11-08T10:00:00+00:00", "2026-11-09T10:00:00+00:00", "weekly"),  # Monday 9 November, local
    ("month", "2026-11-04T09:00:00+00:00", "2026-11-30T10:00:00+00:00", "2026-12-01T10:00:00+00:00", "monthly"),
])
def test_each_limit_stops_a_start_with_its_reset_time_then_allows_it_after_the_reset(client, monkeypatch, period, row_at, still_blocked, free_at, word):
    llm.set_client_override(ScriptedClient(rules()))
    user, mine, project = account(client)
    client.patch(f"/api/users/{user['id']}", json={"limits": {period: 100}})
    spend(user["id"], 100, created_at=row_at)
    at(monkeypatch, "2026-11-04T10:00:00+00:00")
    stopped = start_ba(mine, project)
    body = stopped.json()
    assert stopped.status_code == 429 and body["code"] == "AQE-ALLOW-002" and word in body["message"] and "resets at" in body["message"] and "IST" in body["message"]
    at(monkeypatch, still_blocked)
    assert start_ba(mine, project).status_code == 429, "not reset yet"
    at(monkeypatch, free_at)
    assert start_ba(mine, project).status_code == 201, "reset: works again"


def test_the_overall_allocation_and_the_period_limits_apply_together(client, monkeypatch):
    user, mine, project = account(client, token_limit=10_000)
    at(monkeypatch, "2026-11-04T10:00:00+00:00")
    client.patch(f"/api/users/{user['id']}", json={"limits": {"day": 50, "month": 10_000}})
    spend(user["id"], 60, created_at="2026-11-04T09:00:00+00:00")
    with pytest.raises(auth.AllowanceError) as stopped:
        auth.check_allowance(project["id"], user["id"])
    assert stopped.value.code == "AQE-ALLOW-002" and "daily" in stopped.value.message
    client.patch(f"/api/users/{user['id']}", json={"limits": {"day": None}})
    auth.check_allowance(project["id"], user["id"])
    spend(user["id"], 10_000, created_at="2026-11-04T09:30:00+00:00")
    with pytest.raises(auth.AllowanceError) as stopped:
        auth.check_allowance(project["id"], user["id"])
    assert stopped.value.code == "AQE-ALLOW-001" and "allocation" in stopped.value.message


def test_a_per_model_limit_stops_only_that_model(client, monkeypatch):
    user, mine, project = account(client, ("m-a", "m-pricey"))
    at(monkeypatch, "2026-11-04T10:00:00+00:00")
    client.patch(f"/api/users/{user['id']}", json={"model_limits": [{"model": "m-pricey", "period": "day", "tokens": 100}]})
    spend(user["id"], 100, model="m-pricey", created_at="2026-11-04T09:00:00+00:00")
    auth.check_allowance(project["id"], user["id"], "m-a")
    with pytest.raises(auth.AllowanceError) as stopped:
        auth.check_allowance(project["id"], user["id"], "m-pricey")
    assert stopped.value.code == "AQE-ALLOW-002" and "m-pricey" in stopped.value.message
    assert client.patch(f"/api/users/{user['id']}", json={"model_limits": [{"model": "m-unticked", "period": "day", "tokens": 5}]}).status_code == 400
    assert mine.get("/api/auth/me").json()["model_usage"] == {"m-pricey": 100}


def test_the_time_zone_decides_where_a_day_starts(client, monkeypatch):
    user, mine, project = account(client)
    client.patch(f"/api/users/{user['id']}", json={"limits": {"day": 100}})
    spend(user["id"], 100, created_at="2026-11-04T19:00:00+00:00")  # 00:30 on 5 November in Kolkata, 19:00 on 4 November in UTC
    at(monkeypatch, "2026-11-05T00:30:00+00:00")
    assert models.timezone_name() == "Asia/Kolkata", "the default zone"
    assert models.limit_problem(user["id"]) is not None
    assert client.put("/api/settings/timezone", json={"timezone": "UTC"}).json() == {"timezone": "UTC"}
    try:
        assert models.limit_problem(user["id"]) is None, "in UTC that spending belongs to the day before"
    finally:
        client.put("/api/settings/timezone", json={"timezone": "Asia/Kolkata"})
    assert client.put("/api/settings/timezone", json={"timezone": "Mars/Base"}).status_code == 400
    assert mine.put("/api/settings/timezone", json={"timezone": "UTC"}).status_code == 403


def test_a_limit_during_a_qe_run_stops_it_keeps_finished_batches_and_retry_continues_after_the_reset(client, monkeypatch):
    user, mine, project = account(client)
    client.patch(f"/api/users/{user['id']}", json={"limits": {"day": 100_000}})
    at(monkeypatch, "2026-11-04T10:00:00+00:00")
    from backend.maf import runtime

    monkeypatch.setattr(runtime, "MODEL_CONCURRENCY", 1)
    designer, reviews = Designer(), []
    designer.healed = True

    def review(text):
        if "Score this test cases" in text:
            reviews.append(1)
            if len(reviews) == 2:  # other work by the same account uses up the day while the second batch is being reviewed
                spend(user["id"], 1_000_000, created_at="2026-11-04T10:00:00+00:00")
        return GOOD_REVIEW.replace("90", "95")

    upload_repo(mine, project, {"calc.py": "def add(a, b):\n    return a + b\n", "conftest.py": ""})
    from tests.test_errors import PLAN, REQUIREMENTS

    llm.set_client_override(ScriptedClient([("You are a repository intelligence analyst", "## Purpose\nCalculator"), ("You are a requirements analyst", REQUIREMENTS), ("You are a principal test architect", PLAN),
                                            ("You are an independent reviewer", review), ("You are a test design architect", designer)]))
    run = mine.post(f"/api/projects/{project['id']}/runs", json={"workflow": "qe"}).json()
    for _ in range(4):
        run = wait_run(mine, run["id"])
        if run["status"] != "waiting_approval":
            break
        mine.post(f"/api/approvals/{pending(run)['id']}/decide", json={"approved": True})
    run = wait_run(mine, run["id"], ("failed", "waiting_approval", "completed"))
    assert run["status"] == "failed" and run["failure"]["code"] == "AQE-ALLOW-002" and run["failure"]["stage"] == "design"
    assert "partial" not in run["state"] and not any(a["status"] == "pending" for a in run["approvals"]), "a limit never becomes an approvable partial result"
    kept = list((config.RUNS / run["id"] / "parts" / "design").glob("*.json"))
    assert len(kept) == 2, "the batches that finished before the limit are saved"
    refused = mine.post(f"/api/runs/{run['id']}/retry")
    assert refused.status_code == 429 and refused.json()["code"] == "AQE-ALLOW-002", "retry waits for the reset"
    assert mine.get(f"/api/runs/{run['id']}").json()["status"] == "failed"
    asked = len(designer.batches)
    at(monkeypatch, "2026-11-05T10:00:00+00:00")
    assert mine.post(f"/api/runs/{run['id']}/retry").status_code == 200
    run = wait_run(mine, run["id"])
    assert run["status"] == "waiting_approval" and pending(run)["gate"] == 3 and "PARTIAL" not in pending(run)["title"]
    assert {r for batch in designer.batches[asked:] for r in batch} == set(IDS[8:]), "only the batches that had not finished are asked again"
    doc = next(d for d in mine.get(f"/api/projects/{project['id']}/documents").json() if d["kind"] == "test_cases")
    assert len(mine.get(f"/api/documents/{doc['id']}").json()["data"]) == 64


def test_chat_obeys_the_limits_and_says_when_they_reset(client, monkeypatch):
    user, mine, project = account(client)
    client.patch(f"/api/users/{user['id']}", json={"limits": {"day": 100}})
    at(monkeypatch, "2026-11-04T10:00:00+00:00")
    spend(user["id"], 100, created_at="2026-11-04T09:00:00+00:00")
    llm.set_client_override(ScriptedClient([("You are the Agentic QE Platform project copilot", "Hello")]))
    thread = mine.post(f"/api/projects/{project['id']}/chats", json={"agent": "project-copilot"}).json()
    body = {"threadId": thread["id"], "runId": "r1", "messages": [{"id": "m1", "role": "user", "content": "hi"}], "state": {}, "tools": [], "context": [], "forwardedProps": {}}
    with mine.stream("POST", "/agui/project-copilot", json=body) as response:
        text = "".join(response.iter_text())
    assert "RUN_ERROR" in text and "AQE-ALLOW-002" in text and "resets at" in text and "Hello" not in text
    at(monkeypatch, "2026-11-04T19:00:00+00:00")
    with mine.stream("POST", "/agui/project-copilot", json=body) as response:
        text = "".join(response.iter_text())
    assert "Hello" in text and "RUN_ERROR" not in text
    with db() as con:
        last = rows(con.execute("SELECT model, user_id, source FROM agent_calls WHERE project_id=? ORDER BY id DESC LIMIT 1", (project["id"],)))[0]
    assert last == {"model": "m-a", "user_id": user["id"], "source": "chat"}


def test_admin_work_and_evals_never_count_against_a_user(client):
    from backend.maf import evals

    user, mine, project = account(client)
    llm.set_client_override(ScriptedClient([("You are an independent reviewer", "ok")]))
    evals._sandbox()

    async def as_admin():
        from backend.maf.runtime import AgentCall

        auth.current_user.set({"id": "admin", "role": "admin"})
        return await AgentCall(None, evals.EVAL_PROJECT, "confidence-reviewer", source="eval").text("x")

    before = mine.get("/api/auth/me").json()["tokens_used"]
    asyncio.run(as_admin())
    with db() as con:
        call = rows(con.execute("SELECT user_id FROM agent_calls WHERE source='eval' ORDER BY id DESC LIMIT 1"))[0]
    assert call["user_id"] == "admin" and mine.get("/api/auth/me").json()["tokens_used"] == before
    assert client.get("/api/auth/me").json()["usage"] is None, "the admin has no limits"


# ---- usage report ----------------------------------------------------------------------------

def test_usage_is_admin_only_exports_csv_and_an_empty_database_gives_empty_lists(client, tmp_path, monkeypatch):
    user, mine, project = account(client, ("m-usage-a", "m-usage-b"))
    spend(user["id"], 40, model="m-usage-a")
    spend(user["id"], 60, model="m-usage-b")
    assert mine.get("/api/usage").status_code == 403 and mine.get("/api/usage?format=csv").status_code == 403
    report = client.get("/api/usage").json()
    assert {"name": "m-usage-a", "tokens": 40} in report["by_model"] and {"name": "m-usage-b", "tokens": 60} in report["by_model"] and report["timezone"] == "Asia/Kolkata"
    assert any(r["name"] == mine.get("/api/auth/me").json()["username"] for r in report["by_user"]), "the admin sees login names"
    csv_text = client.get("/api/usage?format=csv").text
    assert csv_text.splitlines()[0] == "day,user,model,agent,calls,tokens_in,tokens_out" and "m-usage-b" in csv_text
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "empty.sqlite3")
    database.migrate()
    assert models.usage_rows(30) == []


def test_user_names_in_usage_follow_the_existing_rule(client):
    user, mine, project = account(client)
    spend(user["id"], 5)
    assert mine.get("/api/usage").status_code == 403, "no other route shows login names to a user"
    assert "username" not in json.dumps(mine.get("/api/settings/models").json())


# ---- secrets ----------------------------------------------------------------------------------

def test_a_secret_and_a_password_in_a_reply_or_request_reach_no_table_or_log(client, caplog):
    secret = "sk-" + "Qw7" * 12
    caplog.set_level("DEBUG")
    llm.set_client_override(ScriptedClient([("You are the Agentic QE Platform project copilot", f"Your key is {secret} and password={USER_PASSWORD}")]))
    user, mine, project = account(client)
    thread = mine.post(f"/api/projects/{project['id']}/chats", json={"agent": "project-copilot"}).json()
    body = {"threadId": thread["id"], "runId": "r1", "messages": [{"id": "m1", "role": "user", "content": f"remember {secret}"}], "state": {}, "tools": [], "context": [], "forwardedProps": {}}
    with mine.stream("POST", "/agui/project-copilot", json=body) as response:
        streamed = "".join(response.iter_text())
    assert start_ba(mine, project, model="m-other-unlisted").status_code == 403
    with db() as con:
        tables = [t["name"] for t in rows(con.execute("SELECT name FROM sqlite_master WHERE type='table'"))]
        stored = json.dumps({t: rows(con.execute(f"SELECT * FROM {t}")) for t in tables}, default=str)
    username = mine.get("/api/auth/me").json()["username"]
    logs = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in config.LOGS.glob("*.jsonl")) if config.LOGS.exists() else ""
    for place, text in {"table": stored, "log": caplog.text + logs, "stream": streamed}.items():
        assert secret not in text and "Qw7Qw7Qw7Qw7" not in text, f"secret reached the {place}"
    assert USER_PASSWORD not in stored + caplog.text + logs, "the password is only in a hash"
    assert username not in stored, "login names are encrypted in the users table and absent elsewhere"
    with db() as con:
        events = json.dumps(rows(con.execute("SELECT * FROM auth_events")))
    assert username not in events and USER_PASSWORD not in events, "auth events name the account id, never the login"


# ---- migration -----------------------------------------------------------------------------------

def test_migration_009_copies_each_users_model_into_the_allowed_list_and_backfills_calls(tmp_path, monkeypatch):
    path = tmp_path / "phase2.sqlite3"
    monkeypatch.setattr(database, "DB_PATH", path)
    con = sqlite3.connect(path)
    for sql in sorted(database.MIGRATIONS.glob("*.sql")):
        if int(sql.name.split("_")[0]) <= 8:
            con.executescript(sql.read_text(encoding="utf-8"))
    con.execute("PRAGMA user_version=8")
    stamp = now()
    for uid, model in (("usr_one", "model-one"), ("usr_two", "model-one"), ("usr_three", ""), ("usr_four", "model-four")):
        con.execute("INSERT INTO users (id, username_lookup, username_enc, password_hash, model, token_limit, active_from, active_until, enabled, created_at, updated_at) VALUES (?,?,?,?,?,NULL,NULL,NULL,1,?,?)", (uid, uid + "k", "enc", "hash", model, stamp, stamp))
    con.execute("INSERT INTO settings VALUES ('llm_model', 'system-model')")
    for pid, owner in (("p_one", "usr_one"), ("p_admin", "admin"), ("prj_agent_evals", None)):
        con.execute("INSERT INTO projects (id, name, description, owner_id, created_at, updated_at, archived) VALUES (?,?,?,?,?,?,0)", (pid, pid, "", owner, stamp, stamp))
    for pid in ("p_one", "p_admin", "prj_agent_evals"):
        con.execute("INSERT INTO agent_calls (agent, project_id, source, prompt_ref, tokens_in, tokens_out, status, created_at) VALUES ('project-copilot', ?, 'chat', 'x', 7, 3, 'ok', ?)", (pid, stamp))
    con.execute("INSERT INTO runs (id, project_id, workflow, status, input, started_at) VALUES ('run_old', 'p_one', 'qe', 'failed', '{}', ?)", (stamp,))
    con.commit()
    con.close()
    database.migrate()
    with database.db() as c:
        listed_models = {m["name"]: m for m in rows(c.execute("SELECT * FROM models"))}
        ticks = {(r["user_id"], r["model"]) for r in rows(c.execute("SELECT * FROM user_models"))}
        calls = {r["project_id"]: r["user_id"] for r in rows(c.execute("SELECT project_id, user_id FROM agent_calls"))}
        run_user = c.execute("SELECT user_id, model FROM runs WHERE id='run_old'").fetchone()
        users = {r["id"]: r["model"] for r in rows(c.execute("SELECT id, model FROM users"))}
    assert set(listed_models) == {"system-model", "model-one", "model-four"} and listed_models["system-model"]["is_default"] == 1 and all(m["enabled"] for m in listed_models.values())
    assert ticks == {("usr_one", "model-one"), ("usr_two", "model-one"), ("usr_three", "system-model"), ("usr_four", "model-four")}, "nobody loses access, including users on the system default"
    assert users == {"usr_one": "model-one", "usr_two": "model-one", "usr_three": "", "usr_four": "model-four"}, "users.model stays as the user's default"
    assert calls == {"p_one": "usr_one", "p_admin": "admin", "prj_agent_evals": "admin"} and tuple(run_user) == ("usr_one", "")
    assert auth.tokens_used("usr_one") == 10
    assert path.exists() and models.allowed("usr_three") == ["system-model"]
