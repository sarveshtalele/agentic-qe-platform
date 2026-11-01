"""Per-case confidence (qe/confidence.py), the QE review and send-back rounds, the human reason for REJECT items, and gate reopening. Only the model is scripted."""
import json

import pytest

from backend.core import documents, gates, ledger
from backend.maf import llm
from backend.qe import confidence
from tests import reviewing
from tests.scripted_client import ScriptedClient
from tests.test_api_workflows import CASES, PLAN, REQUIREMENTS, TESTS, client, pending, project, upload_repo, wait_run  # noqa: F401 - fixtures

CALC = "def add(a, b):\n    return a + b\n"


def design_item(**change):
    item = {"tc_id": "C1", "component": {"file": "calc.py", "line": 2, "symbol": "add"}, "scores": dict(reviewing.PERFECT["design"]), "total": 100, "verdict": "APPROVED", "flaws": []}
    return {**item, **change}


def code_item(**change):
    item = {"tc_id": "TC-1", "file": "calc.py", "scores": dict(reviewing.PERFECT["code"]), "total": 100, "verdict": "APPROVED", "flaws": []}
    return {**item, **change}


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "calc.py").write_text(CALC, encoding="utf-8")
    return tmp_path


# unit tests of the rubric, one per rule of the source


def test_each_rubric_sums_to_100_and_the_thresholds_are_the_plugins():
    assert {kind: sum(rubric.values()) for kind, rubric in confidence.RUBRIC.items()} == {"design": 100, "code": 100, "plan": 100}
    assert confidence.RUBRIC["design"] == {"source_proven": 30, "correct_target": 25, "expected_derivable": 25, "fixture_validity": 20}
    assert confidence.RUBRIC["code"] == {"compilable": 30, "assertion_integrity": 30, "import_safety": 20, "traceability_present": 20}
    assert confidence.RUBRIC["plan"] == {"controls_covered": 40, "level_fit": 30, "scenarios_derivable": 30}
    assert (confidence.THRESHOLD, confidence.ASSERTION_FLOOR) == (70, 20)


@pytest.mark.parametrize("total,verdict", [(100, "APPROVED"), (99, "REVISE"), (70, "REVISE"), (69, "REJECT"), (0, "REJECT")])
def test_verdict_is_decided_by_code_from_the_total(total, verdict):
    assert confidence.verdict_for(total) == verdict


def test_a_perfect_verified_case_is_approved(repo):
    record = confidence.check_item(design_item(), "design", repo)
    assert (record["total"], record["verdict"], record["evidence"], record["low"], record["problems"]) == (100, "APPROVED", "verified", False, [])


def test_the_total_is_the_sum_of_the_scores_not_the_models_number(repo):
    item = design_item(scores={"source_proven": 20, "correct_target": 25, "expected_derivable": 25, "fixture_validity": 20}, total=100, flaws=[{"dimension": "source_proven", "evidence": "calc.py:2", "fix": "Cite it"}])
    record = confidence.check_item(item, "design", repo)
    assert record["total"] == 90 and record["claimed_total"] == 100
    assert any("does not equal the sum" in p for p in record["problems"])


def test_an_invented_verdict_is_recomputed(repo):
    item = design_item(scores={"source_proven": 10, "correct_target": 25, "expected_derivable": 25, "fixture_validity": 20}, total=80, verdict="APPROVED", flaws=[{"dimension": "source_proven", "evidence": "calc.py:2", "fix": "Cite it"}])
    record = confidence.check_item(item, "design", repo)
    assert record["verdict"] == "REVISE" and record["scored_verdict"] == "REVISE"
    assert any("verdict APPROVED does not follow the rule" in p for p in record["problems"])


@pytest.mark.parametrize("scores,fragment", [
    ({"source_proven": 31, "correct_target": 25, "expected_derivable": 25, "fixture_validity": 20}, "source_proven must be a whole number from 0 to 30"),
    ({"source_proven": 29.5, "correct_target": 25, "expected_derivable": 25, "fixture_validity": 20}, "source_proven must be a whole number"),
    ({"source_proven": -1, "correct_target": 25, "expected_derivable": 25, "fixture_validity": 20}, "source_proven must be a whole number"),
    ({"source_proven": 30, "correct_target": 25, "expected_derivable": 25}, "fixture_validity must be a whole number"),
    ({"source_proven": 30, "correct_target": 25, "expected_derivable": 25, "fixture_validity": 20, "style": 5}, "unknown dimension style"),
])
def test_scores_must_be_whole_numbers_in_range_and_known(repo, scores, fragment):
    record = confidence.check_item(design_item(scores=scores, flaws=[{"dimension": "x", "evidence": "calc.py:2", "fix": "y"}]), "design", repo)
    assert any(fragment in p for p in record["problems"]), record["problems"]


