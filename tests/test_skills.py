"""Plugin skills on MAF: loading, the agent mapping, injection into the message, prompt references, the chat pick, the live tool check, skill evals, the API, and the package.
Only the model (ScriptedClient) and the model endpoint (httpx.MockTransport) are scripted."""
import asyncio
import dataclasses
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import httpx
import pytest
from agent_framework import SkillsProvider, SkillsSourceContext

from backend.core import auth, models
from backend.core import skills as skill_lib
from backend.db import db, rows
from backend.maf import evals, governance, llm, skill_chat
from backend.maf import runtime as agents
from backend.maf.agents import POLICIES
from tests.scripted_client import ScriptedClient
from tests.test_api_workflows import USER_PASSWORD, client, make_user, project, sign_in, unique  # noqa: F401 - fixtures

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = {"analyzing-repositories", "authoring-user-stories", "building-qe-dashboard", "designing-test-cases", "executing-tests", "extracting-requirements",
            "generating-test-code", "generating-test-data", "healing-tests", "planning-tests", "tracing-coverage"}
ARCHITECT = "You are a principal test architect"


# ---- loading and the agent mapping ------------------------------------------------

def test_every_skill_loads_through_maf_with_its_references():
    loaded = skill_lib.load()
    assert set(loaded) == EXPECTED and skill_lib.problems() == []
    for skill in loaded.values():
        assert skill.description and skill.version == "1.4.0" and skill.body.startswith("#") and "name:" not in skill.body.split("\n")[0]
    assert set(skill_lib.references("planning-tests")) == {"LEVEL_GUIDELINES.md"}
    assert skill_lib.references("building-qe-dashboard") == {}
    assert skill_lib.get("planning-tests").sha256 and skill_lib.get("planning-tests").sha256 != skill_lib.get("tracing-coverage").sha256
    with pytest.raises(KeyError):
        skill_lib.get("no-such-skill")


def test_a_policy_that_names_an_unknown_skill_fails():
    unknown = {f"{key}: {name}" for key, policy in POLICIES.items() for name in policy.skills if name not in skill_lib.load()}
    assert not unknown, f"These policies name skills that do not exist in skills/: {sorted(unknown)}"
    assert {name for policy in POLICIES.values() for name in policy.skills} <= EXPECTED


def test_the_mapping_matches_the_plan_table():
    assert {key: policy.skills for key, policy in POLICIES.items() if policy.skills} == {
        "repo-intelligence-analyst": ("analyzing-repositories",), "requirements-analyst": ("extracting-requirements",), "business-analyst": ("authoring-user-stories",),
        "principal-test-architect": ("planning-tests",), "test-design-architect": ("designing-test-cases", "generating-test-data"), "test-automation-engineer": ("generating-test-code",),
        "defect-diagnostician": ("healing-tests",), "confidence-reviewer": ("tracing-coverage",)}
    for key in ("bug-reviewer", "feature-engineer", "project-copilot"):
        assert POLICIES[key].skills == () and skill_lib.for_agent(key) == []
    assert skill_lib.agent_of("building-qe-dashboard") == [] and skill_lib.agent_of("generating-test-data") == ["test-design-architect"]


def test_a_skill_maf_cannot_load_is_absent_and_reported(tmp_path):
    good = "---\nname: good-one\ndescription: A good skill.\nmetadata:\n  version: \"2.0\"\n---\n\n# Good\nDo the thing.\n"
    for folder, text in {"good-one": good, "Bad_Name": "---\nname: Bad_Name\ndescription: x\n---\n# no\n", "huge": "---\nname: huge\ndescription: Too big.\n---\n" + "x" * (skill_lib.BODY_LIMIT + 1)}.items():
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "SKILL.md").write_text(text, encoding="utf-8")
    loaded = skill_lib.load(root=tmp_path)
    assert set(loaded) == {"good-one"} and loaded["good-one"].version == "2.0"
    assert skill_lib.names() == sorted(EXPECTED), "loading another folder does not replace the platform's skills"


# ---- the skill text reaches the message, once, before the task --------------------

def call_for(project, key="principal-test-architect", **kwargs):
    scripted = ScriptedClient([(ARCHITECT, "ok")])
    llm.set_client_override(scripted)
    return scripted, agents.AgentCall(None, project["id"], key, **kwargs)


