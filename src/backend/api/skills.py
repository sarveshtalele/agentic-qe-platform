"""Skills API, read only. The skills are the plugin folders under skills/, validated by MAF at startup."""
from __future__ import annotations

from fastapi import APIRouter

from backend.core import skills

router = APIRouter()


def _summary(skill: skills.Skill) -> dict:
    return {"name": skill.name, "description": skill.description, "version": skill.version, "agents": skills.agent_of(skill.name), "references": sorted(skill.references),
            "chars": len(skill.body) + sum(len(t) for t in skill.references.values()), "sha256": skill.sha256}


@router.get("/api/skills")
def list_skills():
    return {"skills": [_summary(skills.get(n)) for n in skills.names()], "problems": skills.problems()}


@router.get("/api/skills/{name}")
def get_skill(name: str):
    skill = skills.get(name)  # KeyError is a 404
    return {**_summary(skill), "body": skill.body, "reference_text": skill.references}