def test_a_score_below_100_needs_flaws_with_path_line_evidence_and_a_fix(repo):
    scores = {"source_proven": 20, "correct_target": 25, "expected_derivable": 25, "fixture_validity": 20}
    none = confidence.check_item(design_item(scores=scores, total=90, verdict="REVISE"), "design", repo)
    assert any("must name each flaw" in p for p in none["problems"])
    vague = confidence.check_item(design_item(scores=scores, total=90, verdict="REVISE", flaws=[{"dimension": "source_proven", "evidence": "somewhere in calc", "fix": ""}]), "design", repo)
    assert any("needs evidence as path:line and a fix" in p for p in vague["problems"])
    good = confidence.check_item(design_item(scores=scores, total=90, verdict="REVISE", flaws=[{"dimension": "source_proven", "evidence": "calc.py:2", "fix": "Cite the return line"}]), "design", repo)
    assert good["problems"] == [] and good["flaws"][0]["file"] == "calc.py" and good["flaws"][0]["line"] == 2


def test_a_missing_citation_is_a_reject_however_high_the_score(repo):
    record = confidence.check_item(design_item(component={"file": "invented.py", "line": 4, "symbol": "ghost"}), "design", repo)
    assert record["total"] == 100 and record["evidence"] == "missing" and record["verdict"] == "REJECT" and record["low"]
    assert "invented.py:4" in record["problems"][-1]


def test_a_flaw_citation_that_is_not_on_disk_is_a_reject(repo):
    scores = {"source_proven": 20, "correct_target": 25, "expected_derivable": 25, "fixture_validity": 20}
    record = confidence.check_item(design_item(scores=scores, total=90, verdict="REVISE", flaws=[{"dimension": "source_proven", "evidence": "gone.py:1", "fix": "x"}]), "design", repo)
    assert record["evidence"] == "missing" and record["verdict"] == "REJECT"


@pytest.mark.parametrize("path", ["../outside.py", "/etc/passwd", "sub/../../outside.py"])
def test_a_path_outside_the_repository_is_a_reject(repo, tmp_path, path):
    (tmp_path.parent / "outside.py").write_text("x = 1\n", encoding="utf-8")
    record = confidence.check_item(design_item(component={"file": path, "line": 1, "symbol": "x"}), "design", repo)
    assert record["evidence"] == "missing" and record["verdict"] == "REJECT"
    assert "outside the repository" in record["problems"][-1]


def test_a_symlink_that_leaves_the_repository_is_a_reject(repo, tmp_path):
    outside = tmp_path.parent / "secret_target.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    try:
        (repo / "link.py").symlink_to(outside)
    except OSError:
        pytest.skip("this system cannot make symlinks")
    assert confidence.check_item(design_item(component={"file": "link.py", "line": 1, "symbol": "x"}), "design", repo)["verdict"] == "REJECT"


def test_a_line_beyond_the_end_of_the_file_is_a_reject(repo):
    assert confidence.check_item(design_item(component={"file": "calc.py", "line": 2, "symbol": "add"}), "design", repo)["evidence"] == "verified"
    for line in (3, 99):
        record = confidence.check_item(design_item(component={"file": "calc.py", "line": line, "symbol": "add"}), "design", repo)
        assert record["evidence"] == "missing" and record["verdict"] == "REJECT", line
    assert confidence.check_item(design_item(component={"file": "calc.py", "line": 0, "symbol": "add"}), "design", repo)["verdict"] == "REJECT"


def test_a_file_over_5_mb_does_not_count(repo):
    (repo / "huge.py").write_bytes(b"x = 1\n" * 1_000_000)
    assert (repo / "huge.py").stat().st_size > confidence.MAX_FILE_BYTES
    assert confidence.check_item(design_item(component={"file": "huge.py", "line": 1, "symbol": "x"}), "design", repo)["verdict"] == "REJECT"


