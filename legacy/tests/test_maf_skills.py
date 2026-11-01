"""
Comprehensive Pytest Suite for Microsoft Agent Framework (MAF) Agent Skills.
Validates all 11 ported skills from sarveshtalele/agentic-qe:
1.  RepoAnalysisSkill (analyzing_repositories)
2.  RequirementsContractSkill (extracting_requirements)
3.  RiskCalculationSkill (planning_tests)
4.  TestCaseDesignSkill (designing_test_cases)
5.  TestCodeEmissionSkill (generating_test_code)
6.  IsolatedTestExecutionSkill (executing_tests)
7.  TestHealingSkill (healing_tests)
8.  TraceabilityMatrixSkill (tracing_coverage)
9.  TestDataSynthesisSkill (generating_test_data)
10. UserStoryAuthoringSkill (authoring_user_stories)
11. QEDashboardSkill (building_qe_dashboard)
"""
from __future__ import annotations

import pytest
from pathlib import Path
from backend.maf.skills import (
    AgentSkill,
    SkillRegistry,
    RepoAnalysisSkill,
    RequirementsContractSkill,
    RiskCalculationSkill,
    TestCaseDesignSkill,
    TestCodeEmissionSkill,
    IsolatedTestExecutionSkill,
    TestHealingSkill,
    TraceabilityMatrixSkill,
    TestDataSynthesisSkill,
    UserStoryAuthoringSkill,
    QEDashboardSkill,
)
from backend.maf.core import AgentSession, Message
from backend.maf.agents import (
    RepoIntelligenceAgent,
    RequirementsAnalystAgent,
    PrincipalTestArchitectAgent,
    TestDesignEngineerAgent,
    TestAutomationEngineerAgent,
    QAExecutionEngineerAgent,
    ConfidenceReviewerAgent,
)
from backend.maf.workflows import SequentialBuilder, ConcurrentBuilder


# ---------------------------------------------------------------------------
# Skill Registry Tests
# ---------------------------------------------------------------------------
def test_skill_registry_discovery():
    all_skills = SkillRegistry.list_all()
    assert len(all_skills) >= 11, f"Expected at least 11 registered skills, got {len(all_skills)}"
    names = {s["name"] for s in all_skills}
    expected = {
        "analyzing_repositories",
        "extracting_requirements",
        "planning_tests",
        "designing_test_cases",
        "generating_test_code",
        "executing_tests",
        "healing_tests",
        "tracing_coverage",
        "generating_test_data",
        "authoring_user_stories",
        "building_qe_dashboard",
    }
    assert expected.issubset(names), f"Missing skills: {expected - names}"


