"""Agent evals on MAF's evaluation API. Each case runs the real active prompt, so prompt versions can be compared."""
from __future__ import annotations

import asyncio
import json
import re

from pathlib import Path

from agent_framework import Content, EvalItem, LocalEvaluator, Message, evaluate_agent, evaluator
from pydantic import ValidationError

from backend.config import ROOT
from backend.core import gherkin, prompts
from backend.core import skills as skill_lib
from backend.core.errors import classify
from backend.core.security import redact
from backend.db import db, new_id, now, rows
from backend.maf import runtime as agents
from backend.maf.evals import grader, metrics, ragas_evaluator, store
from backend.qe import model

EVALS_DIR = ROOT / "evals"
EVAL_PROJECT = "prj_agent_evals"
BENCH_DIR = EVALS_DIR / "benchmarks"
KEY_METRICS = ("precision", "recall", "f1")
STORED_TEXT = 6000  # characters of context and answer kept per case


def _schemas() -> dict:
    from backend.maf import workflows

    return {"Review": workflows.Review, "ReviewFindings": workflows.ReviewFindings, "GeneratedSuite": workflows.GeneratedSuite, "RequirementSet": model.RequirementSet,
            "TestPlan": model.TestPlan, "CaseSet": model.CaseSet, "ConfidenceReview": model.ConfidenceReview}


def available() -> list[str]:
    return sorted(p.stem for p in EVALS_DIR.glob("*.json"))


def _sandbox() -> None:
    """Evals run in a hidden, archived project, so they cannot touch real project data."""
    with db() as con:
        con.execute("INSERT OR IGNORE INTO projects (id, name, description, created_at, updated_at, archived) VALUES (?,?,?,?,?,1)",
                    (EVAL_PROJECT, "Agent evals", "Isolated project for agent evaluations", now(), now()))


def build_checks(rules: dict) -> list:
    """Each rule becomes one MAF check. Failures name what was wrong."""
    checks = []

    def add(name, fn):
        checks.append(evaluator(fn, name=name))

    for word in rules.get("contains", []):
        add(f"contains:{word}", lambda response, w=word: w.lower() in response.lower())
    for word in rules.get("not_contains", []):
        add(f"not_contains:{word}", lambda response, w=word: w.lower() not in response.lower())
    for word in rules.get("not_only", []):
        add(f"not_only:{word}", lambda response, w=word: response.strip().strip(".").lower() != w.lower())
    for pattern in rules.get("matches", []):
        add(f"matches:{pattern}", lambda response, pat=pattern: re.search(pat, response) is not None)
    if rules.get("gherkin"):
        add("valid_gherkin", lambda response: gherkin.validate(_last_part(response))["valid"])
    if rules.get("json_schema"):
        schema = _schemas()[rules["json_schema"]]

        def valid(response: str) -> bool:
            try:
                schema.model_validate(agents.extract_json(response))
                return True
            except (ValueError, ValidationError):
                return False

        add(f"schema:{rules['json_schema']}", valid)
    if "max_score" in rules:
        add(f"score<={rules['max_score']}", lambda response: _score(response) <= rules["max_score"])
    if "min_score" in rules:
        add(f"score>={rules['min_score']}", lambda response: _score(response) >= rules["min_score"])
    return checks


def _last_part(response: str) -> str:
    text = response.strip().removeprefix("```gherkin").removeprefix("```").removesuffix("```").strip()
    start = next((i for i, line in enumerate(text.splitlines()) if line.lstrip().startswith(("Feature:", "@"))), 0)
    return "\n".join(text.splitlines()[start:])


def _score(response: str) -> int:
    try:
        return int(agents.extract_json(response).get("score", -1))
    except (ValueError, TypeError):
        return -1


def skill_cases(agent_key: str) -> list[dict]:
    """The plugin eval cases of this agent's skills. A case gets code checks only where `evals/skill-checks.json` has them for that exact query.

    The plugin's expectations are sentences for a human or grader. A case without code checks is listed as needing a grader and is neither passed nor failed.
    """
    overlay = json.loads((EVALS_DIR / "skills" / "checks.json").read_text(encoding="utf-8")) if (EVALS_DIR / "skills" / "checks.json").is_file() else {}
    cases = []
    for name in skill_lib.for_agent(agent_key):
        for number, plugin_case in enumerate(skill_lib.eval_cases(name), 1):
            checks = overlay.get(name, {}).get(plugin_case["query"])
            cases.append({"name": f"{name} #{number}", "category": "skill", "skill": name, "query": plugin_case["query"], "checks": checks,
                          "expected_behavior": plugin_case.get("expected_behavior", [])})
    return cases


