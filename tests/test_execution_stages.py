"""Classification, setup facts, case limits, test data, defect records, healing limits, and the execution summary. Only the model is scripted."""
import json
import sys

import pytest

from backend.maf import llm
from backend.qe import execution, model, test_data
from tests.scripted_client import ScriptedClient
from tests.test_api_workflows import CASES, TESTS, client, pending, project, upload_repo, wait_run  # noqa: F401 - fixtures
from tests.test_confidence import CALC, base_rules, go_to_gate

# classification


@pytest.mark.parametrize(("message", "expected"), [
    ("assert 429 == 200\n +  where 429 = <Response [429 Too Many Requests]>.status_code", "ENVIRONMENT"),
    ("assert 429 in (200, 201)", "ENVIRONMENT"),
    ("AssertionError: 429 != 200", "ENVIRONMENT"),
    ("assert 200 == 429\n +  where 429 = <Response [429 Too Many Requests]>.status_code", "ENVIRONMENT"),
    ("assert 429 == 429", "DEFECT"),
    ("assert 200 == 429", "DEFECT"),  # a test that expected 429 and did not get it found a real difference
    ("assert 500 == 200", "DEFECT"),
    ("httpx.ConnectError: All connection attempts failed", "ENVIRONMENT"),
    ("httpx.HTTPStatusError: Client error '429 Too Many Requests' for url", "ENVIRONMENT"),
    ("ModuleNotFoundError: No module named 'flask'", "ENVIRONMENT"),
    ("Failed: async def functions are not natively supported.", "ENVIRONMENT"),
    ("TypeError: required_monthly_savings() got an unexpected keyword argument 'x'", "FIXTURE_DRIFT"),
    ("TypeError: AsyncClient.__init__() got an unexpected keyword argument 'app'", "FIXTURE_DRIFT"),
    ("ImportError: cannot import name 'x' from 'a'", "FIXTURE_DRIFT"),
    ("playwright._impl._errors.TimeoutError: waiting for locator('#go')", "SELECTOR_DRIFT"),
    ("ZeroDivisionError: division by zero", "DEFECT"),
])
def test_classification_table(message, expected):
    assert execution.classify_failure(message) == expected


@pytest.mark.parametrize("message", [
    "assert 'connection refused' not in body",
    "assert 'No module named' not in response.text\n+ where 'ModuleNotFoundError' = ...",
    "AssertionError: expected ECONNREFUSED handling\nconnection refused",
    "assert 'timed out waiting for server' == ''",
    "assert response.status_code == 200\nE  assert 500 == 200\nE  429 too many requests",
])
def test_an_assertion_failure_is_never_environment(message):
    assert execution.classify_failure(message) != "ENVIRONMENT"


def junit_result(*messages):
    cases = [{"name": f"test_TC_APP_00{i}", "classname": f"tests.agentic_qe.test_tc_app_00{i}", "time": 0, "status": "failed", "message": m} for i, m in enumerate(messages, 1)]
    return {"runner": "pytest", "verdict": "FAIL", "reason": "", "exit_code": 1, "passed": 3, "failed": len(cases), "skipped": 0, "total": 3 + len(cases), "cases": cases}


def test_environment_failures_stay_failed_and_change_no_verdict_or_counts():
    result = junit_result("assert 429 == 200", "assert 1 == 2")
    assert execution.failure_counts([result]) == {"defect": 1, "test problem": 0, "environment": 1}
    assert (result["passed"], result["failed"], execution.verdict(result, 1)) == (3, 2, "FAIL")
    only_env = {**junit_result("assert 429 == 200"), "passed": 0}
    assert execution.verdict(only_env, 1) == "FAIL" and execution.verdict({**only_env, "failed": 0}, 0) == "INCONCLUSIVE"


# setup facts


def test_environment_facts_and_notes(tmp_path):
    (tmp_path / "app.py").write_text("from slowapi import Limiter\nlimiter = Limiter(key_func=len)\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_own.py").write_text("limiter = Limiter()\n")
    facts = execution.environment_facts(tmp_path, {"slowapi"})
    assert any(x["where"].startswith("app.py:") for x in facts["rate_limiters"]) and not any("tests/" in x["where"] for x in facts["rate_limiters"])
    notes = execution.environment_notes({**facts, "httpx": "0.28.1", "pytest_asyncio": False}, install_deps=False)
    assert "ASGITransport" in notes and "NOT available" in notes and "rate limiter" in notes and "running" in notes
    assert "will be installed" in execution.environment_notes({**facts, "httpx": None, "pytest_asyncio": False}, install_deps=True)


