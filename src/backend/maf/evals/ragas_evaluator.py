"""RAGAS metrics as a MAF `Evaluator`. `ragas` is optional (requirements-evals.txt) and is imported only when a score is asked for.

Without it every RAGAS metric reads "Not measured: RAGAS is not installed" and has no value. Confirmed against ragas 0.4.3 on 2026-11-02:
`ragas.metrics.collections` has Faithfulness, ContextRecall, ContextPrecision, FactualCorrectness (mode "f1"), and AnswerRelevancy (the plan's
"ResponseRelevancy"). `AnswerRelevancy` needs an embeddings model. `llm_factory(model, client=AsyncOpenAI(...))` builds the judge.
"""
from __future__ import annotations

import importlib.util
import os
import re
from typing import Sequence

from agent_framework import EvalItem, EvalItemResult, EvalResults, EvalScoreResult

from backend.config import MODEL_NO_CACHE
from backend.maf import llm

METRICS = ("faithfulness", "context_recall", "context_precision", "factual_correctness", "response_relevancy")
JUDGE_MAX_TOKENS = int(os.environ.get("ATLAS_EVAL_MAX_TOKENS", "16384"))
NOT_INSTALLED = "Not measured: RAGAS is not installed"
NO_EMBEDDINGS = "Not available: the model endpoint offers no embeddings model, which Response Relevancy needs"
CONTEXT_METRICS = ("faithfulness", "context_recall", "context_precision")
REFERENCE_METRICS = ("context_recall", "context_precision", "factual_correctness")
NEEDS = {"faithfulness": "context", "context_recall": "context and reference", "context_precision": "context and reference",
         "factual_correctness": "reference", "response_relevancy": "an embeddings model"}


def judge_model() -> str:
    """The grader model. Empty means none was chosen."""
    return os.environ.get("ATLAS_EVAL_MODEL", "").strip()


def self_graded(agent_model: str) -> bool:
    """A model grading its own work is a weak check, so scores say so."""
    judge = judge_model()
    return not judge or judge == agent_model


def installed() -> tuple[bool, str]:
    if importlib.util.find_spec("ragas") is None:
        return False, NOT_INSTALLED
    try:
        import ragas  # noqa: F401
    except Exception as exc:  # a broken install (such as a langchain mismatch) is not a number either
        return False, f"Not measured: RAGAS is installed but cannot be imported ({type(exc).__name__}: {str(exc)[:160]})"
    return True, ""


def chunks(context: str) -> list[str]:
    """Context pieces for RAGAS: one per `--- FILE name ---` block when the context has them, else the whole text."""
    parts = [p.strip() for p in re.split(r"(?=^--- FILE .+? ---\s*$)", context, flags=re.M) if p.strip()]
    return parts or ([context.strip()] if context.strip() else [])


class RagasEvaluator:
    """MAF `Evaluator`: scores each item with the metrics its fields allow. Tokens used by the judge are in `tokens`."""

    name = "ragas"

    def __init__(self, agent_model: str = "", metrics: Sequence[str] = METRICS, model: str = ""):
        self.model, self.agent_model, self.wanted = model or judge_model() or agent_model, agent_model, tuple(metrics)
        self.tokens = 0
        self.by_metric: dict[str, int] = {}  # judge tokens per metric
        self.plan: list[Sequence[str]] | None = None  # metrics wanted for each item, when they differ
        self.skipped: dict[str, str] = {}  # metric -> why no value, over the whole batch

    def _client(self):
        from openai import AsyncOpenAI

        cfg = llm.current()
        client = AsyncOpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"] or None, timeout=180, max_retries=1)
        create = client.chat.completions.create

        async def counted(*args, **kwargs):
            if MODEL_NO_CACHE:
                kwargs.setdefault("extra_body", {"cache": {"no-cache": True}})
            reply = await create(*args, **kwargs)
            self.tokens += getattr(getattr(reply, "usage", None), "total_tokens", 0) or 0
            return reply

        client.chat.completions.create = counted
        return client

    async def evaluate(self, items: Sequence[EvalItem], *, eval_name: str = "Eval") -> EvalResults:
        ok, why = installed()
        if not ok:
            return EvalResults(provider=self.name, status="not_measured", error=why)
        from ragas.llms import llm_factory
        from ragas.metrics import collections as rm

        judge = llm_factory(self.model, client=self._client(), max_tokens=JUDGE_MAX_TOKENS)  # the default 1024 cut a reasoning model off (IncompleteOutputException, 2026-11-02)
        scorers = {"faithfulness": rm.Faithfulness(judge), "context_recall": rm.ContextRecall(judge), "context_precision": rm.ContextPrecision(judge),
                   "factual_correctness": rm.FactualCorrectness(judge, mode="f1")}
        self.skipped["response_relevancy"] = NO_EMBEDDINGS  # ponytail: no embeddings on this endpoint (404 api_not_supported, 2026-11-02). Add AnswerRelevancy when one exists
        results, counts = [], {"passed": 0, "failed": 0, "errored": 0}
        for number, item in enumerate(items, 1):
            scores, notes = [], {}
            context, reference = chunks(item.context or ""), (item.expected_output or "").strip()
            for metric in (self.plan[number - 1] if self.plan else self.wanted):
                if metric not in scorers:
                    continue
                if (metric in CONTEXT_METRICS and not context) or (metric in REFERENCE_METRICS and not reference):
                    notes[metric] = f"n/a: needs {NEEDS[metric]}, which this case does not have"
                    continue
                before = self.tokens
                try:
                    if metric == "faithfulness":
                        found = await scorers[metric].ascore(user_input=item.query, response=item.response, retrieved_contexts=context)
                    elif metric == "context_recall":
                        found = await scorers[metric].ascore(user_input=item.query, retrieved_contexts=context, reference=reference)
                    elif metric == "context_precision":
                        found = await scorers[metric].ascore(user_input=item.query, reference=reference, retrieved_contexts=context)
                    else:
                        found = await scorers[metric].ascore(response=item.response, reference=reference)
                    scores.append(EvalScoreResult(name=metric, score=float(found.value), sample={"reason": found.reason or "", "judge": self.model, "self_graded": self_graded(self.agent_model)}))
                except Exception as exc:  # one metric failing must not hide the others
                    notes[metric] = f"failed: {type(exc).__name__}: {str(exc)[:300]}"
                self.by_metric[metric] = self.by_metric.get(metric, 0) + self.tokens - before
            status = "error" if notes and not scores and any(v.startswith("failed") for v in notes.values()) else "pass"
            counts["errored" if status == "error" else "passed"] += 1
            results.append(EvalItemResult(item_id=str(number), status=status, scores=scores, input_text=item.query, output_text=item.response, metadata={"notes": notes}))
        return EvalResults(provider=self.name, status="completed", result_counts=counts, items=results)
