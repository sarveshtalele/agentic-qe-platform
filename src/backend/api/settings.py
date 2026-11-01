"""Connections and settings API."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import (
    Response,
)
from pydantic import BaseModel, Field

from backend.core import auth, models
from backend.maf import agui, engine, evals, governance, llm, workflows  # noqa: F401 - workflows registers definitions
from backend.repos import github

router = APIRouter()


class TokenIn(BaseModel):
    token: str = Field(min_length=8)
    label: str = ""


class ModelIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    label: str | None = None
    enabled: bool | None = None
    is_default: bool | None = None


class GateRolesIn(BaseModel):
    roles: dict[str, list[str]]


class ZoneIn(BaseModel):
    timezone: str


class LLMIn(BaseModel):
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None


@router.get("/api/connections")
def connections():
    return github.list_credentials()


@router.post("/api/connections/github", status_code=201)
async def connect_github(body: TokenIn):
    return await github.connect(body.token.strip(), body.label)


@router.get("/api/connections/{credential_id}/repos")
async def connection_repos(credential_id: str):
    return await github.list_repos(credential_id)


@router.delete("/api/connections/{credential_id}", status_code=204)
def remove_connection(credential_id: str):
    github.delete_credential(credential_id)
    return Response(status_code=204)


@router.get("/api/settings/llm")
def llm_settings():
    if auth.current_user.get()["role"] != "admin":  # only the admin sees the endpoint; a user sees their own model
        mine = auth.describe(auth.current_user.get())
        return {"model": mine["model"] or models.system_default(llm.public()["model"]), "configured": llm.public()["configured"]}
    return llm.public()


@router.put("/api/settings/llm")
def update_llm(body: LLMIn):
    return llm.update(body.base_url, body.model, body.api_key)


@router.post("/api/settings/llm/test")
async def test_llm(body: LLMIn):
    return await llm.test_connection(body.base_url, body.model, body.api_key)


# ---- model list (admin) and what each person may pick ---------------------------

@router.get("/api/models")
def list_models():
    return models.list_models()


@router.post("/api/models", status_code=201)
def add_model(body: ModelIn):
    """Added by hand, so the admin means it: it starts enabled. Only a loaded name starts off."""
    try:
        return models.update(body.name, {}) if body.name in {m["name"] for m in models.list_models()} else models.add(body.name, body.label or "", enabled=True)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/api/models")
def patch_model(body: ModelIn):
    try:
        return models.update(body.name, body.model_dump(exclude={"name"}, exclude_none=True))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/api/models", status_code=204)
def delete_model(name: str):
    try:
        models.remove(name)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return Response(status_code=204)


@router.post("/api/models/load")
async def load_models():
    """Lists the names the proxy offers. They are added switched off: a listed name may not work, so each needs its Test and an explicit switch on."""
    listed = await llm.proxy_models()
    known = {m["name"] for m in models.list_models()}
    for name in listed:
        if name not in known:
            models.add(name)
    return {"listed": len(listed), "added": [n for n in listed if n not in known], "models": models.list_models()}


@router.post("/api/models/tool-check")
async def check_model_tools(body: ModelIn):
    """One real tool-call round trip through the endpoint (`llm.tool_check`). The result is kept on the model row."""
    models.get(body.name)  # 404 for a name that is not in the list
    return await llm.tool_check(body.name)


@router.get("/api/settings/models")
def my_models():
    """Only models this person may use, for the run forms and chat. The default marks what applies when nothing is picked."""
    user = auth.describe(auth.current_user.get())
    checks = models.tool_checks()
    if user["role"] == "admin":
        names = [m["name"] for m in models.list_models() if m["enabled"]]
        return {"models": names, "default": models.system_default(llm.public()["model"]), "tools": {n: checks[n] for n in names if n in checks}}
    allowed = models.allowed(user["id"])
    return {"models": allowed, "default": user["model"] if user["model"] in allowed else "", "tools": {n: checks[n] for n in allowed if n in checks}}


@router.get("/api/settings/gate-roles")
def get_gate_roles():
    """Which roles may sign each gate. A gate not listed may be signed by anyone who can write."""
    return {"roles": {str(g): r for g, r in auth.gate_roles().items()}, "assignable": [r for r in auth.ROLES if r != "viewer"]}


@router.put("/api/settings/gate-roles")
def put_gate_roles(body: GateRolesIn):
    try:
        auth.set_gate_roles(body.roles)
    except auth.AuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    return get_gate_roles()


@router.get("/api/settings/timezone")
def get_timezone():
    return {"timezone": models.timezone_name()}


@router.put("/api/settings/timezone")
def set_timezone(body: ZoneIn):
    try:
        return {"timezone": models.set_timezone(body.timezone)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/usage")
def usage(days: int = 30, format: str = "json"):
    """Admin only (rule in core/auth.py). Everything comes from recorded calls; with none, the lists are empty."""
    days = max(1, min(days, 366))
    found = models.usage_rows(days)
    names = auth.display_names({r["user_id"] for r in found if r["user_id"]})
    for item in found:
        item["user"] = names.get(item["user_id"], item["user_id"] or "(not recorded)")
    if format == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["day", "user", "model", "agent", "calls", "tokens_in", "tokens_out"])
        for r in found:
            writer.writerow([r["day"], r["user"], r["model"] or "(not recorded)", r["agent"], r["calls"], r["tokens_in"], r["tokens_out"]])
        return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="usage-{days}d.csv"'})

    def total(key: str) -> list[dict]:
        sums: dict[str, int] = {}
        for r in found:
            label = r[key] or "(not recorded)"
            sums[label] = sums.get(label, 0) + r["tokens_in"] + r["tokens_out"]
        return [{"name": k, "tokens": v} for k, v in sorted(sums.items(), key=lambda kv: -kv[1])]

    by_day = total("day")
    return {"days": days, "timezone": models.timezone_name(), "calls": sum(r["calls"] for r in found), "tokens": sum(r["tokens_in"] + r["tokens_out"] for r in found),
            "by_user": total("user"), "by_model": total("model"), "by_agent": total("agent"), "by_day": sorted(by_day, key=lambda r: r["name"])}