def test_skill_text_reaches_the_agents_message_once_and_before_the_task(client, project):
    scripted, call = call_for(project)
    client.portal.call(call.text, "Plan the thing for REQ-001.")
    client.portal.call(call.text, "Plan it again.")
    sent = scripted.calls[0]
    assert '<skill name="planning-tests" version="1.4.0">' in sent
    assert '<reference skill="planning-tests" file="LEVEL_GUIDELINES.md">' in sent and skill_lib.references("planning-tests")["LEVEL_GUIDELINES.md"][:40] in sent
    assert sent.index("<skill name=") < sent.index("TASK:\nPlan the thing for REQ-001.")
    assert "reply only in the format this request asks for" in sent
    assert scripted.calls[1].count('<skill name="planning-tests"') == 1, "the session keeps it, so a second message does not send it again"


def test_a_stage_chooses_its_skills_and_references(client, project):
    scripted, call = call_for(project, "test-design-architect", skills=("designing-test-cases",))
    scripted.rules = [("You are a test design architect", "ok")]
    client.portal.call(call.text, "Design.")
    assert '<skill name="designing-test-cases"' in scripted.calls[0] and "generating-test-data" not in scripted.calls[0] and "ORACLE_TYPES.md" in scripted.calls[0]
    scripted, call = call_for(project, refs=())
    client.portal.call(call.text, "Plan.")
    assert '<skill name="planning-tests"' in scripted.calls[0] and "<reference" not in scripted.calls[0]
    scripted, call = call_for(project, skills=())
    client.portal.call(call.text, "Plan.")
    assert "<skill" not in scripted.calls[0] and call.prompt_ref == governance.prompts.ref("principal-test-architect")
    with pytest.raises(ValueError, match="does not use the skill"):
        call_for(project, skills=("healing-tests",))
    scripted, call = call_for(project, "project-copilot")
    assert call.skill_set.text == ""


def test_skill_text_is_bounded(monkeypatch):
    monkeypatch.setattr(skill_lib, "REFERENCE_LIMIT", 10)
    rendered = skill_lib.render(["executing-tests"])
    assert rendered.skipped == ["executing-tests/RUNNER_REGISTRY.md", "executing-tests/VERSIONS.md"] and "<reference" not in rendered.text
    assert len(skill_lib.render(["planning-tests", "designing-test-cases"]).text) < skill_lib.BODY_LIMIT


def test_the_json_format_rule_still_follows_the_skill(client, project):
    scripted, call = call_for(project)
    scripted.rules = [(ARCHITECT, '{"cases": []}')]

    class Shape(agents.BaseModel):
        cases: list

    client.portal.call(call.typed, "Plan it.", Shape)
    sent = scripted.calls[0]
    assert sent.index("<skill name=") < sent.index("TASK:") < sent.index("Reply with only one JSON object")


# ---- what is recorded: the live log, agent_calls, the prompt reference -------------

def test_skill_event_agent_call_row_and_prompt_reference(client, project, monkeypatch):
    events = []
    agents.set_emitter(lambda kind, message, data=None: events.append((kind, message, data or {})))
    try:
        scripted, call = call_for(project)
        client.portal.call(call.text, "Plan.")
    finally:
        agents.set_emitter(None)
    skill_events = [e for e in events if e[0] == "skill"]
    assert len(skill_events) == 1 and skill_events[0][2]["skill"] == "planning-tests" and skill_events[0][2]["version"] == "1.4.0"
    assert "planning-tests" in skill_events[0][1]
    with db() as con:
        row = rows(con.execute("SELECT * FROM agent_calls WHERE agent='principal-test-architect' ORDER BY id DESC LIMIT 1"))[0]
    used = json.loads(row["skills"])
    assert used == [{"name": "planning-tests", "version": "1.4.0", "sha256": skill_lib.get("planning-tests").sha256, "refs": ["LEVEL_GUIDELINES.md"]}]
    assert row["prompt_ref"] == call.prompt_ref and "+skills:" in row["prompt_ref"] and call.prompt_ref.startswith(governance.prompts.ref("principal-test-architect"))

    # a changed skill changes the reference, so a stored document version says which skill text made it
    changed = {**skill_lib.load(), "planning-tests": dataclasses.replace(skill_lib.get("planning-tests"), body=skill_lib.get("planning-tests").body + "\nAlso do this.")}
    monkeypatch.setitem(skill_lib._state, "skills", changed)
    other = agents.AgentCall(None, project["id"], "principal-test-architect")
    assert other.prompt_ref != call.prompt_ref and other.prompt_ref.split("+skills:")[0] == call.prompt_ref.split("+skills:")[0]
    assert agents.AgentCall(None, project["id"], "principal-test-architect", skills=()).prompt_ref == governance.prompts.ref("principal-test-architect"), "no skill sent, no suffix"