def test_a_design_case_without_its_component_is_a_reject(repo):
    record = confidence.check_item(design_item(component=None), "design", repo)
    assert record["verdict"] == "REJECT" and any("component under test" in p for p in record["problems"])


def test_without_a_repository_the_evidence_is_not_checked_and_never_called_verified(tmp_path):
    record = confidence.check_item(design_item(), "design", tmp_path / "does-not-exist")
    assert record["evidence"] == "not-checked" and record["verdict"] == "APPROVED"
    assert confidence.check_item(design_item(), "design", None)["evidence"] == "not-checked"


def test_not_strict_reports_not_checked_for_a_missing_citation(repo):
    record = confidence.check_item(design_item(component={"file": "invented.py", "line": 4, "symbol": "ghost"}), "design", repo, strict=False)
    assert record["evidence"] == "not-checked" and record["verdict"] == "APPROVED"


@pytest.mark.parametrize("assertion,low", [(30, False), (20, False), (19, True), (0, True)])
def test_weak_assertions_are_low_confidence_at_any_total(repo, assertion, low):
    scores = {"compilable": 30, "assertion_integrity": assertion, "import_safety": 20, "traceability_present": 20}
    total = sum(scores.values())
    flaws = [] if total == 100 else [{"dimension": "assertion_integrity", "evidence": "calc.py:2", "fix": "Assert the sum"}]
    record = confidence.check_item(code_item(scores=scores, total=total, verdict=confidence.verdict_for(total), flaws=flaws), "code", repo)
    assert record["low"] is low
    if assertion == 19:
        assert record["total"] == 89 and record["verdict"] == "REVISE" and "assertion integrity 19/30" in record["low_reason"]


def test_a_test_that_asserts_nothing_is_low_even_when_the_rest_is_perfect(repo):
    scores = {"compilable": 30, "assertion_integrity": 5, "import_safety": 20, "traceability_present": 20}
    record = confidence.check_item(code_item(scores=scores, total=75, verdict="REVISE", flaws=[{"dimension": "assertion_integrity", "evidence": "calc.py:1", "fix": "Assert the sum"}]), "code", repo)
    assert record["total"] == 75 and record["verdict"] == "REVISE" and record["low"] and "may pass without proving" in record["low_reason"]


def test_a_total_under_the_threshold_is_low(repo):
    scores = {"source_proven": 10, "correct_target": 25, "expected_derivable": 20, "fixture_validity": 10}
    record = confidence.check_item(design_item(scores=scores, total=65, verdict="REJECT", flaws=[{"dimension": "source_proven", "evidence": "calc.py:2", "fix": "x"}]), "design", repo)
    assert record["verdict"] == "REJECT" and record["low"]


def test_a_dimension_of_another_review_type_is_unknown(repo):
    assert confidence.check_item(design_item(scores={**reviewing.PERFECT["design"], "assertion_integrity": 0}), "design", repo)["problems"][0] == "unknown dimension assertion_integrity"


def test_a_code_record_without_its_test_file_is_a_reject(repo):
    assert confidence.check_item(code_item(file=""), "code", repo)["verdict"] == "REJECT"


def test_a_plan_record_uses_the_plan_dimensions(repo):
    record = confidence.check_item({"tc_id": "PLAN", "scores": dict(reviewing.PERFECT["plan"]), "total": 100, "verdict": "APPROVED"}, "plan", repo)
    assert record["total"] == 100 and record["verdict"] == "APPROVED" and record["evidence"] == "verified"


def test_check_doc_summarises_by_the_worst_rule_and_counts_what_did_not_run(repo):
    review = {"items": [design_item(tc_id="A"), design_item(tc_id="B", component={"file": "gone.py", "line": 1, "symbol": "x"})]}
    done = confidence.check_doc(review, "design", repo)
    summary = done["summary"]
    assert summary["verdict"] == "REJECT" and summary["counts"]["reject"] == 1 and summary["counts"]["evidence_missing"] == 1 and summary["score"] == 100
    only_good = confidence.summarise([confidence.check_item(design_item(), "design", repo)])
    assert only_good["verdict"] == "APPROVED"
    with_gap = confidence.summarise([confidence.check_item(design_item(), "design", repo), confidence.not_run("X", "design", "reply broke")])
    assert with_gap["verdict"] == "REVISE" and with_gap["counts"]["not_run"] == 1, "a case that did not run can never leave the roll-up APPROVED"
    nothing = confidence.summarise([confidence.not_run("X", "design", "reply broke")])
    assert nothing["verdict"] == "NOT RUN" and nothing["score"] is None


