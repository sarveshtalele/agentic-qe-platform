from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Union


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Message:
    """Core MAF message envelope passed between agents and executors."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = "user"
    recipient: str = "orchestrator"
    content: str = ""
    kind: str = "chat"  # chat | thought | tool_call | tool_result | interrupt | state_patch
    payload: Dict[str, Any] = field(default_factory=dict)
    superstep: int = 0
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HITLInterrupt:
    """Represents a human-in-the-loop interruption request (RequestInfoEvent)."""
    control_id: str
    action_type: str
    target: str
    details: Dict[str, Any]
    nonce: str
    reason: str


class AgentSession:
    """Maintains runtime state bag, message history, and execution context."""

    def __init__(
        self,
        session_id: str,
        project_id: str,
        workflow_type: str = "magentic",
        initial_state: Optional[Dict[str, Any]] = None,
    ):
        self.session_id = session_id
        self.project_id = project_id
        self.workflow_type = workflow_type
        self.superstep_index = 0
        self.status = "IDLE"  # IDLE | RUNNING | WAITING_APPROVAL | COMPLETED | FAILED
        self.state_bag: Dict[str, Any] = initial_state or {}
        self.messages: List[Message] = []
        self.pending_interrupt: Optional[HITLInterrupt] = None
        self.event_listeners: List[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = []

    def set_state(self, key: str, value: Any) -> None:
        self.state_bag[key] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        return self.state_bag.get(key, default)

    def add_message(self, message: Message) -> None:
        message.superstep = self.superstep_index
        self.messages.append(message)

    async def emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        event = {
            "id": str(uuid.uuid4()),
            "event": event_type,
            "data": data,
            "session_id": self.session_id,
            "project_id": self.project_id,
            "superstep": self.superstep_index,
            "timestamp": now_iso(),
        }
        for listener in self.event_listeners:
            try:
                await listener(event)
            except Exception:
                pass


class AIAgent:
    """Base class for specialist AI Agents conforming to MAF specs."""

    def __init__(
        self,
        name: str,
        role: str,
        description: str,
        system_prompt: str,
        skills: Optional[List[Any]] = None,
    ):
        self.name = name
        self.role = role
        self.description = description
        self.system_prompt = system_prompt
        self.skills: List[Any] = list(skills) if skills else []

    def add_skill(self, skill: Any) -> None:
        """Attaches an executable MAF AgentSkill or AITool to the agent."""
        self.skills.append(skill)

    def get_skill(self, name: str) -> Optional[Any]:
        """Resolves an attached skill by its registered name."""
        for s in self.skills:
            if getattr(s, "name", "") == name:
                return s
        return None

    def list_skills(self) -> List[Dict[str, Any]]:
        """Returns descriptors for all skills attached to this agent."""
        return [
            s.to_descriptor() if hasattr(s, "to_descriptor") else {"name": getattr(s, "name", str(s))}
            for s in self.skills
        ]

    async def process(self, session: AgentSession, inbound_msg: Message) -> List[Message]:
        """Processes an incoming message and returns response messages."""
        raise NotImplementedError


class Executor:
    """Node in the MAF Pregel Graph execution engine."""

    def __init__(self, name: str, agent_or_fn: Union[AIAgent, Callable[[AgentSession, Message], Coroutine[Any, Any, List[Message]]]]):
        self.name = name
        self.agent_or_fn = agent_or_fn
        self.inbox: List[Message] = []

    async def execute(self, session: AgentSession) -> List[Message]:
        if not self.inbox:
            return []
        # Process pending messages in this superstep
        msgs_to_process = list(self.inbox)
        self.inbox.clear()

        out_msgs: List[Message] = []
        for msg in msgs_to_process:
            if isinstance(self.agent_or_fn, AIAgent):
                res = await self.agent_or_fn.process(session, msg)
            else:
                res = await self.agent_or_fn(session, msg)
            if res:
                out_msgs.extend(res)
        return out_msgs


class Edge:
    """Routing path between executors."""

    def __init__(
        self,
        source: str,
        target: str,
        condition: Optional[Callable[[AgentSession, Message], bool]] = None,
    ):
        self.source = source
        self.target = target
        self.condition = condition

    def matches(self, session: AgentSession, msg: Message) -> bool:
        if self.condition is None:
            return True
        return self.condition(session, msg)


class PregelEngine:
    """
    Executes an MAF Graph in deterministic Pregel Supersteps with barrier synchronization.
    """

    def __init__(self, session: AgentSession, max_supersteps: int = 25):
        self.session = session
        self.executors: Dict[str, Executor] = {}
        self.edges: List[Edge] = []
        self.max_supersteps = max_supersteps

    def add_executor(self, executor: Executor) -> None:
        self.executors[executor.name] = executor

    def add_edge(self, source: str, target: str, condition: Optional[Callable[[AgentSession, Message], bool]] = None) -> None:
        self.edges.append(Edge(source, target, condition))

    async def step(self) -> bool:
        """Executes a single Pregel superstep across active executors with barrier sync."""
        active_executors = [ex for ex in self.executors.values() if ex.inbox]
        if not active_executors:
            self.session.status = "COMPLETED"
            return False

        self.session.superstep_index += 1
        current_step = self.session.superstep_index
        outbox: List[Tuple[str, Message]] = []

        for executor in active_executors:
            msgs = await executor.execute(self.session)
            for m in msgs:
                m.superstep = current_step
                self.session.add_message(m)
                outbox.append((executor.name, m))

        for src_name, msg in outbox:
            for edge in self.edges:
                if edge.source == src_name and edge.should_route(self.session, msg):
                    if edge.target in self.executors:
                        self.executors[edge.target].inbox.append(msg)
        return True

    async def run(self, initial_node: str, initial_msg: Message) -> None:
        """Runs the Pregel execution loop."""
        if initial_node not in self.executors:
            raise ValueError(f"Unknown initial node '{initial_node}'")

        self.session.status = "RUNNING"
        self.executors[initial_node].inbox.append(initial_msg)
        self.session.add_message(initial_msg)

        await self.session.emit_event("status_update", {
            "status": "RUNNING",
            "active_node": initial_node,
            "message": f"Starting workflow at node {initial_node}",
        })

        while self.session.status == "RUNNING" and self.session.superstep_index < self.max_supersteps:
            # Check if any executor has pending messages
            active_executors = [ex for ex in self.executors.values() if ex.inbox]
            if not active_executors:
                self.session.status = "COMPLETED"
                await self.session.emit_event("status_update", {
                    "status": "COMPLETED",
                    "message": "Workflow completed cleanly with no pending messages.",
                })
                break

            self.session.superstep_index += 1
            current_step = self.session.superstep_index

            await self.session.emit_event("workflow_step_complete", {
                "superstep": current_step,
                "active_nodes": [ex.name for ex in active_executors],
            })

            # Execute active nodes in parallel or sequence
            outbox: List[Tuple[str, Message]] = []
            for executor in active_executors:
                await self.session.emit_event("status_update", {
                    "status": "EXECUTING",
                    "active_node": executor.name,
                    "superstep": current_step,
                })
                try:
                    msgs = await executor.execute(self.session)
                    for m in msgs:
                        m.superstep = current_step
                        self.session.add_message(m)
                        outbox.append((executor.name, m))
                        # Check for HITL interrupt
                        if m.kind == "interrupt" and self.session.pending_interrupt:
                            self.session.status = "WAITING_APPROVAL"
                            await self.session.emit_event("approval_required", {
                                "nonce": self.session.pending_interrupt.nonce,
                                "control_id": self.session.pending_interrupt.control_id,
                                "action_type": self.session.pending_interrupt.action_type,
                                "target": self.session.pending_interrupt.target,
                                "details": self.session.pending_interrupt.details,
                                "reason": self.session.pending_interrupt.reason,
                            })
                            return
                except Exception as e:
                    self.session.status = "FAILED"
                    await self.session.emit_event("status_update", {
                        "status": "FAILED",
                        "error": str(e),
                        "node": executor.name,
                    })
                    return

            # Barrier Synchronization & Message Routing for next superstep
            for src_name, msg in outbox:
                # Find matching edges
                routed = False
                for edge in self.edges:
                    if edge.source == src_name and edge.matches(self.session, msg):
                        if edge.target in self.executors:
                            self.executors[edge.target].inbox.append(msg)
                            routed = True

        if self.session.superstep_index >= self.max_supersteps and self.session.status == "RUNNING":
            self.session.status = "COMPLETED"
            await self.session.emit_event("status_update", {
                "status": "COMPLETED",
                "message": f"Reached maximum superstep limit ({self.max_supersteps}).",
            })
