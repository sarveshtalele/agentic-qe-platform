"""Connections and settings API."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import (
    Response,
)
from pydantic import BaseModel, Field

from backend.maf import agui, engine, evals, governance, llm, workflows  # noqa: F401 - workflows registers definitions
from backend.repos import github

router = APIRouter()


class TokenIn(BaseModel):
    token: str = Field(min_length=8)
    label: str = ""


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
    return llm.public()


@router.put("/api/settings/llm")
def update_llm(body: LLMIn):
    return llm.update(body.base_url, body.model, body.api_key)


@router.post("/api/settings/llm/test")
async def test_llm(body: LLMIn):
    return await llm.test_connection(body.base_url, body.model, body.api_key)