def test_a_failed_test_is_capped_after_execution(repo):
    ok = confidence.check_item(code_item(tc_id="TC-1", scores={**reviewing.PERFECT["code"], "import_safety": 15}, total=95, verdict="REVISE", flaws=[{"dimension": "import_safety", "evidence": "calc.py:1", "fix": "x"}]), "code", repo)
    other = {**ok, "tc_id": "TC-2"}
    after = confidence.cap_failed([ok, other], {"TC-1": "failed", "TC-2": "passed"})
    first, second = after["records"]
    assert (first["total"], first["total_before"], first["capped"], first["verdict"], first["low"]) == (60, 95, True, "REJECT", True)
    assert (second["total"], second["capped"], second["verdict"]) == (95, False, "REVISE")
    assert (after["score_before"], after["score"], after["capped"], after["failed"], after["executed"]) == (95, 78, 1, 1, 2)
    assert confidence.cap_failed([ok], {"TC-1": "not run"})["capped"] == 0, "a test that did not run is not capped, it is simply not run"


def test_a_total_already_under_the_cap_is_not_raised(repo):
    low = confidence.check_item(code_item(scores={"compilable": 10, "assertion_integrity": 10, "import_safety": 10, "traceability_present": 10}, total=40, verdict="REJECT", flaws=[{"dimension": "compilable", "evidence": "calc.py:1", "fix": "x"}]), "code", repo)
    assert confidence.cap_failed([low], {"TC-1": "failed"})["records"][0]["total"] == 40


# integration: the QE workflow with a scripted reviewer


def base_rules(designer=CASES, grade=None, seen=None, extra=()):
    return [*extra, *reviewing.rules(grade, seen), ("You are a repository intelligence analyst", "## Purpose\nCalculator"), ("You are a requirements analyst", REQUIREMENTS),
            ("You are a principal test architect", PLAN), ("You are an independent reviewer", '{"score": 95, "verdict": "APPROVED", "issues": []}'),
            ("You are a test design architect", designer), ("You are a test automation engineer", TESTS)]


def go_to_gate(client, project, number, rules, approve_reason=""):
    upload_repo(client, project, {"calc.py": CALC, "conftest.py": ""})
    scripted = ScriptedClient(rules)
    llm.set_client_override(scripted)
    run = client.post(f"/api/projects/{project['id']}/runs", json={"workflow": "qe"}).json()
    for _ in range(7):
        run = wait_run(client, run["id"])
        assert run["status"] == "waiting_approval", run["error"]
        if pending(run)["gate"] == number:
            return run, scripted
        assert client.post(f"/api/approvals/{pending(run)['id']}/decide", json={"approved": True, "feedback": approve_reason}).status_code == 200
    raise AssertionError("gate not reached")


def test_a_rejected_case_goes_back_alone_with_its_flaws_and_the_others_are_untouched(client, project):
    seen, rewrites = [], []
    state = {"first": True}

    def grade(kind, key):
        if kind == "design" and key == "C2" and state["first"]:
            state["first"] = False
            return {"scores": {"source_proven": 5, "correct_target": 10, "expected_derivable": 10, "fixture_validity": 5}, "flaws": [{"dimension": "source_proven", "evidence": "calc.py:2", "fix": "Name the add function and assert 0 for add(-1, 1)"}]}
        return None

    def rewrite(text):
        rewrites.append(text)
        return json.dumps({"cases": [{"id": "x", "requirement_id": "REQ-001", "scenario": "Opposites cancel", "type": "Negative", "level": "Unit", "steps": ["call add(-1,1)"], "expected_result": "returns 0", "oracle": "derived"}]})

    run, scripted = go_to_gate(client, project, 3, base_rules(grade=grade, seen=seen, extra=[("Rewrite only this one test case", rewrite)]))
    assert len(rewrites) == 1, "only the rejected case is sent back"
    sent = rewrites[0].rsplit("Rewrite only this one test case", 1)[-1]
    assert "Negatives" in sent and "Name the add function and assert 0" in sent and "calc.py:2" in sent, "its flaw, evidence and fix go with it"
    assert all(other not in sent for other in ("Adds", "Zero", "Bad type")), "no other case is sent"
    first, second = [s for s in seen if s[0] == "design"]
    assert first[1] == ["C1", "C2", "C3", "C4"] and second[1] == ["C2"], "only the sent-back case is reviewed again"
    gate = pending(run)
    records = {r["tc_id"]: r for r in gate["payload"]["confidence"]["records"]}
    assert records["TC-APP-002"]["round"] == 2 and records["TC-APP-002"]["first_round"]["verdict"] == "REJECT" and records["TC-APP-002"]["verdict"] == "APPROVED"
    assert [records[i]["round"] for i in ("TC-APP-001", "TC-APP-003", "TC-APP-004")] == [1, 1, 1]
    doc = next(d for d in client.get(f"/api/projects/{project['id']}/documents").json() if d["kind"] == "test_cases")
    cases = {c["id"]: c for c in client.get(f"/api/documents/{doc['id']}").json()["data"]}
    assert cases["TC-APP-002"]["scenario"] == "Opposites cancel" and cases["TC-APP-001"]["scenario"] == "Adds" and cases["TC-APP-004"]["scenario"] == "Bad type"
    tokens = gate["payload"]["confidence"]["tokens"]
    assert tokens["revise"] > 0 and tokens["review"] > 0 and tokens["total"] == tokens["review"] + tokens["revise"], "real token use is reported"


