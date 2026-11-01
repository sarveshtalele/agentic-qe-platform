"""Typed errors, failure records, retry from the failed stage, kept batches, and the API error shape. Only the model is scripted."""
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import openai
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from backend import config
from backend.app import app
from backend.core import errors
from backend.db import db, rows
from backend.maf import llm
from backend.maf.runtime import AgentCall, extract_json
from tests.scripted_client import ScriptedClient
from tests.test_api_workflows import GOOD_REVIEW, USER_PASSWORD, client, make_user, pending, project, sign_in, unique, upload_repo, wait_run  # noqa: F401 - fixtures

IDS = [f"REQ-{n:03d}" for n in range(1, 17)]  # 16 requirements make four design batches of four
REQUIREMENTS = json.dumps({"requirements": [{"id": i, "title": i, "statement": f"add behaves for {i}", "priority": "P0", "tier": "observed", "file": "calc.py", "line": 2, "quote": "return a + b"} for i in IDS]})
PLAN = json.dumps({"strategy": "Unit first", "areas": [{"id": "A1", "name": "Add", "requirement_ids": IDS, "risk": "P0", "level": "Unit", "framework": "pytest", "rationale": "Pure logic"}], "skipped_levels": {"Integration": "No IO", "E2E": "No UI"}})
SECRET = "sk-" + "Zq9" * 12


class Shape(BaseModel):
    cases: list[dict]


def cases_for(wanted):
    return json.dumps({"cases": [{"id": "TC-APP-001", "requirement_id": r, "scenario": f"{r} {k}", "type": k, "level": "Unit", "steps": ["call add"], "expected_result": "correct", "oracle": "specified"}
                                 for r in wanted for k in ["Positive", "Negative", "Negative (Boundary)", "Exception"]]})


class Designer:
    """Answers design requests. The batch holding REQ-013 gets a broken reply until healed."""

    def __init__(self, broken="I cannot produce that."):
        self.healed, self.broken, self.batches = False, broken, []

    def __call__(self, text):
        section = text.rsplit("Design test cases for only these requirements", 1)[-1].split("PLAN:")[0]
        wanted = [i for i in IDS if i in section]
        self.batches.append(wanted)
        return self.broken if "REQ-013" in wanted and not self.healed else cases_for(wanted)


def qe_client(designer):
    llm.set_client_override(ScriptedClient([
        ("You are a repository intelligence analyst", "## Purpose\nCalculator"), ("You are a requirements analyst", REQUIREMENTS), ("You are a principal test architect", PLAN),
        ("You are an independent reviewer", GOOD_REVIEW.replace("90", "95")), ("You are a test design architect", designer)]))


def run_to_design(client, project, designer):
    upload_repo(client, project, {"calc.py": "def add(a, b):\n    return a + b\n", "conftest.py": ""})
    qe_client(designer)
    run = client.post(f"/api/projects/{project['id']}/runs", json={"workflow": "qe"}).json()
    for _ in range(4):
        run = wait_run(client, run["id"])
        if run["status"] != "waiting_approval":
            break
        client.post(f"/api/approvals/{pending(run)['id']}/decide", json={"approved": True})
    return wait_run(client, run["id"], ("waiting_approval", "failed", "completed"))


def test_one_failed_design_batch_keeps_the_other_three_and_retry_repeats_only_it(client, project):
    designer = Designer()
    run = run_to_design(client, project, designer)
    assert run["status"] == "failed" and run["failure"]["code"] == "AQE-MODEL-001" and run["failure"]["stage"] == "design"
    kept = list((config.RUNS / run["id"] / "parts" / "design").glob("*.json"))
    assert len(kept) == 3, "three finished batches were saved as they completed"
    first_pass = len(designer.batches)
    designer.healed = True
    assert client.post(f"/api/runs/{run['id']}/retry").status_code == 200
    run = wait_run(client, run["id"])
    assert run["status"] == "waiting_approval" and pending(run)["gate"] == 3 and "PARTIAL" not in pending(run)["title"]
    repeated = {r for batch in designer.batches[first_pass:] for r in batch}
    assert repeated == set(IDS[12:]), "only the failed batch is asked again"
    doc = next(d for d in client.get(f"/api/projects/{project['id']}/documents").json() if d["kind"] == "test_cases")
    assert len(client.get(f"/api/documents/{doc['id']}").json()["data"]) == 64 and "partial" not in pending(run)["payload"]
    assert not (config.RUNS / run["id"] / "parts" / "design").exists(), "kept batches are cleared once the stage finishes"


