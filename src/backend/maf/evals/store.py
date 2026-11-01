"""Stored metric values and what the cards show. A value exists only when a metric really ran; otherwise a card says why not."""
from __future__ import annotations

import json
from statistics import mean

from backend.core import prompts
from backend.db import db, now, rows

TILES = ("groundedness", "faithfulness", "recall", "f1")
LABELS = {"groundedness": "Groundedness", "faithfulness": "Faithfulness", "context_recall": "Context recall", "context_precision": "Context precision",
          "response_relevancy": "Response relevancy", "factual_correctness": "Factual correctness", "precision": "Precision", "recall": "Recall", "f1": "F1",
          "mutation_score": "Mutation score"}
RAGAS = ("faithfulness", "context_recall", "context_precision", "response_relevancy", "factual_correctness")

# Part 3 "Metrics for each agent": (groundedness applies, faithfulness applies, what recall and F1 are measured against, the agent-specific measure).
# Recall and F1 apply to every agent, against the answer key named here.
METRICS_BY_AGENT = {
    "repo-intelligence-analyst": (True, True, "Key facts in the answer key", "Modules covered, facts matching the scan"),
    "requirements-analyst": (True, True, "Labelled requirements", "Share with one actor and observable behavior"),
    "principal-test-architect": (True, True, "Requirements covered by the plan", "Level fit, duplicates across levels"),
    "test-design-architect": (True, True, "Labelled scenarios, including boundaries", "Case mix, valid oracles"),
    "test-automation-engineer": (True, False, "Cases with a test", "Mutation score, tests that run"),
    "qa-execution-engineer": (True, True, "Failures reported", "Summary matches the results"),
    "defect-diagnostician": (True, True, "Labelled failures: defect, test problem, or environment", "Seeded bugs fixed with tests passing"),
    "confidence-reviewer": (True, True, "Seeded good and bad work, approve or reject", "Agreement with labels"),
    "business-analyst": (True, True, "Facts from the brief", "Invented figures, headings kept, valid Gherkin"),
    "bug-reviewer": (True, True, "Seeded bugs, plus clean files for false alarms", "False alarm rate"),
    "feature-engineer": (False, False, "Named functions and hidden tests", "Hidden tests pass, none broken"),
    "project-copilot": (True, True, "Question and answer key", "Response relevancy, right tool called"),
}


def applies(agent: str, metric: str) -> bool:
    """False means the card shows n/a. An agent outside the table has no promise, so nothing is n/a for it."""
    if agent not in METRICS_BY_AGENT:
        return True
    grounded, faithful, *_ = METRICS_BY_AGENT[agent]
    return {"groundedness": grounded, "faithfulness": faithful}.get(metric, True)


def record(agent: str, prompt_ref: str, metric: str, *, value: float | None = None, status: str = "measured", reason: str = "", n: int = 0, judge_model: str = "",
           self_graded: bool = False, labels_reviewed: bool | None = None, tokens: int = 0, detail: dict | list | None = None, source: str = "eval", eval_id: str = "",
           batch: str = "", agent_call_id: int | None = None, benchmark: str = "") -> None:
    """A value is stored only with status "measured". Any other status stores no number."""
    if status != "measured":
        value = None
    elif value is None:
        raise ValueError(f"{metric} is marked measured but has no value")
    with db() as con:
        con.execute("INSERT INTO evaluation_metrics (eval_id, batch, agent, prompt_ref, metric, value, status, reason, n, judge_model, self_graded, labels_reviewed, tokens, detail, source, agent_call_id, benchmark, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (eval_id, batch, agent, prompt_ref, metric, value, status, reason[:500], n, judge_model, int(self_graded), None if labels_reviewed is None else int(labels_reviewed), tokens,
                     json.dumps(detail, default=str) if detail is not None else "", source, agent_call_id, benchmark, now()))


def record_live(agent: str, project_id: str, prompt_ref: str, check: dict) -> None:
    """Groundedness of one real reply. A reply with no citations records nothing, since there was nothing to measure."""
    if not check["n"]:
        return
    with db() as con:
        found = con.execute("SELECT MAX(id) FROM agent_calls WHERE agent=? AND project_id=?", (agent, project_id)).fetchone()[0]  # ponytail: two parallel calls of one agent in one project can swap ids
    record(agent, prompt_ref, "groundedness", value=check["value"], n=check["n"], source="live", agent_call_id=found, detail={"bad": check["bad"]})


# ---- reading --------------------------------------------------------------------------------------

def _public(r: dict) -> dict:
    return {**r, "self_graded": bool(r["self_graded"]), "labels_reviewed": None if r["labels_reviewed"] is None else bool(r["labels_reviewed"]), "detail": json.loads(r["detail"]) if r["detail"] else None}


