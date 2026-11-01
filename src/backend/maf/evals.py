"""Agent evals on MAF's evaluation API. Each case runs the real active prompt, so prompt versions can be compared."""
from __future__ import annotations

import asyncio
import json
import re

from agent_framework import LocalEvaluator, evaluate_agent, evaluator
from pydantic import ValidationError

from backend.config import ROOT
from backend.core import gherkin, prompts
from backend.core import skills as skill_lib
from backend.core.errors import classify
from backend.db import db, new_id, now, rows
from backend.maf import runtime as agents
from backend.qe import model

EVALS_DIR = ROOT / "evals"
EVAL_PROJECT = "prj_agent_evals"


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


async def _run_case(agent_key: str, case: dict) -> dict:
    if "skill" in case and not case["checks"]:  # nothing code can check: not run, not scored
        return {"name": case["name"], "category": "skill", "skill": case["skill"], "passed": None, "status": "needs_grader", "failed_checks": [], "expected_behavior": case["expected_behavior"]}
    # existing cases measure the prompt alone, so they send no skill; a skill case sends exactly its skill
    call = agents.AgentCall(None, EVAL_PROJECT, agent_key, source="eval", skills=(case["skill"],) if "skill" in case else ())
    try:
        schema = _schemas().get(case["checks"].get("json_schema"))
        await call.text(f"{case['query']}\n\n{agents.format_rule(schema)}" if schema else case["query"])
    except Exception as exc:  # a failing agent is an eval failure recorded in the result, not a crash of the whole suite
        error = classify(exc)
        return {"name": case["name"], "category": case.get("category", "quality"), "skill": case.get("skill", ""), "passed": False, "failed_checks": [f"error: {error.code} {error.message[:200]}"]}
    outcome = await evaluate_agent(agent=call.agent, queries=[case["query"]], responses=[call.last_response], evaluators=[LocalEvaluator(*build_checks(case["checks"]))], eval_name=f"{agent_key}:{case['name']}")
    items = outcome[0].items or []
    failed = [s.name for item in items for s in item.scores if s.passed is False] if items else []
    counts = outcome[0].result_counts or {}
    result = {"name": case["name"], "category": case.get("category", "quality"), "skill": case.get("skill", ""), "passed": counts.get("failed", 0) == 0 and counts.get("errored", 0) == 0 and counts.get("passed", 0) > 0, "failed_checks": failed}
    if "skill" in case:  # only the code checks were scored; the plugin's sentences were not
        result["ungraded_expectations"] = case["expected_behavior"]
    return result


async def run(agent_key: str) -> dict:
    path = EVALS_DIR / f"{agent_key}.json"
    if not path.exists():
        raise KeyError(f"No eval cases for {agent_key}")
    _sandbox()
    cases = [*json.loads(path.read_text(encoding="utf-8")), *skill_cases(agent_key)]
    results = [await _run_case(agent_key, case) for case in cases]
    scored = [r for r in results if r["passed"] is not None]  # a case that needs a grader is neither passed nor failed
    record = {"id": new_id("evl"), "agent": agent_key, "prompt_ref": prompts.ref(agent_key), "passed": sum(r["passed"] for r in scored), "total": len(scored), "results": json.dumps(results), "created_at": now()}
    with db() as con:
        con.execute("INSERT INTO evaluations (id, agent, prompt_ref, passed, total, results, created_at) VALUES (:id,:agent,:prompt_ref,:passed,:total,:results,:created_at)", record)
    return {**record, "results": results, "needs_grader": len(results) - len(scored)}


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