def test_batches_that_keep_failing_end_as_a_partial_result_that_cannot_be_approved(client, project):
    designer = Designer()
    run = run_to_design(client, project, designer)
    for _ in range(2):  # the third run of the stage may end partial
        assert run["status"] == "failed"
        assert client.post(f"/api/runs/{run['id']}/retry").status_code == 200
        run = wait_run(client, run["id"], ("waiting_approval", "failed"))
    assert run["status"] == "waiting_approval"
    gate = pending(run)
    assert "PARTIAL" in gate["title"] and "REQ-013" in gate["summary"] and gate["payload"]["partial"]["missing"] == IDS[12:]
    doc = next(d for d in client.get(f"/api/projects/{project['id']}/documents").json() if d["kind"] == "test_cases")
    assert "PARTIAL" in doc["title"] and len(client.get(f"/api/documents/{doc['id']}").json()["data"]) == 48
    refused = client.post(f"/api/approvals/{gate['id']}/decide", json={"approved": True})
    assert refused.status_code == 400 and "partial" in refused.json()["message"] and refused.json()["error_id"]
    assert pending(client.get(f"/api/runs/{run['id']}").json())["status"] == "pending", "a refused approval changes nothing"


def test_only_one_retry_can_run_at_a_time(client, project):
    designer = Designer()
    run = run_to_design(client, project, designer)
    designer.healed = True
    with ThreadPoolExecutor(2) as pool:
        codes = sorted(f.result().status_code for f in [pool.submit(client.post, f"/api/runs/{run['id']}/retry") for _ in range(2)])
    assert codes == [200, 409]
    assert wait_run(client, run["id"])["status"] == "waiting_approval"
    assert client.post(f"/api/runs/{run['id']}/retry").status_code == 409, "a run that is not failed cannot be retried"


def test_a_retry_counts_against_the_run_token_limit(client, project, monkeypatch):
    from backend.maf import engine

    run = run_to_design(client, project, Designer())
    monkeypatch.setattr(engine, "RUN_TOKEN_LIMIT", 1)
    refused = client.post(f"/api/runs/{run['id']}/retry")
    assert refused.status_code == 403 and refused.json()["code"] == "AQE-ALLOW-001" and "ATLAS_RUN_TOKEN_LIMIT" in refused.json()["action"]
    assert client.get(f"/api/runs/{run['id']}").json()["status"] == "failed"


def test_retry_belongs_to_the_projects_owner(client):
    first, second = unique("owner"), unique("other")
    make_user(client, first)
    make_user(client, second)
    mine, _ = sign_in(first)
    theirs, _ = sign_in(second)
    project = mine.post("/api/projects", json={"name": "Mine", "description": ""}).json()
    with db() as con:
        con.execute("INSERT INTO runs (id, project_id, workflow, status, input, started_at) VALUES ('run_owned', ?, 'qe', 'failed', '{}', '2026-01-01T00:00:00+00:00')", (project["id"],))
    refused = theirs.post("/api/runs/run_owned/retry")
    assert refused.status_code == 404 and refused.json()["message"] == "Not found", "another user is told nothing about the run"
    assert TestClient(app).post("/api/runs/run_owned/retry").status_code == 401
    llm.set_client_override(ScriptedClient([("x", "ok")]))
    assert mine.post("/api/runs/run_owned/retry").status_code != 404, "the owner reaches the route"
    assert client.post("/api/runs/run_missing/retry").status_code == 404


