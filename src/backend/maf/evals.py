"""Agent evals on MAF's evaluation API. Each case runs the real active prompt, so prompt versions can be compared."""
from __future__ import annotations

import asyncio
import json

from agent_framework import LocalEvaluator, evaluate_agent, evaluator
from pydantic import ValidationError

from backend.config import ROOT
from backend.core import gherkin, prompts
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


async def _run_case(agent_key: str, case: dict) -> dict:
    call = agents.AgentCall(None, EVAL_PROJECT, agent_key, source="eval")
    try:
        schema = _schemas().get(case["checks"].get("json_schema"))
        await call.text(f"{case['query']}\n\n{agents.format_rule(schema)}" if schema else case["query"])
    except Exception as exc:  # a failing agent is an eval failure, not a crash of the whole suite
        return {"name": case["name"], "category": case.get("category", "quality"), "passed": False, "failed_checks": [f"error: {str(exc)[:200]}"]}
    outcome = await evaluate_agent(agent=call.agent, queries=[case["query"]], responses=[call.last_response], evaluators=[LocalEvaluator(*build_checks(case["checks"]))], eval_name=f"{agent_key}:{case['name']}")
    items = outcome[0].items or []
    failed = [s.name for item in items for s in item.scores if s.passed is False] if items else []
    counts = outcome[0].result_counts or {}
    return {"name": case["name"], "category": case.get("category", "quality"), "passed": counts.get("failed", 0) == 0 and counts.get("errored", 0) == 0 and counts.get("passed", 0) > 0, "failed_checks": failed}


async def run(agent_key: str) -> dict:
    path = EVALS_DIR / f"{agent_key}.json"
    if not path.exists():
        raise KeyError(f"No eval cases for {agent_key}")
    _sandbox()
    cases = json.loads(path.read_text(encoding="utf-8"))
    results = [await _run_case(agent_key, case) for case in cases]
    passed = sum(r["passed"] for r in results)
    record = {"id": new_id("evl"), "agent": agent_key, "prompt_ref": prompts.ref(agent_key), "passed": passed, "total": len(results), "results": json.dumps(results), "created_at": now()}
    with db() as con:
        con.execute("INSERT INTO evaluations VALUES (:id,:agent,:prompt_ref,:passed,:total,:results,:created_at)", record)
    return {**record, "results": results}


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
