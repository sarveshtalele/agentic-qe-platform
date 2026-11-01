"""GitHub REST calls for private-repo connection. A token validates, lists repos, and opens PRs."""
from __future__ import annotations

import re

import httpx

from backend.core.security import decrypt, encrypt
from backend.db import db, new_id, now, row, rows

API = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


async def _call(method: str, path: str, token: str, **kwargs) -> httpx.Response:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(method, API + path, headers=_headers(token), **kwargs)
    if response.status_code >= 400:
        detail = response.json().get("message", response.text[:200]) if response.headers.get("content-type", "").startswith("application/json") else response.text[:200]
        raise GitHubError(f"GitHub {response.status_code}: {detail}")
    return response


async def connect(token: str, label: str) -> dict:
    """Validate the token against GitHub first, so a bad token is never stored."""
    response = await _call("GET", "/user", token)
    login = response.json()["login"]
    credential_id = new_id("cred")
    with db() as con:
        con.execute("INSERT INTO credentials VALUES (?,?,?,?,?,?,?)", (credential_id, "github", label or login, login, encrypt(token), response.headers.get("x-oauth-scopes", ""), now()))
    return public(credential_id)


def public(credential_id: str) -> dict:
    with db() as con:
        found = row(con.execute("SELECT id, provider, label, login, scopes, created_at FROM credentials WHERE id=?", (credential_id,)))
    if not found:
        raise KeyError(credential_id)
    return found


def list_credentials() -> list[dict]:
    with db() as con:
        return rows(con.execute("SELECT id, provider, label, login, scopes, created_at FROM credentials ORDER BY created_at DESC"))


def token_for(credential_id: str | None) -> str | None:
    if not credential_id:
        return None
    with db() as con:
        found = con.execute("SELECT secret FROM credentials WHERE id=?", (credential_id,)).fetchone()
    if not found:
        raise KeyError(credential_id)
    return decrypt(found["secret"])


def delete_credential(credential_id: str) -> None:
    with db() as con:
        con.execute("DELETE FROM credentials WHERE id=?", (credential_id,))


async def list_repos(credential_id: str) -> list[dict]:
    response = await _call("GET", "/user/repos", token_for(credential_id), params={"per_page": 100, "sort": "pushed"})
    return [{"full_name": r["full_name"], "private": r["private"], "default_branch": r["default_branch"], "clone_url": r["clone_url"], "pushed_at": r["pushed_at"], "language": r["language"]} for r in response.json()]


def parse_slug(url: str) -> tuple[str, str] | None:
    match = re.match(r"https://github\.com/([^/]+)/([^/.]+?)(?:\.git)?/?$", url.strip())
    return (match.group(1), match.group(2)) if match else None


async def merge_pr(token: str, owner: str, repo: str, number: int) -> dict:
    response = await _call("PUT", f"/repos/{owner}/{repo}/pulls/{number}/merge", token, json={"merge_method": "squash"})
    return {"merged": response.json().get("merged", False), "sha": response.json().get("sha", "")}


async def open_pr(token: str, owner: str, repo: str, head: str, base: str, title: str, body: str) -> dict:
    response = await _call("POST", f"/repos/{owner}/{repo}/pulls", token, json={"title": title, "head": head, "base": base, "body": body})
    pr = response.json()
    return {"number": pr["number"], "url": pr["html_url"], "state": pr["state"]}