def test_a_revise_is_not_sent_back_only_a_reject(client, project):
    seen, rewrites = [], []
    revise_only = lambda kind, key: {"scores": {"fixture_validity": 10}} if kind == "design" and key == "C2" else None
    run, _ = go_to_gate(client, project, 3, base_rules(grade=revise_only, seen=seen, extra=[("Rewrite only this one test case", lambda t: rewrites.append(t) or "x")]))
    assert rewrites == [] and len([s for s in seen if s[0] == "design"]) == 1
    records = {r["tc_id"]: r for r in pending(run)["payload"]["confidence"]["records"]}
    assert records["TC-APP-002"]["verdict"] == "REVISE" and records["TC-APP-002"]["total"] == 90


def test_only_one_round_and_a_case_that_stays_rejected_stays_visible(client, project):
    seen, rewrites = [], []

    def rewrite(text):
        rewrites.append(text)
        return json.dumps({"cases": [{"id": "x", "requirement_id": "REQ-001", "scenario": "Still weak", "type": "Negative", "level": "Unit", "steps": ["call add(-1,1)"], "expected_result": "returns 0", "oracle": "derived"}]})

    always = lambda kind, key: {"scores": {"source_proven": 5, "correct_target": 10, "expected_derivable": 10, "fixture_validity": 5}} if kind == "design" and key == "C2" else None
    run, _ = go_to_gate(client, project, 3, base_rules(grade=always, seen=seen, extra=[("Rewrite only this one test case", rewrite)]))
    assert len(rewrites) == 1 and len([s for s in seen if s[0] == "design"]) == 2, "one send-back and one second review, never a third"
    payload = pending(run)["payload"]["confidence"]
    stuck = next(r for r in payload["records"] if r["tc_id"] == "TC-APP-002")
    assert stuck["verdict"] == "REJECT" and stuck["round"] == 2 and stuck["first_round"]["verdict"] == "REJECT" and stuck["flaws"]
    assert payload["verdict"] == "REJECT" and payload["counts"]["reject"] == 1, "the roll-up shows it, nothing is hidden"


def test_approving_a_reject_needs_a_reason_that_reaches_the_ledger_and_a_revise_does_not(client, project):
    seen = []
    always = lambda kind, key: {"scores": {"source_proven": 5, "correct_target": 10, "expected_derivable": 10, "fixture_validity": 5}} if kind == "design" and key == "C2" else ({"scores": {"fixture_validity": 10}} if kind == "design" and key == "C3" else None)
    run, _ = go_to_gate(client, project, 3, base_rules(grade=always, seen=seen, extra=[("Rewrite only this one test case", lambda t: "I cannot")]))
    gate = pending(run)
    assert {r["tc_id"]: r["verdict"] for r in gate["payload"]["confidence"]["records"]}["TC-APP-003"] == "REVISE"
    for blank in ("", "   "):
        refused = client.post(f"/api/approvals/{gate['id']}/decide", json={"approved": True, "feedback": blank})
        assert refused.status_code == 400 and "TC-APP-002" in refused.text and "reason" in refused.text.lower()
    assert next(g for g in client.get(f"/api/projects/{project['id']}/gates").json() if g["gate"] == 3)["status"] == "pending"
    assert client.post(f"/api/approvals/{gate['id']}/decide", json={"approved": True, "feedback": "Boundary covered by TC-APP-003"}).status_code == 200
    entries = client.get(f"/api/projects/{project['id']}/ledger").json()
    accepted = next(e for e in entries["entries"] if e["action"] == "gate.reject_accepted")
    assert "Boundary covered by TC-APP-003" in accepted["data"] and "TC-APP-002" in accepted["data"] and accepted["target"] == "G3"
    assert entries["verification"]["valid"]