# ---- chat: one small pick per user message, never a failed chat ---------------------

def chat_body(thread, text="Plan the tests for the calculator", message_id="m1"):
    return {"threadId": thread["id"], "runId": "r1", "messages": [{"id": message_id, "role": "user", "content": text}], "state": {}, "tools": [], "context": [], "forwardedProps": {}}


def chat(client, project, rules, text="Plan the tests for the calculator", message_id="m1"):
    scripted = ScriptedClient(rules)
    llm.set_client_override(scripted)
    thread = client.post(f"/api/projects/{project['id']}/chats", json={"agent": "principal-test-architect"}).json()
    with client.stream("POST", "/agui/principal-test-architect", json=chat_body(thread, text, message_id)) as response:
        body = "".join(response.iter_text())
    return scripted, thread, body


def test_chat_picks_a_skill_once_and_adds_it_to_the_turn(client, project):
    scripted, thread, body = chat(client, project, [("You decide which skill", '{"skill": "planning-tests"}'), (ARCHITECT, "Here is a plan"), ("Plan", "x")], message_id=unique("m"))
    assert "Here is a plan" in body and "RUN_FINISHED" in body
    picks = [c for c in scripted.calls if "You decide which skill" in c]
    answers = [c for c in scripted.calls if "You decide which skill" not in c]
    assert len(picks) == 1 and "planning-tests: " in picks[0] and "authoring-user-stories" not in picks[0], "it sees only this agent's skills, by name and description"
    assert len(answers) == 1 and '<skill name="planning-tests"' in answers[0]
    saved = client.get(f"/api/chats/{thread['id']}").json()["messages"]
    assert [m["content"] for m in saved] == ["Plan the tests for the calculator", "Here is a plan"], "the skill text is not stored in the thread"
    with db() as con:
        spent = rows(con.execute("SELECT tokens_in, tokens_out FROM agent_calls WHERE source='chat-skill' ORDER BY id DESC LIMIT 1"))
    assert spent and spent[0]["tokens_in"] + spent[0]["tokens_out"] > 0, "the pick counts as tokens for the user"


@pytest.mark.parametrize("pick_reply", ["I cannot decide.", '{"skill": "healing-tests"}', '{"skill": "none"}', RuntimeError("model down")])
def test_a_failed_pick_leaves_chat_working_without_a_skill(client, project, pick_reply):
    def reply(_text):
        if isinstance(pick_reply, Exception):
            raise pick_reply
        return pick_reply

    scripted, _thread, body = chat(client, project, [("You decide which skill", reply), (ARCHITECT, "Plain answer")], message_id=unique("m"))
    assert "Plain answer" in body and "RUN_FINISHED" in body and "RUN_ERROR" not in body
    assert not any("<skill name=" in c for c in scripted.calls)


def test_the_pick_is_asked_once_for_the_same_message(client, project):
    scripted = ScriptedClient([("You decide which skill", '{"skill": "planning-tests"}')])
    llm.set_client_override(scripted)
    key = ("thr_once", unique("m"))
    first = client.portal.call(lambda: skill_chat.pick("principal-test-architect", project["id"], None, "", "Plan the tests", key=key))
    again = client.portal.call(lambda: skill_chat.pick("principal-test-architect", project["id"], None, "", "Plan the tests", key=key))
    assert first == again == ["planning-tests"] and len(scripted.calls) == 1
    assert client.portal.call(lambda: skill_chat.pick("project-copilot", project["id"], None, "", "anything")) == [] and len(scripted.calls) == 1, "an agent with no skills makes no call"


# ---- the live tool check -------------------------------------------------------------

KEY = "sk-test-secret-key-1234567890"


@pytest.fixture
def endpoint(monkeypatch):
    monkeypatch.setattr(llm, "current", lambda: {"base_url": "http://proxy.test/v1", "model": "", "api_key": KEY})
    models.add("tc-model", enabled=True)
    seen = []

    def serve(model_behavior):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            seen.append({"auth": request.headers["authorization"], **body})
            return model_behavior(body)

        return httpx.MockTransport(handler)

    return serve, seen