def tile(agent: str, metric: str) -> dict:
    """What one card tile shows: n/a, a value with its caveats, not measured, or the reason a metric could not run."""
    if not applies(agent, metric):
        return {"metric": metric, "label": LABELS[metric], "state": "n/a"}
    with db() as con:
        found = rows(con.execute("SELECT * FROM evaluation_metrics WHERE agent=? AND metric=? AND source='eval' ORDER BY id DESC LIMIT 1", (agent, metric)))
        live = rows(con.execute("SELECT value, n FROM (SELECT value, n FROM evaluation_metrics WHERE agent=? AND metric=? AND source='live' ORDER BY id DESC LIMIT 200)", (agent, metric))) if metric == "groundedness" else []
    base = {"metric": metric, "label": LABELS[metric]}
    if found:
        r = _public(found[0])
        reviewed = r["labels_reviewed"]
        return {**base, "state": r["status"], "value": r["value"], "n": r["n"], "reason": r["reason"], "judge_model": r["judge_model"], "self_graded": r["self_graded"], "prompt_ref": r["prompt_ref"],
                "current": r["prompt_ref"] == prompts.ref(agent), "labels": "not reviewed" if reviewed is False else "reviewed" if reviewed else "", "tokens": r["tokens"], "created_at": r["created_at"]}
    if live:
        total = sum(x["n"] for x in live)
        return {**base, "state": "measured", "value": sum(x["value"] * x["n"] for x in live) / total, "n": total, "reason": f"Live: {len(live)} real replies with citations", "self_graded": False, "labels": "", "current": True}
    return {**base, "state": "not_measured", "reason": "Not measured: no evaluation has run"}


def card(agent: str) -> dict:
    return {"agent": agent, "tiles": [tile(agent, m) for m in TILES]}


def cards() -> dict[str, dict]:
    return {a: card(a) for a in METRICS_BY_AGENT}


def detail(agent: str) -> dict:
    """Everything for the agent page: every metric (latest), the trend per prompt version, and the spread over the repeated runs of the latest batch."""
    with db() as con:
        every = [_public(r) for r in rows(con.execute("SELECT * FROM evaluation_metrics WHERE agent=? ORDER BY id", (agent,)))]
    latest_by_metric: dict[str, dict] = {}
    for r in every:
        if r["source"] == "eval":
            latest_by_metric[r["metric"]] = r
    trend: dict[str, dict[str, list[float]]] = {}
    for r in every:
        if r["source"] == "eval" and r["status"] == "measured":
            trend.setdefault(r["metric"], {}).setdefault(r["prompt_ref"], []).append(r["value"])
    spread = {}
    for metric, last in latest_by_metric.items():
        runs = [r["value"] for r in every if r["source"] == "eval" and r["batch"] and r["batch"] == last["batch"] and r["metric"] == metric and r["status"] == "measured"]
        if runs:
            spread[metric] = {"runs": len(runs), "min": min(runs), "max": max(runs), "mean": mean(runs)}
    live = [r for r in every if r["source"] == "live"]
    info = METRICS_BY_AGENT.get(agent)
    return {"agent": agent, "applies": {m: applies(agent, m) for m in LABELS}, "recall_basis": info[2] if info else "", "agent_measure": info[3] if info else "",
            "metrics": [{"metric": m, "label": LABELS[m], **({"state": "n/a"} if not applies(agent, m) else latest_by_metric.get(m, {"state": "not_measured", "reason": "Not measured: no evaluation has run"}))} for m in LABELS],
            "trend": [{"metric": m, "points": [{"prompt_ref": ref, "mean": mean(vals), "runs": len(vals), "min": min(vals), "max": max(vals)} for ref, vals in by.items()]} for m, by in trend.items()],
            "spread": spread, "live": {"replies": len(live), "citations": sum(r["n"] for r in live), "mean": (sum(r["value"] * r["n"] for r in live) / max(1, sum(r["n"] for r in live))) if live else None}}


def by_version(agent: str) -> dict[str, dict]:
    """Mean of each measured metric per prompt reference, for the Prompts page. Nothing for a version that was never evaluated."""
    with db() as con:
        found = rows(con.execute("SELECT prompt_ref, metric, AVG(value) AS value, COUNT(*) AS runs FROM evaluation_metrics WHERE agent=? AND source='eval' AND status='measured' GROUP BY prompt_ref, metric", (agent,)))
    result: dict[str, dict] = {}
    for r in found:
        result.setdefault(r["prompt_ref"], {})[r["metric"]] = {"value": r["value"], "runs": r["runs"]}
    return result