def test_a_gate_with_only_revise_items_needs_no_reason(client, project):
    revise = lambda kind, key: {"scores": {"fixture_validity": 10}} if kind == "design" else None
    run, _ = go_to_gate(client, project, 3, base_rules(grade=revise))
    assert client.post(f"/api/approvals/{pending(run)['id']}/decide", json={"approved": True}).status_code == 200


def test_a_review_batch_that_cannot_be_read_is_not_run_and_never_a_pass(client, project):
    run, _ = go_to_gate(client, project, 3, base_rules(extra=[("Review type: design cases.", "I think these cases look fine, 95 out of 100.")]))
    review = pending(run)["payload"]["confidence"]
    assert review["verdict"] == "NOT RUN" and review["score"] is None and review["counts"]["not_run"] == 4
    assert all(r["status"] == "NOT RUN" and r["total"] is None and r["verdict"] != "APPROVED" for r in review["records"])
    assert run["status"] == "waiting_approval", "the stage went on to its gate"
    assert client.post(f"/api/approvals/{pending(run)['id']}/decide", json={"approved": True}).status_code == 200, "NOT RUN is not a REJECT, so a person may go on"


def test_one_case_the_reviewer_skipped_is_not_run_and_the_roll_up_is_not_approved(client, project):
    skip = lambda kind, key: {"skip": True} if kind == "design" and key == "C3" else None
    run, _ = go_to_gate(client, project, 3, base_rules(grade=skip))
    review = pending(run)["payload"]["confidence"]
    by_id = {r["tc_id"]: r for r in review["records"]}
    assert by_id["TC-APP-003"]["status"] == "NOT RUN" and by_id["TC-APP-003"]["total"] is None
    assert review["verdict"] == "REVISE" and review["score"] == 100 and review["counts"]["not_run"] == 1


def test_an_invented_citation_makes_the_case_a_reject_on_the_gate(client, project):
    def invented(kind, key):
        if kind == "design" and key == "C1":
            return {"component": {"file": "ghost.py", "line": 9, "symbol": "ghost"}}
        return None

    run, _ = go_to_gate(client, project, 3, base_rules(grade=invented, extra=[("Rewrite only this one test case", lambda t: "I cannot")]))
    first = next(r for r in pending(run)["payload"]["confidence"]["records"] if r["tc_id"] == "TC-APP-001")
    assert first["total"] == 100 and first["verdict"] == "REJECT" and first["evidence"] == "missing"


def test_generated_tests_are_reviewed_per_file_and_a_failed_test_is_capped_after_execution(client, project):
    failing = json.loads(TESTS)
    failing["files"][1]["content"] = failing["files"][1]["content"].replace("== 0", "== 5")  # TC-APP-002 asserts a wrong value, so it fails when run
    ninety_five = lambda kind, key: {"scores": {"import_safety": 15}} if kind == "code" else None
    seen = []
    rules = base_rules(grade=ninety_five, seen=seen)
    rules = [r if r[0] != "You are a test automation engineer" else (r[0], json.dumps(failing)) for r in rules]
    run, _ = go_to_gate(client, project, 4, rules)
    review = pending(run)["payload"]["confidence"]
    assert [r["tc_id"] for r in review["records"]] == ["TC-APP-001", "TC-APP-002", "TC-APP-003", "TC-APP-004"] and review["score"] == 95
    assert [s for s in seen if s[0] == "code"][0][1] == ["TC-APP-001", "TC-APP-002", "TC-APP-003", "TC-APP-004"]
    assert all(r["file"].startswith("tests/agentic_qe/") and r["evidence"] == "verified" for r in review["records"])
    assert client.post(f"/api/approvals/{pending(run)['id']}/decide", json={"approved": True}).status_code == 200
    run = wait_run(client, run["id"])
    gate = pending(run)
    assert gate["gate"] == 5
    after = gate["payload"]["confidence"]
    by_id = {r["tc_id"]: r for r in after["records"]}
    assert (by_id["TC-APP-002"]["total"], by_id["TC-APP-002"]["total_before"], by_id["TC-APP-002"]["capped"]) == (60, 95, True)
    assert all(by_id[i]["total"] == 95 and not by_id[i]["capped"] for i in ("TC-APP-001", "TC-APP-003", "TC-APP-004"))
    assert after["score_before"] == 95 and after["score"] < 95 and after["capped"] == 1 and after["failed"] == 1
    assert run["state"]["tests_review"]["score"] == 95, "the review made before execution is kept as it was"
    assert run["state"]["tests_review_after"]["capped"] == 1
    refused = client.post(f"/api/approvals/{gate['id']}/decide", json={"approved": True})
    assert refused.status_code == 400 and "TC-APP-002" in refused.text, "a failed test is a REJECT item, so signing the release needs a reason"
    assert client.post(f"/api/approvals/{gate['id']}/decide", json={"approved": True, "feedback": "Known defect, tracked"}).status_code == 200