# ---------------------------------------------------------------------------
# Skill 1: RepoAnalysisSkill
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_repo_analysis_skill(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name": "test-pkg"}', encoding="utf-8")
    (tmp_path / "index.ts").write_text('export const x = 1;', encoding="utf-8")
    (tmp_path / "index.test.ts").write_text('test("pass", () => {});', encoding="utf-8")

    skill = RepoAnalysisSkill()
    res = await skill.execute({"repo_dir": str(tmp_path)})
    assert res["valid"] is True
    assert res["source_files"] >= 1
    assert res["test_files"] >= 1
    assert "package.json" in str(res["manifests"])


# ---------------------------------------------------------------------------
# Skill 2: RequirementsContractSkill
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_requirements_contract_skill():
    skill = RequirementsContractSkill()
    doc = """
    - User must authenticate with OAuth2 token before accessing ledger.
    - System shall calculate sub-second arithmetic operations with zero unhandled exceptions.
    - Administrator must be able to revoke API credentials immediately.
    """
    res = await skill.execute({"spec_text": doc, "source_file": "spec.md"})
    reqs = res.get("requirements", [])
    assert len(reqs) >= 2
    assert any("authenticate" in r["title"].lower() or "authenticate" in r["behavior"].lower() for r in reqs)
    assert any(r.get("evidenceQuote") for r in reqs)


# ---------------------------------------------------------------------------
# Skill 3: RiskCalculationSkill
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_risk_calculation_skill():
    skill = RiskCalculationSkill()
    res = await skill.execute({
        "controls_covered": 38,
        "level_fit": 28,
        "scenarios_derivable": 28,
    })
    assert res["score"] == 94
    assert res["verdict"] == "APPROVED"
    assert res["ready_for_gate_2"] is True


# ---------------------------------------------------------------------------
# Skill 4: TestCaseDesignSkill
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_test_case_design_skill():
    skill = TestCaseDesignSkill()
    reqs = [{"id": "REQ-001", "title": "Sub-second Transaction Processing"}]
    res = await skill.execute({"requirements": reqs})
    cases = res.get("test_cases", [])
    assert len(cases) == 3  # Positive, Boundary, Exception
    types = {c["type"] for c in cases}
    assert {"Positive", "Boundary", "Exception"}.issubset(types)
    assert all("bdd" in c and "given" in c["bdd"] for c in cases)


# ---------------------------------------------------------------------------
# Skill 5: TestCodeEmissionSkill
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_test_code_emission_skill():
    skill = TestCodeEmissionSkill()
    cases = [
        {"caseId": "TC-001-POS", "scenario": "Nominal verification", "type": "Positive"},
        {"caseId": "TC-002-EXC", "scenario": "Defensive exception check", "type": "Exception"},
    ]
    # Pytest emission
    py_res = await skill.execute({"test_cases": cases, "framework": "pytest"})
    assert "def test_tc_001_pos_execution():" in py_res["code"]
    assert "def test_tc_002_exc_exception_handling():" in py_res["code"]

    # Playwright emission
    ts_res = await skill.execute({"test_cases": cases, "framework": "playwright"})
    assert "@playwright/test" in ts_res["code"]
    assert "TC-001-POS" in ts_res["code"]


# ---------------------------------------------------------------------------
# Skill 6: IsolatedTestExecutionSkill
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_isolated_test_execution_skill():
    skill = IsolatedTestExecutionSkill()
    code = """
import pytest

def test_nominal_addition():
    assert 2 + 2 == 4

def test_string_format():
    val = "agentic_qe"
    assert val.upper() == "AGENTIC_QE"
"""
    res = await skill.execute({"test_code": code, "timeout_sec": 10})
    assert res["passed"] is True
    assert res["exit_code"] == 0
    assert res["passed_cases"] == 2
    assert res["failed_cases"] == 0


# ---------------------------------------------------------------------------
# Skill 7: TestHealingSkill (Assertion Preservation Rule)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_test_healing_skill_assertion_preservation():
    skill = TestHealingSkill()
    # 1. Selector drift (healable)
    sel_res = await skill.execute({
        "error_message": "locator.click: Timeout 5000ms exceeded waiting for locator('button.submit')",
        "test_source": "await page.locator('div > button.submit-btn').click();",
    })
    assert sel_res["category"] == "SELECTOR_DRIFT"
    assert sel_res["can_heal"] is True
    assert sel_res["assertion_preservation_verified"] is True

    # 2. Application defect (non-healable, test assertions must NOT be weakened!)
    defect_res = await skill.execute({
        "error_message": "AssertionError: Expected 200 OK but received 500 Internal Server Error",
    })
    assert defect_res["category"] == "APPLICATION_DEFECT"
    assert defect_res["can_heal"] is False
    assert defect_res["assertion_preservation_verified"] is True


# ---------------------------------------------------------------------------
# Skill 8: TraceabilityMatrixSkill
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_traceability_matrix_skill():
    skill = TraceabilityMatrixSkill()
    reqs = [{"id": "REQ-001"}, {"id": "REQ-002"}]
    cases = [
        {"caseId": "TC-001", "requirementId": "REQ-001"},
        {"caseId": "TC-002", "requirementId": "REQ-002"},
    ]
    res = await skill.execute({"requirements": reqs, "test_cases": cases})
    assert res["coverage_percent"] == 100.0
    assert res["covered_requirements"] == 2
    assert res["meets_gate_criteria"] is True


# ---------------------------------------------------------------------------
# Skill 9: TestDataSynthesisSkill
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_test_data_synthesis_skill():
    skill = TestDataSynthesisSkill()
    valid_user = await skill.execute({"schema_type": "user", "role": "admin", "is_valid": True})
    assert valid_user["fixture"]["is_authenticated"] is True
    assert "bearer_" in valid_user["fixture"]["token"]

    invalid_user = await skill.execute({"schema_type": "user", "role": "guest", "is_valid": False})
    assert invalid_user["fixture"]["is_authenticated"] is False


# ---------------------------------------------------------------------------
# Skill 10: UserStoryAuthoringSkill
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_user_story_authoring_skill():
    skill = UserStoryAuthoringSkill()
    reqs = [{"id": "REQ-101", "title": "Calculate tax withholding", "actor": "FinanceOperator"}]
    res = await skill.execute({"requirements": reqs})
    stories = res.get("stories", [])
    assert len(stories) == 1
    assert "As an FinanceOperator" in stories[0]["role"]
    assert len(stories[0]["acceptance_criteria"]) >= 3


# ---------------------------------------------------------------------------
# Skill 11: QEDashboardSkill
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_qe_dashboard_skill():
    skill = QEDashboardSkill()
    res = await skill.execute({
        "gate_number": 5,
        "gate_name": "Release Sign-off",
        "confidence_score": 96.0,
        "project_id": "PRJ-999",
    })
    assert res["verdict"] == "APPROVED"
    assert "GATE-5-REPORT" in res["markdown_report"]
    assert "SHA-256" in res["markdown_report"]


# ---------------------------------------------------------------------------
# Agent Skill Attachment & Sequential Workflow Execution
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_agent_skill_execution_in_sequential_workflow():
    session = AgentSession("test-sess-001", "PRJ-TEST-SKILLS")
    session.set_state("document_text", "REQ-001: System must process transactions and generate invoices.")

    req_agent = RequirementsAnalystAgent()
    arch_agent = PrincipalTestArchitectAgent()
    design_agent = TestDesignEngineerAgent()
    auto_agent = TestAutomationEngineerAgent()
    exec_agent = QAExecutionEngineerAgent()
    conf_agent = ConfidenceReviewerAgent()

    # Verify skills are registered on agents
    assert len(req_agent.skills) >= 2
    assert len(arch_agent.skills) >= 1
    assert len(design_agent.skills) >= 1
    assert len(auto_agent.skills) >= 2
    assert len(exec_agent.skills) >= 1
    assert len(conf_agent.skills) >= 2

    # Build sequential pipeline
    engine = SequentialBuilder.build(
        session=session,
        nodes=[
            ("RequirementsAnalyst", req_agent),
            ("PrincipalTestArchitect", arch_agent),
            ("TestDesignEngineer", design_agent),
            ("TestAutomationEngineer", auto_agent),
            ("QAExecutionEngineer", exec_agent),
            ("ConfidenceReviewer", conf_agent),
        ],
    )

    # Run engine
    await engine.run("RequirementsAnalyst", Message(content="Extract requirements and execute test workflow"))

    # Assert end-to-end artifact flow
    assert session.get_state("requirements") is not None
    assert session.get_state("test_strategy") is not None
    assert session.get_state("test_cases") is not None
    assert session.get_state("generated_test_code") is not None
    assert session.get_state("test_execution_result") is not None
    assert session.get_state("confidence_review") is not None
    assert session.get_state("confidence_review")["total_score"] >= 80


# ---------------------------------------------------------------------------
# API Endpoints for MAF Skills
# ---------------------------------------------------------------------------
def test_maf_skills_api_endpoints():
    from starlette.testclient import TestClient
    from backend.app import app

    client = TestClient(app)

    # 1. List all MAF skills
    res = client.get("/api/maf/skills")
    assert res.status_code == 200
    data = res.json()
    assert "skills" in data
    assert data["count"] >= 11
    skill_names = {s["name"] for s in data["skills"]}
    assert "planning_tests" in skill_names
    assert "executing_tests" in skill_names

    # 2. Execute risk calculation skill via API
    exec_res = client.post("/api/maf/skills/planning_tests/execute", json={
        "controls_covered": 36,
        "level_fit": 28,
        "scenarios_derivable": 28,
    })
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["skill"] == "planning_tests"
    assert exec_data["result"]["score"] == 92
    assert exec_data["result"]["verdict"] == "APPROVED"