def ask(project, reply, schema=Shape, agent="confidence-reviewer", attempts=3):
    """Run AgentCall.typed against a scripted reply and return the error it ends with."""
    scripted = ScriptedClient([("Review this", reply)])
    llm.set_client_override(scripted)
    return scripted, AgentCall(None, project["id"], agent)


def fails(client, project, reply, schema=Shape):
    scripted, call = ask(project, reply, schema)
    with pytest.raises(errors.AqeError) as caught:
        client.portal.call(call.typed, "Review this", schema)
    return caught.value, scripted


def request():
    return httpx.Request("POST", "http://proxy.test/v1/chat/completions")


def refuse(exc):
    def raiser(_text):
        raise exc

    return raiser


def test_broken_json_of_every_kind_is_never_replaced_by_a_fragment(client, project):
    cut_off = '{"cases": [{"id": "A", "x": 1}, {"id": "B", "x": '
    error, scripted = fails(client, project, cut_off)
    assert error.code == "AQE-MODEL-001" and "not valid JSON near character" in error.message and error.detail["parse_pos"] > 0
    assert error.retryable and error.action and "That reply was rejected" in scripted.calls[-1], "the position goes back to the model"
    assert error.detail["reply"] == cut_off.strip()
    nested = '{"cases": [{"id": "A", "steps": [{"k": 1}], "x": '  # a complete list inside a case is not the answer
    for names in (("cases",), ()):
        with pytest.raises(ValueError, match="not valid JSON"):
            extract_json(nested, names)
    with pytest.raises(ValueError):
        extract_json('{"cases": [{"id": "A"} {"id": "B"}]}', ("cases",))  # a missing comma
    shaped, _ = fails(client, project, '{"id": "A", "requirement_id": "R"}')
    assert shaped.code == "AQE-MODEL-003" and "not valid JSON" not in shaped.message and "cases" in shaped.message
    # a raw line break and a lone backslash are repaired, and the whole object comes back, not a part of it
    assert extract_json('{"cases": [{"id": "A", "note": "line one\nline two"}, {"id": "B"}]}', ("cases",))["cases"][1] == {"id": "B"}
    assert extract_json(r'{"cases": [{"id": "A", "pattern": "\d+ in C:\Users"}, {"id": "B"}]}', ("cases",))["cases"][0]["pattern"] == r"\d+ in C:\Users"