def benchmarks() -> list[str]:
    return sorted(p.name for p in BENCH_DIR.iterdir() if (p / "labels.json").is_file()) if BENCH_DIR.is_dir() else []


def _labels(name: str) -> dict:
    return json.loads((BENCH_DIR / name / "labels.json").read_text(encoding="utf-8"))


def _numbered(base: Path, names: list[str]) -> str:
    """Files as the agents receive code: a FILE header and numbered lines."""
    return "\n".join(f"--- FILE {n} ---\n" + "\n".join(f"{i}: {line}" for i, line in enumerate((base / n).read_text(encoding="utf-8").splitlines(), 1)) for n in names)


def bench_cases(agent_key: str, name: str) -> list[dict]:
    """Cases of one benchmark for an agent, with their context built from the benchmark's own files."""
    path = BENCH_DIR / name / "cases" / f"{agent_key}.json"
    if not path.is_file():
        return []
    base = BENCH_DIR / name / "repo"
    cases = []
    for case in json.loads(path.read_text(encoding="utf-8")):
        context = case.get("context") or (_numbered(base, case["context_files"]) if case.get("context_files") else "")
        cases.append({**case, "context": context, "benchmark": name})
    return cases


def _find_items(answer: str, key: dict) -> list[dict]:
    found = agents.extract_json(answer)
    items = found.get(key.get("list", ""), []) if isinstance(found, dict) else found
    return [i if isinstance(i, dict) else {"text": str(i)} for i in items]


def _key_counts(answer: str, key: dict) -> dict:
    """Precision, recall, and F1 inputs for one case. A reply that is not JSON has every key item missed and nothing found."""
    if key.get("match") == "contains":
        return metrics.coverage(answer, key["items"])
    try:
        items = _find_items(answer, key)
    except (ValueError, AttributeError):
        items = []
    same = metrics.at_location if key.get("match") == "location" else metrics.has_keywords
    return metrics.match(items, key["items"], same)


async def _run_case(agent_key: str, case: dict) -> dict:
    case = {"checks": None, **case}
    if "skill" in case and not case["checks"]:  # nothing code can check: a judge grades it, and without one it stays unrun
        judge = ragas_evaluator.judge_model()
        if not judge or not case["expected_behavior"]:
            return {"name": case["name"], "category": "skill", "skill": case["skill"], "passed": None, "status": "needs_grader", "failed_checks": [], "expected_behavior": case["expected_behavior"]}
        return await _graded_skill_case(agent_key, case, judge)
    # existing cases measure the prompt alone, so they send no skill; a skill case sends exactly its skill
    call = agents.AgentCall(None, EVAL_PROJECT, agent_key, source="eval", skills=(case["skill"],) if "skill" in case else ())
    checks = case["checks"] or {}
    context = case.get("context", "")
    try:
        schema = _schemas().get(checks.get("json_schema"))
        message = case["query"] + (f"\nCODE:\n{context}" if case.get("context_files") else "")
        answer = await call.text(f"{message}\n\n{agents.format_rule(schema)}" if schema else message)
    except Exception as exc:  # a failing agent is an eval failure recorded in the result, not a crash of the whole suite
        error = classify(exc)
        return {"name": case["name"], "category": case.get("category", "quality"), "skill": case.get("skill", ""), "passed": False, "failed_checks": [f"error: {error.code} {error.message[:200]}"], "tokens": call.tokens}
    wanted = case.get("metrics", [])
    measured = {}
    if "groundedness" in wanted:
        measured["groundedness"] = metrics.groundedness(answer, context=context)
    if any(m in wanted for m in KEY_METRICS) and case.get("key"):
        measured["key"] = _key_counts(answer, case["key"])
    if case.get("mutation"):
        measured["mutation"] = _mutation(case, answer)
    evaluators = [LocalEvaluator(*build_checks(checks))] if checks else []
    outcome = await evaluate_agent(agent=call.agent, queries=[case["query"]], responses=[call.last_response], evaluators=evaluators or [LocalEvaluator(evaluator(lambda response: True, name="ran"))], eval_name=f"{agent_key}:{case['name']}")
    items = outcome[0].items or []
    failed = [s.name for item in items for s in item.scores if s.passed is False] if items else []
    counts = outcome[0].result_counts or {}
    passed = counts.get("failed", 0) == 0 and counts.get("errored", 0) == 0 and counts.get("passed", 0) > 0
    reasons = [f"failed {f}" for f in failed] + [c["reason"] for c in measured.get("groundedness", {}).get("bad", [])[:3]]
    result = {"name": case["name"], "category": case.get("category", "quality"), "skill": case.get("skill", ""), "passed": passed, "failed_checks": failed, "tokens": call.tokens, "model": call.model,
              "question": case["query"][:STORED_TEXT], "context": redact(context)[:STORED_TEXT], "answer": redact(answer)[:STORED_TEXT], "reference": case.get("reference", ""),
              "reason": "; ".join(reasons), "measured": measured, "wanted": wanted, "_item": (case["query"], answer, context, case.get("reference", ""))}
    if "skill" in case:  # only the code checks were scored; the plugin's sentences were not
        result["ungraded_expectations"] = case["expected_behavior"]
    return result


