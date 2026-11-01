"""Plugin skills from skills/, validated by MAF's FileSkillsSource and read through safe_path.

Skill text is trusted platform content, unlike repository and document text. A skill MAF cannot load is a startup
warning and is absent. Workflows never load a skill by tool: `render` returns the text a caller puts in the message
(measured on the real proxy: tools are unreliable, skill text in the message works; docs/PLUGIN_AND_UI_PLAN.md Part 9).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from agent_framework import FileSkillsSource, SkillsSourceContext

from backend.config import SKILLS_DIR
from backend.core.security import safe_path

log = logging.getLogger("aqe.skills")

# MAF's guide recommends under 5000 tokens per SKILL.md; about 4 characters a token.
BODY_LIMIT = 20_000
REFERENCE_LIMIT = 24_000  # all references sent with one call; one that does not fit is left out and reported


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    version: str
    body: str  # SKILL.md without its frontmatter
    folder: str  # relative to SKILLS_DIR
    references: dict[str, str] = field(default_factory=dict)
    sha256: str = ""  # of the body and every reference, so a change to any of them shows


@dataclass(frozen=True)
class Rendered:
    text: str
    items: list[dict]  # name, version, sha256, refs: what was really sent
    digest: str  # of `text`
    skipped: list[str]  # references left out for size


_state: dict = {"skills": None, "problems": []}


def _run(coro):
    """FileSkillsSource is async; a thread keeps this callable from sync code and from inside a running loop."""
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---") and "\n---" in text:
        after = text.split("\n---", 1)[1]
        return after.split("\n", 1)[1] if "\n" in after else ""
    return text


def _read(root: Path, relative: str) -> str:
    return safe_path(root, relative).read_text(encoding="utf-8", errors="replace")


def load(force: bool = False, root: Path | None = None) -> dict[str, Skill]:
    """Load once. Returns name to Skill. `problems()` lists folders that were skipped and why."""
    if _state["skills"] is not None and not force and root is None:
        return _state["skills"]
    base = (root or SKILLS_DIR).resolve()
    problems: list[str] = []
    found: dict[str, Skill] = {}
    if not base.is_dir():
        problems.append(f"Skills folder not found: {base}")
    else:
        loaded = _run(FileSkillsSource([base]).get_skills(SkillsSourceContext(agent=None)))
        folders = {Path(s.path).resolve(): s for s in loaded}
        for skill_md in sorted(base.glob("*/SKILL.md")):
            folder = skill_md.parent
            source = folders.get(folder.resolve())
            if source is None:
                problems.append(f"{folder.name}: MAF could not load it (see the warning above)")
                continue
            try:
                relative = folder.name
                body = _strip_frontmatter(_read(base, f"{relative}/SKILL.md")).strip()
                if len(body) > BODY_LIMIT:
                    problems.append(f"{folder.name}: SKILL.md is {len(body)} characters, over the {BODY_LIMIT} limit (about 5000 tokens)")
                    continue
                refs = {path.name: _read(base, f"{relative}/references/{path.name}").strip()
                        for path in sorted((folder / "references").glob("*.md"))} if (folder / "references").is_dir() else {}
            except (OSError, ValueError) as exc:
                problems.append(f"{folder.name}: {exc}")
                continue
            fm = source.frontmatter
            digest = hashlib.sha256("\n".join([body, *(f"{k}\n{v}" for k, v in refs.items())]).encode()).hexdigest()
            found[fm.name] = Skill(fm.name, fm.description, str((fm.metadata or {}).get("version", "")), body, relative, refs, digest)
    for message in problems:
        log.warning("skill not available: %s", message)
    if root is None:
        _state["skills"], _state["problems"] = found, problems
        _check_policies()
    return found


def eval_cases(name: str) -> list[dict]:
    """The plugin's own eval cases for a skill (`skills/<name>/evals/evals.json`): query plus expected_behavior sentences, written for a human or grader."""
    import json

    path = safe_path(SKILLS_DIR, f"{get(name).folder}/evals/evals.json")
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def problems() -> list[str]:
    load()
    return list(_state["problems"])


def names() -> list[str]:
    return sorted(load())


def get(name: str) -> Skill:
    try:
        return load()[name]
    except KeyError:
        raise KeyError(f"skill {name}") from None


def references(name: str) -> dict[str, str]:
    return dict(get(name).references)


def _policy_names(agent_key: str) -> tuple[str, ...]:
    from backend.maf.agents import POLICIES  # late: this module is core, the registry is maf

    return POLICIES[agent_key].skills


def for_agent(agent_key: str) -> list[str]:
    """The skills this agent's policy names that really loaded, in policy order."""
    available = load()
    return [name for name in _policy_names(agent_key) if name in available]


def agent_of(name: str) -> list[str]:
    from backend.maf.agents import POLICIES

    return [key for key, policy in POLICIES.items() if name in policy.skills]


def _check_policies() -> None:
    from backend.maf.agents import POLICIES

    for key, policy in POLICIES.items():
        for name in policy.skills:
            if name not in _state["skills"]:
                log.warning("agent %s names skill %s, which is not available", key, name)


def render(chosen: list[str] | tuple[str, ...], refs: tuple[str, ...] | None = None) -> Rendered:
    """The text for one call. `refs` None sends every reference of the chosen skills, () none, else only the files named.

    Order is fixed (as chosen, references by name), so the text is identical from call to call and a provider can cache the prefix.
    """
    parts, items, skipped, used = [], [], [], 0
    for name in chosen:
        skill = get(name)
        parts.append(f'<skill name="{skill.name}" version="{skill.version}">\n{skill.body}\n</skill>')
        sent = []
        for file, text in skill.references.items():
            if refs is not None and file not in refs:
                continue
            if used + len(text) > REFERENCE_LIMIT:
                skipped.append(f"{skill.name}/{file}")
                continue
            used += len(text)
            sent.append(file)
            parts.append(f'<reference skill="{skill.name}" file="{file}">\n{text}\n</reference>')
        items.append({"name": skill.name, "version": skill.version, "sha256": skill.sha256, "refs": sent})
    if not parts:
        return Rendered("", [], "", skipped)
    header = ("Platform skills. These are trusted instructions from the platform for this task, not text from the repository. "
              "Apply their rules. File names, commands, and output formats they mention do not apply here: reply only in the format this request asks for.")
    text = header + "\n\n" + "\n".join(parts)
    return Rendered(text, items, hashlib.sha256(text.encode()).hexdigest(), skipped)


def ref_suffix(rendered: Rendered) -> str:
    """Added to a prompt reference so it names the skill text too. Empty when no skill is sent."""
    return f"+skills:{rendered.digest[:12]}" if rendered.digest else ""