def test_a_rejected_test_file_goes_back_alone_and_is_rewritten_on_the_branch(client, project):
    state = {"first": True}

    def grade(kind, key):
        if kind == "code" and key == "TC-APP-003" and state["first"]:
            state["first"] = False
            return {"scores": {"assertion_integrity": 0, "compilable": 10, "import_safety": 10, "traceability_present": 10}, "flaws": [{"dimension": "assertion_integrity", "evidence": "tests/agentic_qe/test_tc_app_003.py:5", "fix": "Assert the sum"}]}
        return None

    rewrites = []
    better = json.loads(TESTS)["files"][2]
    better["content"] = better["content"].replace("assert add(0, 0) == 0", "assert add(0, 0) + 1 == 1")

    def rewrite(text):
        rewrites.append(text)
        return json.dumps({"framework": "pytest", "files": [better]})

    run, _ = go_to_gate(client, project, 4, base_rules(grade=grade, extra=[("Rewrite only this generated test file", rewrite)]))
    assert len(rewrites) == 1 and "test_tc_app_003.py" in rewrites[0] and "Assert the sum" in rewrites[0]
    sent = rewrites[0].rsplit("Rewrite only this generated test file", 1)[-1]
    assert "TC-APP-001" not in sent and "TC-APP-004" not in sent, "no other case is sent"
    record = next(r for r in pending(run)["payload"]["confidence"]["records"] if r["tc_id"] == "TC-APP-003")
    assert record["round"] == 2 and record["verdict"] == "APPROVED"
    from backend.config import project_dir

    written = next((project_dir(project["id"]) / "worktrees").glob("*/tests/agentic_qe/test_tc_app_003.py")).read_text(encoding="utf-8")
    assert "+ 1 == 1" in written


# gate reopening


def approve_all_gates(project_id):
    for number in range(6):
        gates.decide(project_id, number, True, "usr_qa", "agreed")


def test_editing_approved_requirements_reopens_g1_to_g5_and_the_ledger_still_verifies(client, project):
    pid = project["id"]
    req = documents.create(pid, "requirements", "Requirements", "| ID |\n|---|\n| REQ-001 |", "usr_qa")
    plan = documents.create(pid, "test_plan", "Plan", "plan", "usr_qa")
    approve_all_gates(pid)
    assert [g["status"] for g in gates.status(pid)] == ["approved"] * 6
    page = client.get(f"/api/documents/{req['id']}").json()
    assert page["would_reopen"] == [1, 2, 3, 4, 5], "the page can warn before saving"
    saved = client.put(f"/api/documents/{req['id']}", json={"content": "| ID |\n|---|\n| REQ-001 |\n| REQ-002 |", "note": "Added"})
    assert saved.status_code == 200 and saved.json()["reopened"] == [1, 2, 3, 4, 5]
    after = gates.status(pid)
    assert after[0]["status"] == "approved" and all(g["status"] == "pending" and g["decided_by"] is None for g in after[1:])
    reopened = [e for e in ledger.entries(pid) if e["action"] == "gate.reopened"]
    assert sorted(e["target"] for e in reopened) == ["G1", "G2", "G3", "G4", "G5"]
    detail = json.loads(next(e for e in reopened if e["target"] == "G1")["data"])
    assert detail["cause"].startswith("requirements edited") and detail["document"] == req["id"] and detail["was"] == "approved" and detail["decided_by"] == "usr_qa" and detail["signature"]
    assert ledger.verify(pid)["valid"] is True
    assert client.get(f"/api/documents/{plan['id']}").json()["would_reopen"] == [], "nothing is approved now, so nothing would reopen"