def _mutation(case: dict, answer: str) -> dict:
    """Generated tests run against the benchmark repository with each planted bug, in a temporary copy."""
    spec = case["mutation"]
    try:
        suite = _schemas()["GeneratedSuite"].model_validate(agents.extract_json(answer))
    except (ValueError, ValidationError) as exc:
        return {"verdict": "INCONCLUSIVE", "score": None, "reason": f"No usable tests in the reply: {str(exc)[:150]}", "killed": 0, "survived": 0, "not_applied": 0, "executed": 0, "mutants": []}
    return metrics.mutation_score(BENCH_DIR / case["benchmark"] / spec["repo"], {f.path: f.content for f in suite.files}, spec["mutants"], target=spec.get("target", "."))


async def _graded_skill_case(agent_key: str, case: dict, judge: str) -> dict:
    call = agents.AgentCall(None, EVAL_PROJECT, agent_key, source="eval", skills=(case["skill"],))
    base = {"name": case["name"], "category": "skill", "skill": case["skill"], "question": case["query"][:STORED_TEXT]}
    try:
        answer = await call.text(case["query"])
    except Exception as exc:
        error = classify(exc)
        return {**base, "passed": False, "failed_checks": [f"error: {error.code} {error.message[:200]}"], "tokens": call.tokens}
    graded = await grader.grade(case["query"], answer, case["expected_behavior"], judge=judge, agent_model=call.model)
    failed = [f"expectation: {g['expectation'][:120]} ({g['reason']})" for g in graded["grades"] if g["verdict"] != "PASS"]
    return {**base, "passed": graded["passed"], "status": "graded" if graded["passed"] is not None else "grader_failed", "failed_checks": failed + ([graded["error"]] if graded.get("error") else []),
            "answer": redact(answer)[:STORED_TEXT], "reason": "; ".join(failed), "grades": graded["grades"], "judge_model": judge, "self_graded": graded["self_graded"],
            "tokens": call.tokens + graded["tokens"], "model": call.model, "measured": {}, "wanted": []}