def test_each_error_code_comes_from_a_real_failure(client, project, tmp_path):
    from backend.core import auth
    from backend.maf.workflows import qe
    from backend.maf.engine import RunContext
    from backend.repos import git

    truncated = {"cut_off": '{"cases": [{"id": "A"'}
    error, _ = fails(client, project, truncated)
    assert error.code == "AQE-MODEL-002" and error.detail["finish_reason"] == "length" and "token limit" in error.action and not error.retryable
    assert fails(client, project, "plain prose")[0].code == "AQE-MODEL-001"
    assert fails(client, project, '{"id": "A"}')[0].code == "AQE-MODEL-003"
    timeout, _ = fails(client, project, refuse(openai.APITimeoutError(request=request())))
    assert timeout.code == "AQE-MODEL-004" and timeout.retryable and "ATLAS_MODEL_TIMEOUT" in timeout.action
    refused, _ = fails(client, project, refuse(RuntimeError("400 finish_reason content_filter blocked by label 'Jailbreak'")))
    assert refused.code == "AQE-MODEL-005" and "Jailbreak" in refused.message and not refused.retryable
    reply = httpx.Response(401, request=request(), headers={"x-request-id": "req-from-provider"})
    key, _ = fails(client, project, refuse(openai.AuthenticationError("bad key", response=reply, body=None)))
    assert key.code == "AQE-MODEL-006" and not key.retryable and "Settings" in key.action
    assert key.detail["provider_status"] == 401 and key.detail["provider_request_id"] == "req-from-provider", "the provider's status and request id are kept"
    busy, _ = fails(client, project, refuse(openai.RateLimitError("slow down", response=httpx.Response(429, request=request()), body=None)))
    assert busy.code == "AQE-MODEL-006" and busy.retryable and busy.detail["provider_status"] == 429
    assert fails(client, project, refuse(openai.APIConnectionError(request=request())))[0].code == "AQE-MODEL-006"
    # allocation
    name = unique()
    make_user(client, name, token_limit=0)
    owner, _ = sign_in(name)
    limited = owner.post("/api/projects", json={"name": "Limited", "description": ""}).json()
    with db() as con:
        con.execute("INSERT INTO agent_calls (agent, project_id, source, prompt_ref, tokens_in, tokens_out, latency_ms, tool_calls, status, created_at) VALUES ('project-copilot', ?, 'chat', 'x', 5, 5, 1, 0, 'ok', '2026-01-01')", (limited["id"],))
    with pytest.raises(errors.AllowanceError) as caught:
        auth.check_allowance(limited["id"])
    assert caught.value.code == "AQE-ALLOW-001" and "administrator" in caught.value.action and not caught.value.retryable
    # git
    with pytest.raises(errors.RepoError) as caught:
        git.run(["definitely-not-a-git-command"], cwd=tmp_path)
    assert caught.value.code == "AQE-REPO-001" and "repository" in caught.value.action
    # tests that could not run
    def timed_out(*_):
        raise subprocess.TimeoutExpired("pip", 1)

    from backend.qe import execution

    original = execution.install_dependencies
    execution.install_dependencies = timed_out
    try:
        with pytest.raises(errors.ExecutionError) as caught:
            client.portal.call(qe.qe_execute, RunContext("run_x", project["id"], "execute"), {"worktree": str(tmp_path), "install_deps": True, "framework": "pytest", "mode": "brownfield"})
    finally:
        execution.install_dependencies = original
    assert caught.value.code == "AQE-TEST-001" and "install dependencies" in caught.value.action
    # a bug in this application
    bug = errors.classify(ZeroDivisionError("division by zero"))
    assert bug.code == "AQE-INT-001" and "diagnostics" in bug.action and not bug.retryable
    # old types still work
    assert issubclass(errors.AllowanceError, RuntimeError) and issubclass(git.GitError, RuntimeError) and issubclass(llm.LLMNotConfigured, RuntimeError)


def test_evidence_failure_is_aqe_evid_001_on_the_run(client, project):
    upload_repo(client, project, {"calc.py": "def add(a, b):\n    return a + b\n", "conftest.py": ""})
    fake = json.dumps({"requirements": [{"id": "REQ-001", "title": "x", "statement": "invented", "priority": "P0", "tier": "observed", "file": "calc.py", "line": 1, "quote": "not in the file"}]})
    llm.set_client_override(ScriptedClient([("You are a repository intelligence analyst", "## Purpose\nCalc"), ("You are a requirements analyst", fake), ("You are an independent reviewer", GOOD_REVIEW)]))
    run = client.post(f"/api/projects/{project['id']}/runs", json={"workflow": "qe"}).json()
    run = wait_run(client, run["id"])
    client.post(f"/api/approvals/{pending(run)['id']}/decide", json={"approved": True})
    run = wait_run(client, run["id"], ("failed",))
    assert run["failure"]["code"] == "AQE-EVID-001" and run["failure"]["stage"] == "requirements" and "Review the requirements" in run["failure"]["action"]


def test_a_secret_in_a_rejected_reply_reaches_no_file_log_table_or_response(client, project, caplog):
    caplog.set_level("DEBUG")
    broken = '{"cases": [{"id": "A", "note": "key ' + SECRET + '", "x": '
    run = run_to_design(client, project, Designer(broken=broken))
    assert run["status"] == "failed"
    failure = run["failure"]
    saved = config.RUNS / run["id"] / failure["reply_file"]
    assert saved.is_file() and "sk-Z" in saved.read_text(encoding="utf-8"), "the reply is saved, with the secret masked"
    with db() as con:
        tables = {t["name"] for t in rows(con.execute("SELECT name FROM sqlite_master WHERE type='table'"))}
        stored = json.dumps({t: rows(con.execute(f"SELECT * FROM {t}")) for t in sorted(tables - {"users", "sessions"})}, default=str)
    files = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (config.RUNS / run["id"]).rglob("*") if p.is_file())
    api = client.get(f"/api/runs/{run['id']}").text
    for place, text in {"table": stored, "file": files, "api": api, "log": caplog.text}.items():
        assert SECRET not in text and "Zq9Zq9Zq9Zq9" not in text, f"secret reached the {place}"
    assert failure["stack"] and "Traceback" in failure["stack"]