def test_a_later_gate_cannot_be_approved_while_an_earlier_one_is_open(client, project):
    pid = project["id"]
    req = documents.create(pid, "requirements", "Requirements", "one", "usr_qa")
    approve_all_gates(pid)
    documents.save_version(req["id"], "two", "usr_qa")
    with pytest.raises(gates.GateOrderError, match="Gate 1 must be approved before gate 2"):
        gates.decide(pid, 2, True, "usr_qa", "again")
    assert client.post(f"/api/projects/{pid}/gates/2/decision", json={"approved": True}).status_code == 400
    gates.decide(pid, 1, True, "usr_qa", "re-approved")
    gates.decide(pid, 2, True, "usr_qa", "re-approved")
    assert [g["status"] for g in gates.status(pid)][:3] == ["approved"] * 3 and ledger.verify(pid)["valid"] is True


def test_a_run_waiting_on_a_reopened_gate_cannot_be_approved_past_it(client, project):
    run, _ = go_to_gate(client, project, 2, base_rules())
    req = next(d for d in client.get(f"/api/projects/{project['id']}/documents").json() if d["kind"] == "requirements")
    saved = client.put(f"/api/documents/{req['id']}", json={"content": "# Changed\n\nREQ-001 now differs", "note": "Edited"}).json()
    assert saved["reopened"] == [1]
    refused = client.post(f"/api/approvals/{pending(run)['id']}/decide", json={"approved": True})
    assert refused.status_code == 400 and "Gate 1 must be approved before gate 2" in refused.text
    assert client.get(f"/api/runs/{run['id']}").json()["status"] == "waiting_approval", "the run stays waiting, honestly"
    assert client.post(f"/api/projects/{project['id']}/gates/1/decision", json={"approved": True, "reason": "Edit reviewed"}).status_code == 200
    assert client.post(f"/api/approvals/{pending(run)['id']}/decide", json={"approved": True}).status_code == 200


def test_restoring_an_old_version_also_reopens_but_a_first_version_and_a_draft_do_not(client, project):
    pid = project["id"]
    created = documents.create(pid, "requirements", "Requirements", "v1", "usr_qa")
    assert created["reopened"] == [], "a new document is not an edit"
    for number in range(6):
        gates.decide(pid, number, True, "usr_qa", "ok")
    documents.save_version(created["id"], "v2", "usr_qa")
    assert [g["status"] for g in gates.status(pid)][1:] == ["pending"] * 5
    for number in range(1, 6):
        gates.decide(pid, number, True, "usr_qa", "ok")
    restored = client.post(f"/api/documents/{created['id']}/restore/1")
    assert restored.status_code == 200 and restored.json()["reopened"] == [1, 2, 3, 4, 5]
    other = documents.create(pid, "brd", "Business doc", "x", "usr_qa")
    for number in range(1, 6):
        gates.decide(pid, number, True, "usr_qa", "ok")
    assert documents.save_version(other["id"], "y", "usr_qa")["reopened"] == [], "a document no gate rests on reopens nothing"
    assert documents.save_version(other["id"], "y", "usr_qa")["version"] == 2


def test_editing_a_document_whose_gate_is_not_approved_reopens_nothing(client, project):
    pid = project["id"]
    cases = documents.create(pid, "test_code", "Tests", "a", "usr_qa")
    gates.decide(pid, 0, True, "usr_qa", "ok")
    assert documents.save_version(cases["id"], "b", "usr_qa")["reopened"] == []
    assert gates.status(pid)[0]["status"] == "approved"


def test_nothing_approves_by_default(client, project):
    """A review that scores 100 on every item still leaves the gate pending until a named person decides."""
    run, _ = go_to_gate(client, project, 3, base_rules())
    assert pending(run)["payload"]["confidence"]["verdict"] == "APPROVED"
    assert next(g for g in client.get(f"/api/projects/{project['id']}/gates").json() if g["gate"] == 3)["status"] == "pending"