def test_async_tests_are_found_and_the_pytest_option_is_command_line_only(tmp_path):
    (tmp_path / "tests/agentic_qe").mkdir(parents=True)
    (tmp_path / "tests/agentic_qe/test_a.py").write_text("async def test_a():\n    assert 1\n")
    (tmp_path / "tests/agentic_qe/test_b.py").write_text("def test_b():\n    assert 1\n")
    assert execution.async_test_files(tmp_path) == ["tests/agentic_qe/test_a.py"]
    command, _ = execution.build_command("pytest", tmp_path, "tests/agentic_qe", tmp_path / "j.xml", ("-o", "asyncio_mode=auto"))
    assert command[-2:] == ["-o", "asyncio_mode=auto"] and not (tmp_path / "pytest.ini").exists()


# case limits


def test_case_limit_keeps_all_p0_then_p1_and_reports_what_was_left():
    reqs = [{"id": "R0", "priority": "P0"}, {"id": "R1", "priority": "P1"}, {"id": "R2", "priority": "P2"}]
    cases = [{"id": f"TC-{n}", "requirement_id": r, "priority": "P2"} for n, r in enumerate(["R2", "R1", "R0", "R2", "R0", "R1"], 1)]
    kept, info = model.limit_cases(cases, reqs, 4)
    assert [c["id"] for c in kept] == ["TC-2", "TC-3", "TC-5", "TC-6"] and info["left_out"] == ["TC-1", "TC-4"] and info["left_out_by_priority"] == {"P2": 2}
    assert info["message"].startswith("2 cases left out") and not info["p0_over_limit"]
    kept, info = model.limit_cases(cases, reqs, 1)
    assert {c["id"] for c in kept} == {"TC-3", "TC-5"} and info["p0_over_limit"] and "never cut" in info["message"]
    kept, info = model.limit_cases(cases, reqs, 60)
    assert len(kept) == 6 and info["left_out_count"] == 0 and info["message"].startswith("No cases left out")


def test_the_gate_shows_the_case_limit_and_a_real_token_estimate(client, project, monkeypatch):
    from backend.maf.workflows import qe

    monkeypatch.setattr(qe, "MAX_CASES", 1)
    many = json.loads(CASES)
    many["cases"][0]["priority"] = "P1"
    run, _ = go_to_gate(client, project, 3, base_rules(designer=json.dumps(many)))
    payload = pending(run)["payload"]
    assert payload["case_limit"]["limit"] == 1 and payload["case_limit"]["p0_over_limit"] is True, "REQ-001 is P0, so all its cases stay"
    estimate = payload["estimate"]
    assert estimate["recorded_calls"] >= 1 and estimate["estimated_tokens"] == estimate["average_tokens_per_call"] * estimate["expected_calls"] and estimate["used_so_far"] > 0
    assert len(payload["documents"]) == 2 and payload["titles"] == ["Test cases", "Test data"]


# test data


def test_test_data_port_has_the_plugins_shapes_and_no_real_personal_data():
    assert test_data.synthesize({"kind": "user", "role": "admin"}) == {"id": "usr_admin_001", "email": "testuser_admin@example.com", "role": "admin"}
    assert test_data.synthesize({"kind": "user", "valid": False})["email"] == "not-an-email"
    assert test_data.synthesize({"kind": "auth", "role": "viewer"})["Authorization"] == "Bearer mock_jwt_token_for_viewer"
    assert test_data.boundary_payload("number")["maxSafeInteger"] == 2**53 - 1 and len(test_data.boundary_payload("string")["maxLength1024"]) == 1024
    page = test_data.synthesize({"kind": "pagination", "items": list(range(25)), "pageSize": 10, "pageIndex": 2})
    assert page["items"] == [20, 21, 22, 23, 24] and page["totalPages"] == 3 and page["hasNextPage"] is False and page["hasPrevPage"] is True
    with pytest.raises(ValueError):
        test_data.synthesize({"kind": "nope"})


def test_fixtures_are_masked_bounded_and_reference_shared_datasets():
    cases = [{"id": "TC-1", "type": "Negative (Boundary)", "scenario": "Empty name", "test_data": "jane.doe@gmail.com, 123-45-6789, sk-" + "a" * 30, "steps": ["send an empty name"], "expected_result": "rejected"}]
    fixtures = test_data.build_fixtures(cases)
    text = json.dumps(fixtures)
    assert "jane.doe" not in text and "123-45-6789" not in text and "sk-" + "a" * 30 not in text and "masked@example.com" in text
    assert "boundary" in fixtures["datasets"] and fixtures["cases"]["TC-1"]["uses"]
    assert len(json.dumps(test_data.build_fixtures(cases * 1))) < test_data.FIXTURE_LIMIT


