"""Evaluation metrics (EVL): formulas, groundedness, mutation score with real pytest, the n/a table, the grader, RAGAS missing, storage, and the cards.
Only the model (ScriptedClient) is scripted. Mutation score runs the real pytest on a tiny real repository."""
import asyncio
import json
from pathlib import Path

import pytest
from agent_framework import Content, EvalItem, LocalEvaluator, Message

from backend.core import auth, prompts
from backend.db import db, rows
from backend.maf import evals, governance, llm
from backend.maf.evals import grader, metrics, ragas_evaluator, store
from tests.scripted_client import ScriptedClient
from tests.test_api_workflows import client, project  # noqa: F401 - fixtures
from tests.test_models import account

ROOT = Path(__file__).resolve().parent.parent
SHOP = ROOT / "evals" / "benchmarks" / "shop"


# ---- formulas, including division by zero ------------------------------------------------------

def test_formulas_on_known_inputs():
    assert metrics.precision(3, 1) == 0.75 and metrics.recall(3, 1) == 0.75
    assert metrics.f1(3, 1, 1) == pytest.approx(0.75) and metrics.f1(2, 2, 0) == pytest.approx(2 * 2 / (2 * 2 + 2))
    assert metrics.f1(1, 0, 0) == 1.0 and metrics.ratio(1, 4) == 0.25


def test_a_zero_denominator_has_no_value_never_0_or_1():
    assert metrics.precision(0, 0) is None and metrics.recall(0, 0) is None and metrics.f1(0, 0, 0) is None
    assert metrics.ratio(0, 0) is None
    assert metrics.precision(0, 3) == 0.0, "found things that were all wrong is a real zero"


def test_matching_is_one_to_one_and_reports_misses_and_extras():
    key = [{"file": "a.py", "line": 10, "tolerance": 1}, {"file": "a.py", "line": 20}, {"file": "b.py", "line": 5}]
    found = [{"file": "a.py", "line": 11}, {"file": "a.py", "line": 10}, {"file": "c.py", "line": 1}]
    got = metrics.match(found, key, metrics.at_location)
    assert (got["tp"], got["fp"], got["fn"]) == (1, 2, 2), "the second finding at line 10 cannot match the same key item again"
    assert got["precision"] == pytest.approx(1 / 3) and got["recall"] == pytest.approx(1 / 3)
    assert metrics.match([], [], metrics.at_location)["f1"] is None


def test_coverage_counts_labelled_facts_in_text_and_cannot_count_extras():
    got = metrics.coverage("Tax is 18 percent and shipping is free from 500.", [{"keywords": ["18"]}, {"keywords": ["500"]}, {"keywords": ["40"]}])
    assert (got["tp"], got["fn"], got["fp"]) == (2, 1, None) and got["recall"] == pytest.approx(2 / 3)
    assert got["precision"] is None and got["f1"] is None


# ---- groundedness -----------------------------------------------------------------------------------

@pytest.fixture
def repo(tmp_path):
    (tmp_path / "calc.py").write_text("def divide(a, b):\n    return a / b\n", encoding="utf-8")
    return tmp_path


def test_groundedness_checks_every_path_line_and_quote_on_disk(repo):
    reply = json.dumps({"findings": [
        {"file": "calc.py", "line": 2, "quote": "return a / b"},        # real
        {"file": "calc.py", "line": 9, "quote": "return a / b"},        # real quote, wrong line: the quote is found and the line corrected
        {"file": "calc.py", "line": 2, "quote": "return a // b"},       # invented quote
        {"file": "nope.py", "line": 1, "quote": "x = 1"},               # no such file
        {"file": "../outside.py", "line": 1, "quote": "x = 1"},         # escape
        {"file": "calc.py", "line": 50},                                # no such line
    ]})
    got = metrics.groundedness(reply, root=repo)
    assert got["n"] == 6 and got["value"] == pytest.approx(2 / 6)
    reasons = " | ".join(b["reason"] for b in got["bad"])
    assert "quote is not in calc.py" in reasons and "nope.py does not exist" in reasons and "outside" in reasons and "no line 50" in reasons


