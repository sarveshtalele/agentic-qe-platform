"""Skills in chat. Tools are unreliable through the proxy, so by default code picks the skill and adds its text to the turn.

On a model whose live tool check passed (`llm.tool_check`), MAF's `SkillsProvider` is used instead and the model loads skills itself.
"""
from __future__ import annotations

import logging

from agent_framework import (
    Agent,
    ContextProvider,
    Content,
    FileSkillsSource,
    FilteringSkillsSource,
    Message,
    SkillsProvider,
)
from pydantic import BaseModel

from backend.config import MODEL_NO_CACHE, SKILLS_DIR
from backend.core import models, prompts
from backend.core import skills as skill_lib
from backend.maf import governance, llm

log = logging.getLogger("aqe.chat")
PICK_MAX_TOKENS = 1000  # a reasoning model spends part of this thinking; the answer itself is a few tokens
_picked: dict[tuple[str, str], list[str]] = {}  # (thread, message id) to the skills chosen, so a message is asked about once
_PICKED_MAX = 500


class SkillPick(BaseModel):
    skill: str = ""  # a skill name, or "" when none applies


def mode(agent_key: str, model: str) -> str:
    """'none' (the agent has no skills), 'provider' (this model passed the tool check) or 'pick' (code chooses and injects)."""
    if not skill_lib.for_agent(agent_key):
        return "none"
    return "provider" if models.tool_status(model) == "passed" else "pick"


def provider(agent_key: str) -> SkillsProvider:
    """MAF's own skills feature, limited to this agent's skills. No script runner, and no approval pause for reading a skill."""
    allowed = set(skill_lib.for_agent(agent_key))
    source = FilteringSkillsSource(FileSkillsSource([SKILLS_DIR]), lambda skill, _context: skill.frontmatter.name in allowed)
    return SkillsProvider(source, disable_load_skill_approval=True, disable_read_skill_resource_approval=True)


class SkillText(ContextProvider):
    """Adds the chosen skill text ahead of the user's message for this turn only. It is not stored in the thread."""

    def __init__(self, text: str):
        super().__init__("chosen-skill")
        self.text = text

    async def before_run(self, *, agent, session, context, state) -> None:
        context.extend_messages(self.source_id, [Message(role="user", contents=[Content.from_text(self.text)])])


async def pick(agent_key: str, project_id: str, user_id: str | None, model: str, message: str, *, key: tuple[str, str] | None = None) -> list[str]:
    """One small structured call: which of this agent's skills, if any, applies to the message. Any failure means no skill, never a failed chat.

    The call is made through the same telemetry as other model calls, so its tokens count against the user (source `chat-skill`).
    `key` is (thread, message id): asking again for the same message returns the first answer without another call.
    """
    names = skill_lib.for_agent(agent_key)
    if not names or not message.strip():
        return []
    if key and key in _picked:
        return _picked[key]
    from backend.maf import runtime  # late: runtime imports this module

    listing = "\n".join(f"- {n}: {skill_lib.get(n).description}" for n in names)
    instructions = ("You decide which skill, if any, applies to a user's message. Choose one only when the message clearly asks for what the skill does; "
                    f"otherwise choose none.\nSkills:\n{listing}")
    options: dict = {"max_tokens": PICK_MAX_TOKENS}
    if MODEL_NO_CACHE:
        options["extra_body"] = {"cache": {"no-cache": True}}
    chosen: list[str] = []
    try:
        agent = Agent(client=llm.client(model), name=f"{agent_key}-skill-pick", instructions=instructions, default_options=options,
                      middleware=[governance.telemetry(agent_key, project_id, None, "chat-skill", model, user_id, prompts.ref(agent_key))])
        response = await agent.run(f"User message:\n{message[:2000]}\n\n{runtime.format_rule(SkillPick)}")
        name = SkillPick.model_validate(runtime.extract_json(response.text or "", ("skill",))).skill.strip()
        if name in names:
            chosen = [name]
        elif name and name.lower() not in {"none", "null"}:
            log.warning("skill pick for %s named %r, which this agent does not have; no skill used", agent_key, name[:60])
    except Exception as exc:  # the answer to the user must not depend on this call
        log.warning("skill pick failed for %s, chat continues without a skill: %s", agent_key, str(exc)[:200] or type(exc).__name__)
    if key:
        if len(_picked) >= _PICKED_MAX:
            _picked.pop(next(iter(_picked)))
        _picked[key] = chosen
    return chosen