# defect records and healing limits


def test_defect_record_shape_and_text_from_the_healing_patterns():
    record = execution.failure_record(junit_result("assert 429 == 200")["cases"][0], "ENVIRONMENT")
    assert set(record) == {"test", "case_id", "classification", "class", "evidence", "cause", "fix", "pattern", "healed"}
    assert record["classification"] == "environment" and record["case_id"] == "TC-APP-001" and "rate limiter" in record["cause"] and record["healed"] is False
    defect = execution.failure_record(junit_result("assert 1 == 2")["cases"][0], "DEFECT", note={"cause": "add subtracts", "fix": "use +"})
    assert defect["classification"] == "defect" and defect["pattern"] == "Real App Bug" and (defect["cause"], defect["fix"]) == ("add subtracts", "use +")
    drift = execution.failure_record(junit_result("TypeError: f() got an unexpected keyword argument 'zz'")["cases"][0], "FIXTURE_DRIFT")
    assert drift["classification"] == "test problem" and "'zz'" in drift["cause"]


def test_healing_may_repair_drifted_tests_and_fixtures_only():
    failures = [{"class": "DEFECT", "classname": "tests.agentic_qe.test_tc_app_001", "name": "test_TC_APP_001"}, {"class": "FIXTURE_DRIFT", "classname": "tests.agentic_qe.test_tc_app_002", "name": "test_TC_APP_002"}]
    assert not execution.heal_allowed(failures, "tests/agentic_qe/test_tc_app_001.py"), "a test that found a defect stays as it is"
    assert execution.heal_allowed(failures, "tests/agentic_qe/test_tc_app_002.py") and execution.heal_allowed(failures, "tests/agentic_qe/fixtures.json")
    assert not execution.heal_allowed(failures, "calc.py") and not execution.heal_allowed(failures, "tests/agentic_qe/test_tc_app_003.py")
    assert not execution.assertions_preserved("assert a == 1\nassert b", "assert a == 1")[0], "a removed assertion is refused"


# static checks through the workflow


BAD = TESTS.replace("assert add(2, 3) == 5", "assert add(2, 3, c=4) == 5")


def run_to(client, project, number, rules):
    upload_repo(client, project, {"calc.py": CALC, "conftest.py": ""})
    scripted = ScriptedClient(rules)
    llm.set_client_override(scripted)
    run = client.post(f"/api/projects/{project['id']}/runs", json={"workflow": "qe"}).json()
    for _ in range(8):
        run = wait_run(client, run["id"])
        assert run["status"] == "waiting_approval", run["error"]
        if pending(run)["gate"] == number:
            return run, scripted
        client.post(f"/api/approvals/{pending(run)['id']}/decide", json={"approved": True})
    raise AssertionError("gate not reached")


def fixed_file():
    first = json.loads(TESTS)["files"][0]
    return json.dumps({"framework": "pytest", "files": [first]})


def test_a_bad_keyword_goes_back_alone_with_the_real_signature(client, project):
    calls = []
    rules = base_rules(designer=CASES, extra=[("fix every problem the static checks found", lambda t: (calls.append(t), fixed_file())[1])])
    rules[-1] = ("You are a test automation engineer", BAD)
    run, _ = run_to(client, project, 4, rules)
    assert len(calls) == 1, "only the one bad test is sent back"
    sent = calls[0].rsplit("Rewrite only this generated test file", 1)[-1]
    assert "'c'" in sent and "Real signature: add(a, b)" in sent and "test_tc_app_001.py" in sent and "test_tc_app_002" not in sent
    payload = pending(run)["payload"]
    assert payload["emit_unresolved"] == [] and payload["estimate"]["used_so_far"] > 0
    doc = client.get(f"/api/documents/{payload['documents'][0]}").json()
    assert "c=4" not in doc["content"] and "assert add(2, 3) == 5" in doc["content"]