def _aggregate(agent_key: str, prompt_ref: str, results: list[dict], ragas: dict, *, eval_id: str, batch: str, benchmark: str, reviewed: bool | None) -> None:
    """One stored row per metric for this run. A metric nothing measured is stored with its reason and no value."""
    base = {"eval_id": eval_id, "batch": batch, "benchmark": benchmark, "labels_reviewed": reviewed}
    cases = [r for r in results if r.get("measured") is not None]
    wanted = {m for r in cases for m in r.get("wanted", [])}
    for metric in ("groundedness", "faithfulness", "recall", "f1"):  # the four tiles always get a row, n/a where they do not apply
        if not store.applies(agent_key, metric):
            store.record(agent_key, prompt_ref, metric, status="n/a", reason="Does not apply to this agent", **base)
    g = [r["measured"]["groundedness"] for r in cases if "groundedness" in r["measured"]]
    if g and store.applies(agent_key, "groundedness"):
        n = sum(x["n"] for x in g)
        if n:
            store.record(agent_key, prompt_ref, "groundedness", value=sum(x["value"] * x["n"] for x in g) / n, n=n, detail=[{"case": r["name"], "bad": r["measured"]["groundedness"]["bad"]} for r in cases if "groundedness" in r["measured"]], **base)
        else:
            store.record(agent_key, prompt_ref, "groundedness", status="not_measured", reason="No reply cited a file, line, or quote", **base)
    k = [r["measured"]["key"] for r in cases if "key" in r["measured"]]
    if k:
        tp, fn = sum(x["tp"] for x in k), sum(x["fn"] for x in k)
        fp = None if any(x["fp"] is None for x in k) else sum(x["fp"] for x in k)
        detail = {"tp": tp, "fp": fp, "fn": fn, "missed": [x["missed"] for x in k], "extra": [x["extra"] for x in k]}
        for metric, value in (("precision", None if fp is None else metrics.precision(tp, fp)), ("recall", metrics.recall(tp, fn)), ("f1", None if fp is None else metrics.f1(tp, fp, fn))):
            if value is None:
                store.record(agent_key, prompt_ref, metric, status="not_measured", reason="This key lists facts to find, so extras cannot be counted" if fp is None else "Nothing was labelled or found, so the ratio has no denominator", detail=detail, **base)
            else:
                store.record(agent_key, prompt_ref, metric, value=value, n=len(k), detail=detail, **base)
    for r in cases:
        if "mutation" in r["measured"]:
            m = r["measured"]["mutation"]
            if m["score"] is None:
                store.record(agent_key, prompt_ref, "mutation_score", status="inconclusive", reason=m["reason"], detail=m, **base)
            else:
                store.record(agent_key, prompt_ref, "mutation_score", value=m["score"], n=m["killed"] + m["survived"], detail=m, **base)
    for metric in wanted & set(store.RAGAS):
        if not store.applies(agent_key, metric):
            store.record(agent_key, prompt_ref, metric, status="n/a", reason="Does not apply to this agent", **base)
            continue
        info = ragas.get(metric, {"status": "not_measured", "reason": "Not measured: model-graded metrics were not requested for this run"})
        if info.get("values"):
            store.record(agent_key, prompt_ref, metric, value=sum(info["values"]) / len(info["values"]), n=len(info["values"]), judge_model=info["judge"], self_graded=info["self_graded"], tokens=info["tokens"], detail=info["cases"], **base)
        else:
            store.record(agent_key, prompt_ref, metric, status=info.get("status", "not_measured"), reason=info.get("reason", "No case could be scored"), judge_model=info.get("judge", ""), self_graded=info.get("self_graded", False), tokens=info.get("tokens", 0), **base)


async def _ragas(agent_key: str, results: list[dict]) -> dict:
    """Per metric: the values with their cases, or the status and reason there are none. One batch through MAF's Evaluator interface."""
    asked = [(r, [m for m in r["wanted"] if m in store.RAGAS]) for r in results if r.get("_item") and any(m in store.RAGAS for m in r.get("wanted", []))]
    if not asked:
        return {}
    model_name = next((r["model"] for r, _ in asked if r.get("model")), "")
    names = tuple(sorted({m for _, ms in asked for m in ms}))
    runner = ragas_evaluator.RagasEvaluator(model_name, names)
    items = []
    for r, _ in asked:
        question, answer, context, reference = r["_item"]
        items.append(EvalItem(conversation=[Message(role="user", contents=[Content.from_text(question)]), Message(role="assistant", contents=[Content.from_text(answer)])], context=context or None, expected_output=reference or None))
    runner.plan = [ms for _, ms in asked]
    try:
        done = await runner.evaluate(items, eval_name=f"{agent_key}:ragas")
    except Exception as exc:  # the judge failing is a result of its own, never a score
        return {m: {"status": "failed", "reason": f"RAGAS could not run: {type(exc).__name__}: {str(exc)[:300]}", "judge": runner.model, "self_graded": ragas_evaluator.self_graded(model_name), "tokens": runner.tokens} for m in names}
    if done.status != "completed":
        return {m: {"status": "not_measured", "reason": done.error or "RAGAS did not run"} for m in names}
    out: dict = {}
    for metric in names:
        values, cases = [], []
        why = ""
        for (r, _), item in zip(asked, done.items):
            found = next((s for s in item.scores if s.name == metric), None)
            if found:
                values.append(found.score)
                cases.append({"case": r["name"], "value": found.score, "reason": (found.sample or {}).get("reason", "")})
                r.setdefault("ragas", {})[metric] = found.score
            else:
                why = (item.metadata or {}).get("notes", {}).get(metric, why)
        status = "unavailable" if metric in runner.skipped else "failed" if why.startswith("failed") else "not_measured"
        out[metric] = {"values": values, "cases": cases, "judge": runner.model, "self_graded": ragas_evaluator.self_graded(model_name), "tokens": runner.by_metric.get(metric, 0),
                       "status": status, "reason": runner.skipped.get(metric) or why or "No case could be scored"}
    return out