def test_groundedness_with_nothing_cited_has_no_value(repo):
    got = metrics.groundedness("This code is fine.", root=repo)
    assert got == {"value": None, "n": 0, "bad": []}


def test_groundedness_against_the_given_context_and_prose_citations(repo):
    context = "--- FILE a.py ---\n1: def f():\n2:     return 1\n"
    good = metrics.groundedness(json.dumps([{"file": "a.py", "line": 2, "quote": "return 1"}]), context=context)
    assert good["value"] == 1.0
    bad = metrics.groundedness(json.dumps([{"file": "b.py", "line": 1, "quote": "x"}, {"file": "a.py", "line": 1, "quote": "def g():"}]), context=context)
    assert bad["value"] == 0.0 and "not in the given context" in bad["bad"][0]["reason"]
    prose = metrics.groundedness("See calc.py:2 and calc.py:99 for the division.", root=repo)
    assert prose["n"] == 2 and prose["value"] == 0.5


def test_metric_checks_plug_into_maf_local_evaluator(repo):
    item = EvalItem(conversation=[Message(role="user", contents=[Content.from_text("q")]),
                                  Message(role="assistant", contents=[Content.from_text(json.dumps({"findings": [{"file": "calc.py", "line": 2, "quote": "return a / b"}]}))])])
    done = asyncio.run(LocalEvaluator(metrics.groundedness_check(root=repo)).evaluate([item]))
    assert done.items[0].scores[0].name == "groundedness" and done.items[0].scores[0].score == 1.0
    silent = EvalItem(conversation=[Message(role="user", contents=[Content.from_text("q")]), Message(role="assistant", contents=[Content.from_text("no citations")])])
    none = asyncio.run(LocalEvaluator(metrics.groundedness_check(root=repo)).evaluate([silent]))
    score = none.items[0].scores[0]
    assert score.passed is False and score.score == 0.0 and score.sample["reason"].startswith("Not measured"), "MAF checks are pass or fail, so the reason says it was not measured"


# ---- mutation score on a tiny real repository with real pytest -------------------------------------------

