"""
Tests for Microsoft Agent Framework (MAF) Agent Evaluation Subsystem.
Verifies compliance with agent-framework.pdf (Pages 220-227):
- RelevanceEvaluator, CoherenceEvaluator, GroundednessEvaluator, TaskAdherenceEvaluator
- CompositeEvaluator weighted multi-dimensional grading
- Benchmark evaluation across all 8 MAF agents
- API endpoints: /api/evaluations, /api/evaluations/run, /api/evaluations/evaluate-item
"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient
from backend.app import app
from backend.maf.evaluation import (
    AgentEvaluationSuite,
    CompositeEvaluator,
    EvalItem,
    RelevanceEvaluator,
    CoherenceEvaluator,
    GroundednessEvaluator,
    TaskAdherenceEvaluator,
)

client = TestClient(app)


@pytest.mark.asyncio
async def test_maf_individual_evaluators():
    item = EvalItem(
        query="Implement exponential backoff retry for failed order transactions",
        response="""// Implements exponential backoff retry for failed order transactions
export function retryWithBackoff(fn, maxRetries = 3) {
  let delay = 1000;
  for (let i = 0; i < maxRetries; i++) {
    try { return fn(); } catch (err) { delay *= 2; }
  }
}""",
        context="Order transaction service retry requirement with exponential backoff.",
        agent_name="FeatureBuilderAgent",
    )

    relevance = await RelevanceEvaluator().evaluate(item)
    assert relevance.passed is True
    assert relevance.score >= 0.70

    coherence = await CoherenceEvaluator().evaluate(item)
    assert coherence.passed is True
    assert coherence.score >= 0.70

    groundedness = await GroundednessEvaluator().evaluate(item)
    assert groundedness.passed is True
    assert groundedness.score >= 0.70

    adherence = await TaskAdherenceEvaluator().evaluate(item)
    assert adherence.passed is True
    assert adherence.score >= 0.70


@pytest.mark.asyncio
async def test_maf_composite_evaluator():
    item = EvalItem(
        query="Extract testable business requirements for user authentication",
        response="REQ-001: Authentication - Users must authenticate using OAuth2 token.\nREQ-002: Token Refresh - Expired tokens must be refreshed automatically.",
        context="User authentication and token refresh specifications.",
        agent_name="RequirementsAnalystAgent",
    )
    evaluator = CompositeEvaluator()
    result = await evaluator.evaluate_item(item)

    assert result.agent_name == "RequirementsAnalystAgent"
    assert result.composite_score >= 80.0
    assert result.passed is True
    assert result.verdict in ("EXCELLENT", "PASS")
    assert len(result.metrics) == 4
    assert "relevance" in result.metrics
    assert "coherence" in result.metrics
    assert "groundedness" in result.metrics
    assert "task_adherence" in result.metrics


@pytest.mark.asyncio
async def test_maf_agent_evaluation_suite_all_pass():
    suite_res = await AgentEvaluationSuite.evaluate_all()

    assert suite_res["total_agents_evaluated"] == 8
    assert suite_res["all_passed"] is True
    assert suite_res["overall_composite_score"] >= 85.0

    expected_agents = [
        "RequirementsAnalystAgent",
        "DocumentReviewerAgent",
        "FeatureBuilderAgent",
        "InteractiveDebuggerAgent",
        "RepoIntelligenceAnalyst",
        "TestDesignEngineerAgent",
        "TestAutomationEngineerAgent",
        "ConfidenceReviewerAgent",
    ]
    for ag in expected_agents:
        assert ag in suite_res["agents"]
        data = suite_res["agents"][ag]
        assert data["passed"] is True
        assert data["composite_score"] >= 75.0
        assert data["verdict"] in ("EXCELLENT", "PASS")


def test_maf_evaluation_api_endpoints():
    # 1. GET /api/evaluations
    res_get = client.get("/api/evaluations")
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert data_get["all_passed"] is True
    assert data_get["total_agents_evaluated"] == 8

    # 2. POST /api/evaluations/run
    res_run = client.post("/api/evaluations/run")
    assert res_run.status_code == 200
    data_run = res_run.json()
    assert data_run["overall_composite_score"] >= 85.0

    # 3. POST /api/evaluations/evaluate-item
    res_item = client.post(
        "/api/evaluations/evaluate-item",
        json={
            "query": "Synthesize regression pytest",
            "response": "import pytest\ndef test_order_regression():\n    assert 1 == 1\n",
            "context": "Order regression testing",
            "agent_name": "TestAutomationEngineerAgent",
        },
    )
    assert res_item.status_code == 200
    data_item = res_item.json()
    assert data_item["passed"] is True
    assert data_item["composite_score"] >= 70.0