def called(name, call_id="call_1"):
    return httpx.Response(200, json={"choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": None, "tool_calls": [{"id": call_id, "type": "function", "function": {"name": name, "arguments": "{}"}}]}}]})


def said(text, finish="stop"):
    return httpx.Response(200, json={"choices": [{"finish_reason": finish, "message": {"role": "assistant", "content": text}}]})


def tool_name(body):
    return body["tools"][0]["function"]["name"]


def good_model(body):
    if body["messages"][-1]["role"] == "tool":
        return said("The code is " + json.loads(body["messages"][-1]["content"])["reference"])
    return called(tool_name(body))


def check(client, transport):
    return client.portal.call(lambda: llm.tool_check("tc-model", transport=transport))


def test_tool_check_passes_a_model_that_calls_the_tool_and_uses_its_result(client, endpoint):
    serve, seen = endpoint
    result = check(client, serve(good_model))
    assert result["status"] == "passed" and result["tools_called"] == [tool_name(seen[0])] and result["max_tokens"] == llm.TOOL_CHECK_MAX_TOKENS
    assert len(seen) == 2 and all(r["max_tokens"] == llm.TOOL_CHECK_MAX_TOKENS and len(r["tools"]) == 1 for r in seen)
    assert tool_name(seen[0]).startswith("aqe_probe_") and seen[0]["messages"][0]["content"].count(tool_name(seen[0])) == 1
    token = json.loads(seen[1]["messages"][-1]["content"])["reference"]
    assert token.startswith("AQE-") and token not in json.dumps(seen[0]), "the unique token appears only in the tool's reply"
    stored = models.get("tc-model")
    assert stored["tools_status"] == "passed" and stored["tools_checked_at"] and stored["tools_max_tokens"] == llm.TOOL_CHECK_MAX_TOKENS
    other = check(client, serve(good_model))
    assert tool_name(seen[0]) != tool_name(seen[2]), "names are unique per check"
    assert KEY not in json.dumps([result, other, stored])


@pytest.mark.parametrize("name,behavior,reason", [
    ("a tool that was never offered", lambda body: called("read_file"), "read_file"),
    ("an answer in text", lambda body: said("I only have read_file."), "It said: I only have read_file."),
    ("nothing at all", lambda body: said("", "length"), "returned nothing"),
    ("the result ignored", lambda body: said("All done.") if body["messages"][-1]["role"] == "tool" else called(tool_name(body)), "ignored its result"),
    ("an empty final reply", lambda body: said("", "length") if body["messages"][-1]["role"] == "tool" else called(tool_name(body)), "then returned nothing"),
])
def test_tool_check_fails_for_each_way_a_model_can_misbehave(client, endpoint, name, behavior, reason):
    serve, _seen = endpoint
    result = check(client, serve(behavior))
    assert result["status"] == "failed" and reason in result["reason"], name
    stored = models.get("tc-model")
    assert stored["tools_status"] == "failed" and reason in stored["tools_reason"]


def test_tool_check_never_reveals_the_key_even_when_the_endpoint_echoes_it(client, endpoint):
    serve, _seen = endpoint
    result = check(client, serve(lambda body: httpx.Response(400, text=f"bad request, header was Bearer {KEY} and key {KEY}")))
    assert result["status"] == "failed" and result["reason"].startswith("HTTP 400") and KEY not in json.dumps(result) and KEY not in json.dumps(models.get("tc-model"))
    unreachable = httpx.MockTransport(lambda request: (_ for _ in ()).throw(httpx.ConnectError(f"cannot connect with {KEY}")))
    with pytest.raises(Exception) as caught:
        check(client, unreachable)
    assert KEY not in str(caught.value)


