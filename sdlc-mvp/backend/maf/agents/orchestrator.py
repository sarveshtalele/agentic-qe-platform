from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from ..core import AIAgent, AgentSession, Message


class MagenticOrchestratorAgent(AIAgent):
    """
    Dynamic Central Orchestrator managing specialist delegation and workflow execution.
    """

    def __init__(self):
        super().__init__(
            name="MagenticOrchestrator",
            role="Magentic Central Orchestrator",
            description="Coordinates multi-agent SDLC workflows, delegates subtasks, and aggregates deliverables.",
            system_prompt="""You are the Magentic Central Orchestrator for ForgeSDLC.
Break down SDLC objectives into structured agent tasks. Coordinate Requirements, Repo Intelligence,
Test Architecture, Test Design, Test Automation, and Confidence Review agents.""",
        )

    async def process(self, session: AgentSession, inbound_msg: Message) -> List[Message]:
        await session.emit_event("thought_step", {
            "agent": self.name,
            "thought": f"Orchestrator evaluating message from '{inbound_msg.sender}' (kind: {inbound_msg.kind})...",
        })

        content_lower = inbound_msg.content.lower()

        # If inbound is from user, decide first specialist to delegate to
        if inbound_msg.sender == "user":
            if "repo" in content_lower or "scan" in content_lower:
                next_agent = "RepoIntelligenceAnalyst"
            elif "req" in content_lower or "doc" in content_lower or "story" in content_lower:
                next_agent = "RequirementsAnalyst"
            elif "test" in content_lower or "qe" in content_lower or "run" in content_lower:
                next_agent = "PrincipalTestArchitect"
            elif "confidence" in content_lower or "score" in content_lower or "sign" in content_lower:
                next_agent = "ConfidenceReviewer"
            else:
                next_agent = "RequirementsAnalyst"

            await session.emit_event("thought_step", {
                "agent": self.name,
                "thought": f"Delegating initial phase to specialist agent: {next_agent}",
            })

            return [
                Message(
                    sender=self.name,
                    recipient=next_agent,
                    content=inbound_msg.content,
                    kind="chat",
                    payload={"delegated_by": self.name},
                )
            ]

        # If inbound is from a specialist, decide next step or synthesize
        if inbound_msg.sender == "RepoIntelligenceAnalyst":
            return [
                Message(
                    sender=self.name,
                    recipient="RequirementsAnalyst",
                    content="Proceed with requirements analysis.",
                    kind="chat",
                )
            ]
        elif inbound_msg.sender == "RequirementsAnalyst":
            return [
                Message(
                    sender=self.name,
                    recipient="PrincipalTestArchitect",
                    content="Formulate test strategy from approved requirements.",
                    kind="chat",
                )
            ]
        elif inbound_msg.sender == "PrincipalTestArchitect":
            return [
                Message(
                    sender=self.name,
                    recipient="TestDesignEngineer",
                    content="Design deterministic test cases.",
                    kind="chat",
                )
            ]
        elif inbound_msg.sender == "TestDesignEngineer":
            return [
                Message(
                    sender=self.name,
                    recipient="TestAutomationEngineer",
                    content="Generate automated pytest test code.",
                    kind="chat",
                )
            ]
        elif inbound_msg.sender == "TestAutomationEngineer":
            return [
                Message(
                    sender=self.name,
                    recipient="QAExecutionEngineer",
                    content="Execute test suite in isolated runner.",
                    kind="chat",
                )
            ]
        elif inbound_msg.sender == "QAExecutionEngineer":
            return [
                Message(
                    sender=self.name,
                    recipient="ConfidenceReviewer",
                    content="Perform final confidence and release readiness review.",
                    kind="chat",
                )
            ]
        elif inbound_msg.sender == "ConfidenceReviewer":
            # Complete workflow!
            summary = (
                "Full SDLC & Quality Engineering cycle completed successfully! "
                "All specialist agents have executed their phases and generated verified artifacts."
            )
            await session.emit_event("agent_message", {
                "agent": self.name,
                "content": summary,
            })
            return []

        return []
