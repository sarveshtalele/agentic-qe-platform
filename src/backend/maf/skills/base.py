from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine, Dict, List, Optional, Type


class AgentSkill(ABC):
    """
    Base class for Microsoft Agent Framework (MAF) Agent Skills.
    Matches AIFunction / AITool pattern from Microsoft.Extensions.AI / agent-framework.pdf.
    """

    def __init__(self, name: str, description: str, category: str = "QualityEngineering"):
        self.name = name
        self.description = description
        self.category = category

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the skill against the given session context or payload."""
        raise NotImplementedError

    def to_descriptor(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
        }


class SkillRegistry:
    """Central registry for discovering and resolving MAF agent skills."""
    _registry: Dict[str, AgentSkill] = {}

    @classmethod
    def register(cls, skill: AgentSkill) -> AgentSkill:
        cls._registry[skill.name] = skill
        return skill

    @classmethod
    def get(cls, name: str) -> Optional[AgentSkill]:
        return cls._registry.get(name)

    @classmethod
    def list_all(cls) -> List[Dict[str, Any]]:
        return [s.to_descriptor() for s in cls._registry.values()]


def maf_skill(name: str, description: str, category: str = "QualityEngineering"):
    """Decorator to register a function or class as an executable MAF skill."""
    def decorator(cls_or_fn: Any):
        if inspect.isclass(cls_or_fn):
            instance = cls_or_fn()
            SkillRegistry.register(instance)
            return cls_or_fn
        else:
            class FuncSkill(AgentSkill):
                def __init__(self):
                    super().__init__(name=name, description=description, category=category)

                async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
                    if inspect.iscoroutinefunction(cls_or_fn):
                        return await cls_or_fn(context)
                    return cls_or_fn(context)

            instance = FuncSkill()
            SkillRegistry.register(instance)
            return cls_or_fn
    return decorator