def test_tool_check_api_is_admin_only_and_shows_in_the_lists_and_health(client, endpoint, monkeypatch):
    serve, _seen = endpoint
    transport = serve(good_model)
    real = httpx.AsyncClient
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: real(**{**kw, "transport": transport}))
    outcome = client.post("/api/models/tool-check", json={"name": "tc-model"})
    assert outcome.status_code == 200 and outcome.json()["status"] == "passed" and KEY not in outcome.text
    assert client.post("/api/models/tool-check", json={"name": "not-listed"}).status_code == 404
    listed = {m["name"]: m for m in client.get("/api/models").json()}
    assert listed["tc-model"]["tools_status"] == "passed" and listed["tc-model"]["tools_checked_at"]
    assert client.get("/api/settings/models").json()["tools"]["tc-model"]["status"] == "passed"
    health = client.get("/api/health").json()
    assert health["skills"] == {"loaded": 11, "problems": 0} and health["tool_checks"]["passed"] >= 1 and set(health["tool_checks"]) == {"passed", "failed", "not_checked"}
    name = unique("tester")
    make_user(client, name, models=["tc-model"])
    other, _ = sign_in(name)
    assert other.post("/api/models/tool-check", json={"name": "tc-model"}).status_code == 403
    assert other.get("/api/settings/models").json()["tools"]["tc-model"]["status"] == "passed", "chat can warn about a failed check"


def test_a_model_that_passed_the_check_gets_skills_provider_in_chat_and_others_get_the_pick(client, project):
    llm.set_client_override(ScriptedClient([]))
    models.add("tp-model", enabled=True)
    assert skill_chat.mode("principal-test-architect", "tp-model") == "pick" and skill_chat.mode("project-copilot", "tp-model") == "none"
    models.set_tool_check("tp-model", False, "ignored the result", 2000)
    assert skill_chat.mode("principal-test-architect", "tp-model") == "pick"
    plain = agents.build("principal-test-architect", project["id"], chat=True, model="tp-model", source="chat")
    assert not any(isinstance(p, SkillsProvider) for p in plain.context_providers)
    models.set_tool_check("tp-model", True, "ok", 2000)
    assert skill_chat.mode("principal-test-architect", "tp-model") == "provider"
    smart = agents.build("principal-test-architect", project["id"], chat=True, model="tp-model", source="chat")
    provider = next(p for p in smart.context_providers if isinstance(p, SkillsProvider))
    offered = asyncio.run(provider._source.get_skills(SkillsSourceContext(agent=smart)))
    assert [s.frontmatter.name for s in offered] == ["planning-tests"], "only this agent's skills"
    workflow = agents.build("principal-test-architect", project["id"], model="tp-model")
    assert not any(isinstance(p, SkillsProvider) for p in workflow.context_providers), "workflows never rely on a tool to load a skill"


# ---- evals ------------------------------------------------------------------------------

def test_converted_checks_belong_to_real_plugin_cases():
    overlay = json.loads((ROOT / "evals/skills/checks.json").read_text(encoding="utf-8"))
    for name, queries in ((k, v) for k, v in overlay.items() if not k.startswith("_")):
        known = {case["query"] for case in skill_lib.eval_cases(name)}
        assert set(queries) <= known, f"{name} has checks for a query the plugin does not have"
        for rules in queries.values():
            assert evals.build_checks(rules), "a converted case has at least one real check"
    total = sum(len(skill_lib.eval_cases(n)) for n in skill_lib.names())
    converted = sum(len(q) for k, q in overlay.items() if not k.startswith("_"))
    assert total == 33 and converted == 5, "only what code can literally check was converted"


def test_skill_cases_run_with_their_skill_and_ungradable_ones_are_not_scored(client):
    scripted = ScriptedClient([("Plan tests for the approved requirements", "Unit tests for logic, Integration for services."), (ARCHITECT, '{"strategy": "x", "areas": [], "skipped_levels": {}}')])
    llm.set_client_override(scripted)
    result = client.post("/api/agents/principal-test-architect/evals").json()
    skill_results = [r for r in result["results"] if r["skill"] == "planning-tests"]
    assert [r["passed"] for r in skill_results] == [False, None, None], "the reply never says API, so the one coded case fails; the others are not scored"
    assert skill_results[0]["failed_checks"] == ["contains:API"] and skill_results[1]["status"] == "needs_grader" and skill_results[1]["expected_behavior"]
    assert skill_results[0]["ungraded_expectations"], "the plugin's sentences are kept and marked as not graded"
    assert result["needs_grader"] == 2 and result["total"] == len(result["results"]) - 2
    asked = [c for c in scripted.calls if "Plan tests for the approved requirements" in c]
    assert len(asked) == 1 and '<skill name="planning-tests"' in asked[0], "the case runs with its skill"
    assert not any("Plan tests but there are no approved requirements" in c for c in scripted.calls), "a case that needs a grader never calls the model"
    plain = [c for c in scripted.calls if "Plan tests for the approved requirements" not in c]
    assert plain and not any("<skill name=" in c for c in plain), "the original cases still measure the prompt alone"
    llm.set_client_override(ScriptedClient([("Plan tests for the approved requirements", "Unit, Integration and API levels"), (ARCHITECT, '{"strategy": "x", "areas": [], "skipped_levels": {}}')]))
    better = client.post("/api/agents/principal-test-architect/evals").json()
    assert [r["passed"] for r in better["results"] if r["skill"]] == [True, None, None]


