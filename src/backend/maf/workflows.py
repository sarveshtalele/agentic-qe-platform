from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from .core import AgentSession, Edge, Executor, Message, PregelEngine


class WorkflowBuilder:
    """Generic builder for graph-based MAF workflows."""

    def __init__(self, session: AgentSession):
        self.session = session
        self.engine = PregelEngine(session)

    def add_node(self, name: str, agent_or_fn: Any) -> WorkflowBuilder:
        self.engine.add_executor(Executor(name, agent_or_fn))
        return self

    def add_edge(
        self,
        source: str,
        target: str,
        condition: Optional[Callable[[AgentSession, Message], bool]] = None,
    ) -> WorkflowBuilder:
        self.engine.add_edge(source, target, condition)
        return self

    def build(self) -> PregelEngine:
        return self.engine


class SequentialBuilder:
    """Creates a deterministic linear pipeline of agents (A1 -> A2 -> ... -> An)."""

    @staticmethod
    def build(session: AgentSession, nodes: List[tuple[str, Any]]) -> PregelEngine:
        engine = PregelEngine(session)
        for i, (name, agent) in enumerate(nodes):
            engine.add_executor(Executor(name, agent))
            if i > 0:
                prev_name = nodes[i - 1][0]
                engine.add_edge(prev_name, name)
        return engine


class ConcurrentBuilder:
    """Creates a fan-out parallel execution graph with a fan-in barrier."""

    @staticmethod
    def build(
        session: AgentSession,
        fan_out_node: tuple[str, Any],
        worker_nodes: List[tuple[str, Any]],
        fan_in_node: tuple[str, Any],
    ) -> PregelEngine:
        engine = PregelEngine(session)
        # Add root
        engine.add_executor(Executor(fan_out_node[0], fan_out_node[1]))
        # Add fan-in barrier
        engine.add_executor(Executor(fan_in_node[0], fan_in_node[1]))

        # Add workers and wire fan-out and fan-in
        for w_name, w_agent in worker_nodes:
            engine.add_executor(Executor(w_name, w_agent))
            engine.add_edge(fan_out_node[0], w_name)
            engine.add_edge(w_name, fan_in_node[0])

        return engine


class HandoffBuilder:
    """Creates direct specialist-to-specialist routing based on intent message metadata."""

    @staticmethod
    def build(
        session: AgentSession,
        agents: List[tuple[str, Any]],
        router_fn: Optional[Callable[[AgentSession, Message], str]] = None,
    ) -> PregelEngine:
        engine = PregelEngine(session)
        for name, agent in agents:
            engine.add_executor(Executor(name, agent))

        # Wire all-to-all handoffs conditioned on message recipient
        for src_name, _ in agents:
            for dst_name, _ in agents:
                if src_name != dst_name:
                    # Edge checks if message recipient is explicitly target
                    def make_cond(target_name: str):
                        return lambda sess, msg: msg.recipient == target_name or msg.payload.get("handoff_to") == target_name
                    engine.add_edge(src_name, dst_name, make_cond(dst_name))

        return engine


class MagenticBuilder:
    """Creates a Magentic manager-led dynamic agent orchestration graph."""

    @staticmethod
    def build(
        session: AgentSession,
        orchestrator: tuple[str, Any],
        specialists: List[tuple[str, Any]],
    ) -> PregelEngine:
        engine = PregelEngine(session)
        orch_name = orchestrator[0]
        engine.add_executor(Executor(orch_name, orchestrator[1]))

        for spec_name, spec_agent in specialists:
            engine.add_executor(Executor(spec_name, spec_agent))
            # Orchestrator can delegate to specialist
            def make_to_spec_cond(target_name: str):
                return lambda sess, msg: msg.recipient == target_name
            engine.add_edge(orch_name, spec_name, make_to_spec_cond(spec_name))

            # Specialist always reports back to orchestrator
            engine.add_edge(spec_name, orch_name)

        return engine


class GroupChatBuilder:
    """
    Creates a collaborative multi-agent group chat workflow conforming to Microsoft Agent Framework.
    Supports round-robin or dynamic speaker selection with termination conditions.
    """

    @staticmethod
    def build(
        session: AgentSession,
        participants: List[tuple[str, Any]],
        selection_func: Optional[Callable[[AgentSession, Message], str]] = None,
        max_rounds: int = 10,
    ) -> PregelEngine:
        engine = PregelEngine(session, max_supersteps=max_rounds * len(participants))
        participant_names = [p[0] for p in participants]

        for name, agent in participants:
            engine.add_executor(Executor(name, agent))

        # Wire all-to-all with round-robin or custom speaker selection
        for i, (src_name, _) in enumerate(participants):
            next_name = participant_names[(i + 1) % len(participant_names)]
            for dst_name in participant_names:
                if dst_name != src_name:
                    if selection_func:
                        def make_select_cond(target: str):
                            return lambda sess, msg: selection_func(sess, msg) == target
                        engine.add_edge(src_name, dst_name, make_select_cond(dst_name))
                    else:
                        def make_rr_cond(target: str, expected_next: str):
                            return lambda sess, msg: msg.recipient == target or (msg.recipient == "group" and target == expected_next)
                        engine.add_edge(src_name, dst_name, make_rr_cond(dst_name, next_name))

        return engine