def test_a_test_that_is_still_wrong_after_one_round_stays_marked(client, project):
    calls = []
    rules = base_rules(extra=[("fix every problem the static checks found", lambda t: (calls.append(t), json.dumps({"framework": "pytest", "files": [json.loads(BAD)["files"][0]]}))[1])])
    rules[-1] = ("You are a test automation engineer", BAD)
    run, _ = run_to(client, project, 4, rules)
    assert len(calls) == 1
    marked = pending(run)["payload"]["emit_unresolved"]
    assert len(marked) == 1 and marked[0]["case_id"] == "TC-APP-001" and "Real signature: add(a, b)" in marked[0]["findings"][0]
    saved = client.get(f"/api/documents/{pending(run)['payload']['documents'][0]}").json()
    assert "STATIC CHECK FINDINGS" in saved["content"] and [t for t in saved["data"] if t.get("unresolved")] == [{"case_id": "TC-APP-001", "path": "tests/agentic_qe/test_tc_app_001.py", "unresolved": True}]


# the execution summary


def summary_rules(reply):
    return base_rules(extra=[("You are a QA execution engineer", reply)])


def at_gate5(client, project, reply):
    run, _ = run_to(client, project, 5, summary_rules(reply))
    return pending(run)["payload"]


def test_the_agents_execution_summary_is_used_when_it_matches_the_junit_counts(client, project):
    good = json.dumps({"summary": "4 passed, 0 failed, 0 skipped. All tests passed.", "passed": 4, "failed": 0, "skipped": 0, "verdict": "PASS"})
    payload = at_gate5(client, project, good)
    assert payload["execution_summary"]["source"] == "agent" and payload["execution_summary"]["text"].startswith("4 passed")
    assert payload["failure_classes"] == {"defect": 0, "test problem": 0, "environment": 0} and payload["defect_records"] == []


@pytest.mark.parametrize("reply", [
    {"summary": "All good.", "passed": 3, "failed": 1, "skipped": 0, "verdict": "PASS"},
    {"summary": "All 9 tests passed.", "passed": 4, "failed": 0, "skipped": 0, "verdict": "PASS"},
    {"summary": "4 passed, 2 failed.", "passed": 4, "failed": 0, "skipped": 0, "verdict": "PASS"},
    {"summary": "Everything fine.", "passed": 4, "failed": 0, "skipped": 0, "verdict": "FAIL"},
])
def test_a_summary_that_does_not_match_the_counts_is_refused(client, project, reply):
    payload = at_gate5(client, project, json.dumps(reply))
    assert payload["execution_summary"]["source"] == "code" and "refused" in payload["execution_summary"]["reason"]
    assert payload["execution_summary"]["text"].startswith("pytest: PASS. 4 passed, 0 failed, 0 skipped")


def test_summary_checks_in_isolation():
    result = {**junit_result("assert 1 == 2"), "passed": 2}
    ok = {"summary": "2 passed, 1 failed. FAIL.", "passed": 2, "failed": 1, "skipped": 0, "verdict": "FAIL"}
    assert execution.summary_problems(ok, result) == []
    assert execution.summary_problems({**ok, "summary": "3 tests ran, 5 failed"}, result)
    assert "defect" in execution.code_summary(result)


def test_prepare_sets_async_mode_for_the_generated_tests_only_and_the_async_test_really_passes(client, project, tmp_path):
    from backend.maf.engine import RunContext
    from backend.maf.workflows import qe

    from backend.db import db, now

    pytest.importorskip("pytest_asyncio")
    with db() as con:
        con.execute("INSERT INTO runs (id, project_id, workflow, status, input, state, started_at) VALUES ('run_prep', ?, 'qe', 'running', '{}', '{}', ?)", (project["id"], now()))
    (tmp_path / "tests/agentic_qe").mkdir(parents=True)
    (tmp_path / "tests/agentic_qe/test_a.py").write_text("import asyncio\n\n\nasync def test_a():\n    await asyncio.sleep(0)\n    assert 1 + 1 == 2\n")
    update = client.portal.call(qe.qe_prepare, RunContext("run_prep", project["id"], "prepare"), {"worktree": str(tmp_path), "mode": "brownfield"})
    assert update["pytest_args"] == ["-o", "asyncio_mode=auto"] and update["async_tests"] == ["tests/agentic_qe/test_a.py"] and update["env_facts"]["pytest_asyncio"]
    result = execution.run_suite("pytest", tmp_path, "tests/agentic_qe", tmp_path / "out", 120, tuple(update["pytest_args"]))
    assert (result["passed"], result["failed"], result["verdict"]) == (1, 0, "PASS")
    assert not list(tmp_path.glob("*.ini")) and not (tmp_path / "pyproject.toml").exists(), "the repository's own config is not edited"