def test_every_error_has_the_same_shape_and_a_request_id(client, project, monkeypatch, caplog):
    import os

    from backend.maf import engine

    caplog.set_level("DEBUG")
    missing = client.get("/api/runs/run_missing")
    body = missing.json()
    assert missing.status_code == 404 and set(body) == {"code", "message", "action", "error_id", "detail"} and body["detail"] == body["message"] and body["error_id"].startswith("err_")
    assert missing.headers["X-Request-Id"].startswith("req_")
    invalid = client.post("/api/projects", json={"description": "no name"})
    assert invalid.status_code == 422 and isinstance(invalid.json()["detail"], list) and invalid.json()["message"] and invalid.headers["X-Request-Id"]
    anonymous = TestClient(app).get("/api/projects")
    assert anonymous.status_code == 401 and anonymous.json()["detail"] == "Sign in first" and anonymous.headers["X-Request-Id"]
    assert client.get("/api/health").headers["X-Request-Id"], "success responses carry it too"
    assert client.get("/api/health").headers["X-Request-Id"] != client.get("/api/health").headers["X-Request-Id"]
    llm.set_client_override(None)
    monkeypatch.setattr(llm, "current", lambda: {"base_url": "", "model": "", "api_key": ""})  # other tests may have saved a model in settings
    typed = client.post(f"/api/projects/{project['id']}/runs", json={"workflow": "qe"})
    assert typed.status_code == 412 and typed.json()["code"] == "AQE-MODEL-006" and "Settings" in typed.json()["action"]
    # a bug becomes a 500 with an id, and the secret in its message goes nowhere
    def boom(_run_id):
        raise ZeroDivisionError(f"broke with {SECRET}")

    monkeypatch.setattr(engine, "get", boom)
    with TestClient(app, raise_server_exceptions=False) as quiet:
        quiet.post("/api/auth/login", json={"username": "qa-admin", "password": os.environ["ATLAS_ADMIN_PASSWORD"]})
        crashed = quiet.get("/api/runs/run_any")
    assert crashed.status_code == 500 and crashed.json()["code"] == "AQE-INT-001" and crashed.json()["error_id"] and crashed.headers["X-Request-Id"]
    assert SECRET not in crashed.text and SECRET not in caplog.text and crashed.json()["error_id"] in caplog.text


def test_failure_records_carry_what_is_needed_to_debug_them(client, project):
    run = run_to_design(client, project, Designer())
    failure = run["failure"]
    assert failure["agent"] == "test-design-architect" and failure["prompt_ref"].startswith("test-design-architect@v") and failure["attempt"] == 2
    assert failure["parse_pos"] is None and failure["technical"] and failure["reply_file"].startswith("failures/err_")
    assert (config.RUNS / run["id"] / failure["reply_file"]).read_text(encoding="utf-8") == "I cannot produce that."
    assert any(e["type"] == "error" and failure["code"] in e["message"] and e["data"]["error_id"] == failure["id"] for e in __import__("backend.maf.engine", fromlist=["x"]).events(run["id"])), "the live log carries the code"


def test_model_calls_carry_the_no_cache_control(client, project, monkeypatch):
    from backend.maf import runtime

    llm.set_client_override(ScriptedClient([("x", "ok")]))
    assert AgentCall(None, project["id"], "confidence-reviewer").agent.default_options["extra_body"] == {"cache": {"no-cache": True}}
    monkeypatch.setattr(runtime, "MODEL_NO_CACHE", False)
    assert "extra_body" not in AgentCall(None, project["id"], "confidence-reviewer").agent.default_options