async def run(agent_key: str, *, benchmark: str = "", repeats: int = 1, ragas: bool = False) -> dict:
    """Run an agent's eval cases, or a benchmark's cases for it. `repeats` runs the whole set again so the spread can be shown; `ragas` adds the model-graded metrics."""
    path = EVALS_DIR / f"{agent_key}.json"
    if not path.exists():
        raise KeyError(f"No eval cases for {agent_key}")
    if benchmark and benchmark not in benchmarks():
        raise KeyError(f"No benchmark {benchmark}")
    _sandbox()
    reviewed = bool(_labels(benchmark).get("reviewed", False)) if benchmark else None
    batch, runs = new_id("bat"), []
    for _ in range(max(1, repeats)):
        cases = bench_cases(agent_key, benchmark) if benchmark else [*json.loads(path.read_text(encoding="utf-8")), *skill_cases(agent_key)]
        results = [await _run_case(agent_key, case) for case in cases]
        scored = [r for r in results if r["passed"] is not None]  # a case that needs a grader is neither passed nor failed
        ref = prompts.ref(agent_key)
        shown = await _ragas(agent_key, results) if ragas else {}
        eval_id = new_id("evl")
        _aggregate(agent_key, ref, results, shown, eval_id=eval_id, batch=batch, benchmark=benchmark, reviewed=reviewed)
        for r in results:
            r.pop("_item", None)
        record = {"id": eval_id, "agent": agent_key, "prompt_ref": ref, "passed": sum(r["passed"] for r in scored), "total": len(scored), "results": json.dumps(results, default=str), "created_at": now()}
        with db() as con:
            con.execute("INSERT INTO evaluations (id, agent, prompt_ref, passed, total, results, created_at) VALUES (:id,:agent,:prompt_ref,:passed,:total,:results,:created_at)", record)
        runs.append({**record, "results": results, "needs_grader": len(results) - len(scored), "tokens": sum(r.get("tokens", 0) for r in results) + sum(v.get("tokens", 0) for v in shown.values())})
    return {**runs[-1], "batch": batch, "repeats": len(runs), "benchmark": benchmark, "labels_reviewed": reviewed, "tokens_total": sum(r["tokens"] for r in runs)}


async def run_all(concurrency: int = 4) -> list[dict]:
    gate = asyncio.Semaphore(concurrency)

    async def one(agent_key: str) -> dict:
        async with gate:
            return await run(agent_key)

    return await asyncio.gather(*(one(a) for a in available()))


def history(agent_key: str) -> list[dict]:
    with db() as con:
        items = rows(con.execute("SELECT * FROM evaluations WHERE agent=? ORDER BY rowid DESC LIMIT 20", (agent_key,)))
    return [{**i, "results": json.loads(i["results"])} for i in items]


def cases_worst_first(agent_key: str) -> list[dict]:
    """The cases of the latest run: failed first, then by the lowest score any metric gave."""
    latest = history(agent_key)
    if not latest:
        return []

    def badness(r: dict) -> tuple:
        scores = [v for v in (r.get("ragas") or {}).values()]
        return (r["passed"] is not False, min(scores) if scores else 1.0)

    return sorted(latest[0]["results"], key=badness)