def test_the_matches_rule_is_a_real_regex_check(client):
    document = "## Scope\n## Functional Requirements\nFR-001 Reset link valid for 30 minutes\n## Open Questions\n"
    feature = "Feature: Login\n\n  @FR-001 @FR-002\n  Scenario: Sign in\n    Given a member\n    When they sign in\n    Then they see home\n"
    llm.set_client_override(ScriptedClient([("Convert into a Gherkin feature", feature), ("Write the document", document), ("web calculator", "Given, When, Then, Exception, but no story in the required form")]))
    result = client.post("/api/agents/business-analyst/evals").json()
    skill_case = next(r for r in result["results"] if r["skill"] and r["passed"] is not None)
    assert skill_case["passed"] is False and any(name.startswith("matches:") for name in skill_case["failed_checks"])


# ---- the API and its access rule ----------------------------------------------------------

def test_skills_api_is_read_only_for_any_signed_in_account(client):
    listed = client.get("/api/skills").json()
    assert {s["name"] for s in listed["skills"]} == EXPECTED and listed["problems"] == []
    planning = next(s for s in listed["skills"] if s["name"] == "planning-tests")
    assert planning["agents"] == ["principal-test-architect"] and planning["references"] == ["LEVEL_GUIDELINES.md"] and planning["description"] and planning["version"] == "1.4.0"
    detail = client.get("/api/skills/planning-tests").json()
    assert detail["body"].startswith("# Planning Tests") and "LEVEL_GUIDELINES.md" in detail["reference_text"]
    assert client.get("/api/skills/nope").status_code == 404
    name = unique("reader")
    make_user(client, name)
    for role_account, kind in ((name, "developer"),):
        other, _ = sign_in(role_account)
        assert other.get("/api/skills").status_code == 200 and other.get("/api/skills/planning-tests").status_code == 200
        assert other.post("/api/skills", json={}).status_code == 405 and other.delete("/api/skills/planning-tests").status_code == 405, kind
    from fastapi.testclient import TestClient

    from backend.app import app

    assert TestClient(app).get("/api/skills").status_code == 401
    viewer = {"id": "usr_v", "role": "user", "account_role": "viewer"}
    assert auth.rule_of("/api/skills") == "session" and auth.rule_of("/api/skills/planning-tests") == "session"
    assert auth.access_problem("GET", "/api/skills/planning-tests", viewer) is None


# ---- the Azure package -----------------------------------------------------------------------

def test_the_backend_package_holds_skills_that_load_from_the_configured_folder(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("package_azure", ROOT / "scripts/package_azure.py")
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    entries = package.backend_entries()
    for needed in ("skills/planning-tests/SKILL.md", "skills/planning-tests/references/LEVEL_GUIDELINES.md", "skills/generating-test-code/assets/playwright.config.ts", "skills/healing-tests/evals/evals.json"):
        assert needed in entries, f"{needed} is not in the backend ZIP"
    assert {n.split("/")[1] for n in entries if n.startswith("skills/") and n.endswith("/SKILL.md")} == EXPECTED
    archive = tmp_path / "backend.zip"
    with zipfile.ZipFile(archive, "w") as bundle:  # the same entries the script writes
        for name, source in entries.items():
            bundle.write(source, name)
    unpacked = tmp_path / "unpacked"
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(unpacked)
    env = {**os.environ, "ATLAS_DATA_DIR": str(tmp_path / "data"), "ATLAS_SKILLS_DIR": str(unpacked / "skills"), "PYTHONPATH": str(unpacked / "src")}
    code = "from backend.core import skills\nprint(len(skills.load()), len(skills.problems()), skills.get('planning-tests').version)"
    out = subprocess.run([sys.executable, "-c", code], env=env, cwd=unpacked, capture_output=True, text=True, timeout=120)
    assert out.stdout.split()[-3:] == ["11", "0", "1.4.0"], out.stderr[-500:]