@pytest.fixture
def tiny(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\npythonpath = .\n", encoding="utf-8")
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a + b\n\n\ndef sign(n):\n    if n > 0:\n        return 1\n    return -1\n", encoding="utf-8")
    return tmp_path


MUTANTS = [{"id": "M-add", "file": "calc.py", "find": "return a + b", "replace": "return a - b"},
           {"id": "M-sign", "file": "calc.py", "find": "if n > 0:", "replace": "if n >= 0:"},
           {"id": "M-gone", "file": "calc.py", "find": "text that is not there", "replace": "x"}]


def test_mutation_score_counts_killed_and_surviving_bugs(tiny):
    tests = {"tests/test_calc.py": "from calc import add, sign\n\n\ndef test_add():\n    assert add(2, 3) == 5\n\n\ndef test_sign_positive():\n    assert sign(4) == 1\n"}
    got = metrics.mutation_score(tiny, tests, MUTANTS)
    status = {m["id"]: m["status"] for m in got["mutants"]}
    assert status == {"M-add": "killed", "M-sign": "survived", "M-gone": "not_applied"}, "sign(0) is never tested, so the >= mutant survives"
    assert got["verdict"] == "MEASURED" and got["score"] == 0.5 and got["killed"] == 1 and got["survived"] == 1 and got["not_applied"] == 1
    assert "return a + b" in (tiny / "calc.py").read_text(encoding="utf-8"), "the real repository is never touched"
    assert not (tiny / "tests").exists(), "generated tests are written only in the temporary copy"
    better = dict(tests, **{"tests/test_calc.py": tests["tests/test_calc.py"] + "\n\ndef test_sign_zero():\n    assert sign(0) == -1\n"})
    assert metrics.mutation_score(tiny, better, MUTANTS)["score"] == 1.0


def test_mutation_score_with_zero_executed_tests_is_inconclusive_with_no_number(tiny):
    empty = metrics.mutation_score(tiny, {"tests/test_none.py": "def helper():\n    return 1\n"}, MUTANTS)
    assert empty["verdict"] == "INCONCLUSIVE" and empty["score"] is None and "No test was executed" in empty["reason"] and empty["executed"] == 0
    failing = metrics.mutation_score(tiny, {"tests/test_bad.py": "def test_bad():\n    assert 1 == 2\n"}, MUTANTS)
    assert failing["verdict"] == "INCONCLUSIVE" and failing["score"] is None and "already fail" in failing["reason"]
    nothing_applies = metrics.mutation_score(tiny, {"tests/test_ok.py": "def test_ok():\n    assert True\n"}, [MUTANTS[2]])
    assert nothing_applies["verdict"] == "INCONCLUSIVE" and nothing_applies["score"] is None


# ---- the n/a table and the cards ---------------------------------------------------------------------------

def test_every_agent_is_in_the_applicability_table_and_na_has_no_number():
    assert set(store.METRICS_BY_AGENT) == set(governance.POLICIES)
    assert not store.applies("feature-engineer", "groundedness") and not store.applies("feature-engineer", "faithfulness")
    assert not store.applies("test-automation-engineer", "faithfulness") and store.applies("test-automation-engineer", "groundedness")
    assert all(store.applies(a, m) for a in store.METRICS_BY_AGENT for m in ("recall", "f1"))
    tile = store.tile("feature-engineer", "faithfulness")
    assert tile == {"metric": "faithfulness", "label": "Faithfulness", "state": "n/a"}
    assert "value" not in tile


def test_a_card_says_not_measured_until_something_ran():
    fresh = store.tile("confidence-reviewer", "recall")
    assert fresh["state"] in ("not_measured", "measured")
    if fresh["state"] == "not_measured":
        assert "Not measured" in fresh["reason"] and "value" not in fresh


def test_a_measured_row_needs_a_value_and_other_states_store_none():
    with pytest.raises(ValueError):
        store.record("bug-reviewer", "x@v1:aaa", "recall", status="measured")
    store.record("bug-reviewer", "x@v1:bbb", "faithfulness", value=0.9, status="failed", reason="the judge did not answer")
    with db() as con:
        stored = rows(con.execute("SELECT value, status FROM evaluation_metrics WHERE prompt_ref='x@v1:bbb'"))
    assert stored == [{"value": None, "status": "failed"}]


def test_scores_are_stored_and_trended_by_prompt_version():
    agent = "principal-test-architect"
    store.record(agent, "trend@v1:aaa", "recall", value=0.4, n=3, benchmark="shop", labels_reviewed=False)
    store.record(agent, "trend@v2:bbb", "recall", value=0.7, n=3, benchmark="shop", labels_reviewed=False)
    store.record(agent, "trend@v2:bbb", "recall", value=0.9, n=3, benchmark="shop", labels_reviewed=False)
    by = store.by_version(agent)
    assert by["trend@v1:aaa"]["recall"]["value"] == 0.4 and by["trend@v2:bbb"]["recall"] == {"value": pytest.approx(0.8), "runs": 2}
    points = {p["prompt_ref"]: p for t in store.detail(agent)["trend"] if t["metric"] == "recall" for p in t["points"]}
    assert points["trend@v2:bbb"]["min"] == 0.7 and points["trend@v2:bbb"]["max"] == 0.9 and points["trend@v2:bbb"]["runs"] == 2
    assert store.tile(agent, "recall")["labels"] == "not reviewed", "the tile warns while the labels are unchecked"


# ---- judge model and self grading --------------------------------------------------------------------------

def test_a_score_is_self_graded_unless_a_different_judge_is_set(monkeypatch):
    monkeypatch.delenv("ATLAS_EVAL_MODEL", raising=False)
    assert ragas_evaluator.self_graded("deepseek") is True
    monkeypatch.setenv("ATLAS_EVAL_MODEL", "deepseek")
    assert ragas_evaluator.self_graded("deepseek") is True
    monkeypatch.setenv("ATLAS_EVAL_MODEL", "kimi")
    assert ragas_evaluator.self_graded("deepseek") is False and ragas_evaluator.judge_model() == "kimi"


def test_ragas_missing_reads_not_measured_and_gives_no_number(monkeypatch, client):
    monkeypatch.setattr(ragas_evaluator, "installed", lambda: (False, ragas_evaluator.NOT_INSTALLED))
    done = asyncio.run(ragas_evaluator.RagasEvaluator("m").evaluate([EvalItem(conversation=[Message(role="user", contents=[Content.from_text("q")]), Message(role="assistant", contents=[Content.from_text("a")])], context="c")], eval_name="x"))
    assert done.status == "not_measured" and done.error == "Not measured: RAGAS is not installed" and not done.items
    llm.set_client_override(ScriptedClient([("Reverse-engineer the requirements", json.dumps({"requirements": [{"id": "R", "title": "t", "statement": "s", "file": "cart.py", "line": 25, "quote": "if discount_percent < 0 or discount_percent > 100:"}]}))]))
    result = asyncio.run(evals.run("requirements-analyst", benchmark="shop", ragas=True))
    with db() as con:
        faith = rows(con.execute("SELECT value, status, reason FROM evaluation_metrics WHERE eval_id=? AND metric='faithfulness'", (result["id"],)))
    assert faith == [{"value": None, "status": "not_measured", "reason": "Not measured: RAGAS is not installed"}]
    assert store.tile("requirements-analyst", "faithfulness")["state"] == "not_measured"


# ---- a benchmark run with known answers --------------------------------------------------------------------------

def finding(file, line, quote):
    return {"title": "t", "severity": "high", "file": file, "line": line, "quote": quote, "explanation": "e"}


BUG_REPLY = json.dumps({"findings": [
    finding("cart.py", 27, "discount = self.subtotal() * discount_percent / 10"),
    finding("inventory.py", 14, "if self.available(sku) < quantity - 1:"),
    finding("pricing.py", 10, "return round_money(amount * TAX_RATE_PERCENT // 100)"),
    finding("money.py", 6, "return float(Decimal(str(value)).quantize(Decimal(\"0.01\"), rounding=ROUND_HALF_UP))"),  # false alarm in a clean file
    finding("cart.py", 5, "this line does not exist"),                                                               # invented quote
]})


def test_benchmark_run_computes_precision_recall_f1_and_groundedness_from_the_key(client, monkeypatch):
    monkeypatch.delenv("ATLAS_EVAL_MODEL", raising=False)
    llm.set_client_override(ScriptedClient([("Review these files for real defects", BUG_REPLY)]))
    result = asyncio.run(evals.run("bug-reviewer", benchmark="shop", repeats=2))
    assert result["repeats"] == 2 and result["labels_reviewed"] is False and result["benchmark"] == "shop"
    case = result["results"][0]
    assert case["measured"]["key"]["tp"] == 3 and case["measured"]["key"]["fp"] == 2 and case["measured"]["key"]["fn"] == 2
    got = {t["metric"]: t for t in store.card("bug-reviewer")["tiles"]}
    assert got["recall"]["value"] == pytest.approx(0.6) and got["f1"]["value"] == pytest.approx(0.6)
    assert got["groundedness"]["value"] == pytest.approx(0.8) and got["groundedness"]["n"] == 5
    assert got["recall"]["labels"] == "not reviewed" and got["faithfulness"]["state"] == "not_measured", "no judge ran, so no number"
    spread = store.detail("bug-reviewer")["spread"]["recall"]
    assert spread["runs"] == 2 and spread["min"] == spread["max"] == pytest.approx(0.6)
    assert "does not exist" in case["reason"] or "not in" in case["reason"], "the reason names why a citation failed"


def test_cases_come_worst_first_with_question_context_answer_and_reason(client):
    llm.set_client_override(ScriptedClient([("Review these files for real defects", BUG_REPLY)]))
    asyncio.run(evals.run("bug-reviewer", benchmark="shop"))
    first = evals.cases_worst_first("bug-reviewer")[0]
    assert first["question"].startswith("Review these files") and "--- FILE cart.py ---" in first["context"] and "findings" in first["answer"] and first["reason"]
    assert "_item" not in first


def test_the_api_serves_cards_and_agent_metrics(client):
    cards = client.get("/api/evals/cards").json()
    assert set(cards["cards"]) == set(governance.POLICIES) and "shop" in cards["benchmarks"]
    assert [t["metric"] for t in cards["cards"]["bug-reviewer"]["tiles"]] == ["groundedness", "faithfulness", "recall", "f1"]
    assert cards["ragas"]["installed"] in (True, False) and cards["ragas"]["judge_model"] == ""
    detail = client.get("/api/agents/bug-reviewer/metrics").json()
    assert {m["metric"] for m in detail["metrics"]} >= {"groundedness", "mutation_score"} and "cases" in detail
    assert client.get("/api/agents/no-such/metrics").status_code == 404
    assert isinstance(client.get("/api/prompts/bug-reviewer/scores").json(), dict)
    assert client.post("/api/agents/bug-reviewer/evals", json={"benchmark": "nope"}).status_code == 404


def test_a_user_cannot_start_an_eval_and_an_admin_eval_is_not_theirs(client):
    user, mine, project = account(client)
    assert mine.post("/api/agents/bug-reviewer/evals", json={}).status_code == 403
    llm.set_client_override(ScriptedClient([("Review these files for real defects", BUG_REPLY)]))
    before = mine.get("/api/auth/me").json()["tokens_used"]
    with db() as con:
        last_id = con.execute("SELECT COALESCE(MAX(id),0) FROM agent_calls").fetchone()[0]

    async def as_admin():
        auth.current_user.set({"id": "admin", "role": "admin"})
        return await evals.run("bug-reviewer", benchmark="shop")

    asyncio.run(as_admin())
    with db() as con:
        owners = {r["user_id"] for r in rows(con.execute("SELECT user_id FROM agent_calls WHERE source='eval' AND id>?", (last_id,)))}
    assert owners == {"admin"} and mine.get("/api/auth/me").json()["tokens_used"] == before


# ---- live groundedness on a real reply ----------------------------------------------------------------------------

def live_count():
    with db() as con:
        return con.execute("SELECT COUNT(*) FROM evaluation_metrics WHERE source='live'").fetchone()[0]


def test_every_real_reply_records_free_groundedness_per_agent_call(client, project):
    from backend.config import repo_dir
    from backend.maf.runtime import AgentCall

    root = repo_dir(project["id"])
    root.mkdir(parents=True, exist_ok=True)
    (root / "calc.py").write_text("def divide(a, b):\n    return a / b\n", encoding="utf-8")
    reply = json.dumps({"findings": [finding("calc.py", 2, "return a / b"), finding("calc.py", 2, "return b / a")]})
    llm.set_client_override(ScriptedClient([("Review", reply)]))
    call = AgentCall(None, project["id"], "bug-reviewer", source="workflow")
    asyncio.run(call.text("Review calc.py"))
    with db() as con:
        live = rows(con.execute("SELECT value, n, source, agent_call_id, prompt_ref FROM evaluation_metrics WHERE source='live' AND agent='bug-reviewer' ORDER BY id DESC LIMIT 1"))[0]
        call_row = rows(con.execute("SELECT id FROM agent_calls WHERE project_id=? ORDER BY id DESC LIMIT 1", (project["id"],)))[0]
    assert live["value"] == 0.5 and live["n"] == 2 and live["agent_call_id"] == call_row["id"] and live["prompt_ref"] == prompts.ref("bug-reviewer")
    before = live_count()
    llm.set_client_override(ScriptedClient([("Review", "Nothing to report.")]))
    asyncio.run(AgentCall(None, project["id"], "bug-reviewer", source="workflow").text("Review calc.py"))
    assert live_count() == before, "a reply with no citations records nothing"


# ---- the grader for plugin skill cases -----------------------------------------------------------------------------

def test_grader_evidence_that_is_not_in_the_output_is_a_fail():
    output = "Unit tests cover the logic.   Integration tests cover the API."
    grades = [grader.Grade(expectation="a", verdict="PASS", evidence="unit tests cover the logic."),
              grader.Grade(expectation="b", verdict="PASS", evidence="Contract tests cover the service."),
              grader.Grade(expectation="c", verdict="PASS", evidence="")]
    got = grader.verify(output, ["a", "b", "c", "d"], grades)
    assert [g["verdict"] for g in got] == ["PASS", "FAIL", "FAIL", "FAIL"]
    assert got[1]["reason"] == "Evidence not found in the output" and got[2]["reason"] == "No evidence was quoted" and "no grade" in got[3]["reason"]


def judge_reply(evidence):
    def reply(text):
        block = text.split("EXPECTATIONS, in order:\n")[1].split("\n\nGive one grade")[0]
        listed = [line.split(". ", 1)[1] for line in block.splitlines()]
        return json.dumps({"grades": [{"expectation": e, "verdict": "PASS", "evidence": evidence, "reason": "r"} for e in listed]})
    return reply


def test_skill_cases_stay_needs_grader_without_a_judge_and_are_graded_with_one(client, monkeypatch):
    monkeypatch.delenv("ATLAS_EVAL_MODEL", raising=False)
    architect = "You are a principal test architect"
    agent_says = "Unit tests for the logic and Integration tests for the services."
    llm.set_client_override(ScriptedClient([("Plan tests", agent_says), (architect, '{"strategy": "x", "areas": [], "skipped_levels": {}}'), ("Save the test plan", agent_says)]))
    without = asyncio.run(evals._run_case("principal-test-architect", evals.skill_cases("principal-test-architect")[1]))
    assert without["passed"] is None and without["status"] == "needs_grader"
    monkeypatch.setenv("ATLAS_EVAL_MODEL", "judge-model")
    real = ScriptedClient([("You grade an AI agent's output", judge_reply("Unit tests for the logic")), ("Plan tests", agent_says), (architect, '{"strategy": "x", "areas": [], "skipped_levels": {}}')])
    llm.set_client_override(real)
    graded = asyncio.run(evals._run_case("principal-test-architect", evals.skill_cases("principal-test-architect")[1]))
    assert graded["passed"] is True and graded["status"] == "graded" and graded["judge_model"] == "judge-model" and graded["tokens"] > 0
    assert all(g["evidence"] for g in graded["grades"])
    llm.set_client_override(ScriptedClient([("You grade an AI agent's output", judge_reply("Words the agent never wrote")), ("Plan tests", agent_says), (architect, '{"strategy": "x", "areas": [], "skipped_levels": {}}')]))
    invented = asyncio.run(evals._run_case("principal-test-architect", evals.skill_cases("principal-test-architect")[1]))
    assert invented["passed"] is False and any("Evidence not found" in g["reason"] for g in invented["grades"])


# ---- benchmark labels ------------------------------------------------------------------------------------------------

def test_benchmark_labels_are_marked_unreviewed_and_point_at_real_lines():
    shop = json.loads((SHOP / "labels.json").read_text(encoding="utf-8"))
    finance = json.loads((ROOT / "evals" / "benchmarks" / "finance" / "labels.json").read_text(encoding="utf-8"))
    assert shop["reviewed"] is False and finance["reviewed"] is False
    assert len(finance["commit"]) == 40 and finance["bugs"] and finance["requirements"]
    planted = {"BUG-1": "/ 10", "BUG-2": "quantity - 1", "BUG-3": "// 100", "BUG-4": "amount > FREE_SHIPPING_FROM", "BUG-5": "inventory.reserve"}
    for bug in shop["bugs"]:
        lines = (SHOP / "repo" / bug["file"]).read_text(encoding="utf-8").splitlines()
        assert planted[bug["id"]] in lines[bug["line"] - 1], bug["id"]
    assert not {b["file"] for b in shop["bugs"]} & set(shop["clean_files"])
    for item in [*shop["requirements"], *finance["requirements"]]:
        assert item["tolerance"] >= 0 and item["line"] >= 1
    for agent in ("bug-reviewer", "requirements-analyst", "business-analyst", "test-automation-engineer"):
        assert evals.bench_cases(agent, "shop"), agent


def test_the_shop_tests_pass_so_a_mutation_baseline_is_valid():
    got = metrics.mutation_score(SHOP / "repo", {"tests/test_x.py": "from money import round_money\n\n\ndef test_round():\n    assert round_money(2.675) == 2.68\n"}, [{"id": "M", "file": "money.py", "find": "ROUND_HALF_UP)", "replace": "ROUND_DOWN)"}])
    assert got["verdict"] == "MEASURED" and got["score"] == 1.0

