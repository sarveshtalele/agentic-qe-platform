"""Sign-in and user management."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from backend.core import auth

router = APIRouter()
DATE = r"^\d{4}-\d{2}-\d{2}$|^$"


class LoginIn(BaseModel):
    username: str = Field(max_length=200)
    password: str = Field(max_length=500)


class ModelLimit(BaseModel):
    model: str
    period: str
    tokens: int = Field(ge=0)


class UserIn(BaseModel):
    username: str = Field(max_length=60)
    password: str = Field(max_length=500)
    model: str = ""
    models: list[str] | None = None
    role: str = "developer"
    token_limit: int | None = Field(default=None, ge=0)
    active_from: str | None = Field(default=None, pattern=DATE)
    active_until: str | None = Field(default=None, pattern=DATE)


class PasswordIn(BaseModel):
    current_password: str = Field(max_length=500)
    new_password: str = Field(max_length=500)


class UserPatch(BaseModel):
    model_config = ConfigDict(protected_namespaces=())  # model_limits is a field of ours, not a pydantic setting
    password: str | None = Field(default=None, max_length=500)
    role: str | None = None
    model: str | None = None
    models: list[str] | None = None
    limits: dict[str, int | None] | None = None
    model_limits: list[ModelLimit] | None = None
    token_limit: int | None = Field(default=None, ge=0)
    active_from: str | None = Field(default=None, pattern=DATE)
    active_until: str | None = Field(default=None, pattern=DATE)
    enabled: bool | None = None


@router.get("/api/auth/status")
def status():
    return {"configured": auth.admin_configured()}


@router.post("/api/auth/login")
def login(body: LoginIn, request: Request, response: Response):
    if not auth.admin_configured():
        raise HTTPException(503, "Sign-in is not set up. Add ATLAS_ADMIN_USERNAME and ATLAS_ADMIN_PASSWORD to .env, then restart")
    try:
        token = auth.login(body.username, body.password)
    except auth.AuthError as exc:
        raise HTTPException(401, str(exc)) from exc
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    response.set_cookie(auth.COOKIE, token, httponly=True, samesite="strict", secure=secure, max_age=auth.SESSION_HOURS * 3600, path="/")
    return auth.describe(auth.session_user(token))


@router.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response):
    if token := request.cookies.get(auth.COOKIE):
        auth.logout(token)
    response.delete_cookie(auth.COOKIE, path="/")


@router.get("/api/auth/me")
def me():
    return auth.describe(auth.current_user.get())


@router.get("/api/auth/events")
def events():
    return auth.recent_events()


@router.get("/api/users")
def list_users():
    return auth.list_users()


@router.post("/api/users", status_code=201)
def create_user(body: UserIn):
    try:
        return auth.create_user(body.username, body.password, body.model, body.token_limit, body.active_from, body.active_until, body.models, body.role)
    except auth.AuthError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/api/users/{user_id}")
def update_user(user_id: str, body: UserPatch):
    try:
        return auth.update_user(user_id, body.model_dump(exclude_unset=True))  # model_limits become plain dicts
    except auth.AuthError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/api/account/password", status_code=204)
def change_password(body: PasswordIn, request: Request):
    """Needs the current password. Other sessions of this account end. The body is never logged."""
    try:
        auth.change_password(auth.signer(), body.current_password, body.new_password, request.cookies.get(auth.COOKIE))
    except auth.Forbidden:
        raise
    except auth.AuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    return Response(status_code=204)
