"""Model provider settings. Environment wins on first run; the Settings page can override and encrypts the key."""
from __future__ import annotations

import json
import os
import secrets
import time

import httpx
from agent_framework.openai import OpenAIChatCompletionClient
from openai import AsyncOpenAI

from backend.config import MODEL_TIMEOUT
from backend.core import models
from backend.core.errors import ModelEndpointError
from backend.core.security import decrypt, encrypt, redact
from backend.db import db


class LLMNotConfigured(ModelEndpointError):
    pass


def _get(key: str) -> str:
    with db() as con:
        found = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return found["value"] if found else ""


def _set(key: str, value: str) -> None:
    with db() as con:
        con.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, value))


def current() -> dict:
    stored_key = _get("llm_api_key")
    api_key = decrypt(stored_key.encode()) if stored_key else os.environ.get("OPENAI_API_KEY", "")
    return {
        "base_url": _get("llm_base_url") or os.environ.get("OPENAI_BASE_URL", ""),
        "model": _get("llm_model") or os.environ.get("DEFAULT_MODEL", ""),
        "api_key": api_key,
    }


def public() -> dict:
    cfg = current()
    key = cfg.pop("api_key")
    return {**cfg, "has_api_key": bool(key), "api_key_hint": f"…{key[-4:]}" if len(key) > 8 else "", "configured": bool(key and cfg["model"])}


def update(base_url: str | None, model: str | None, api_key: str | None) -> dict:
    if base_url is not None:
        _set("llm_base_url", base_url.strip().rstrip("/"))
    if model is not None:
        _set("llm_model", model.strip())
    if api_key:
        _set("llm_api_key", encrypt(api_key.strip()).decode())
    return public()


_override = None


def set_client_override(client) -> None:
    """Test seam: tests inject a scripted MAF chat client. Production code never calls this."""
    global _override
    _override = client


def client(model: str = ""):
    """A project owner's allocated model replaces the default. All models share the configured endpoint and key."""
    if _override is not None:
        return _override
    cfg = current()
    cfg["model"] = model or cfg["model"]
    if not cfg["api_key"] or not cfg["model"]:
        raise LLMNotConfigured("No model configured. Open Settings and set the base URL, model, and API key.")
    # MAF allows 100 tool rounds by default. Long tool loops outgrow model context, so agents get a hard limit.
    # a hung model call must fail the run with a clear error, not leave it running forever
    http = AsyncOpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"] or None, timeout=MODEL_TIMEOUT, max_retries=1)
    return OpenAIChatCompletionClient(model=cfg["model"], async_client=http,
                                      function_invocation_configuration={"max_iterations": 10, "max_function_calls": 30})


async def test_connection(base_url: str | None = None, model: str | None = None, api_key: str | None = None) -> dict:
    """Send a real one-word completion. Reports the measured latency and the model's real reply."""
    cfg = current()
    base, name, key = (base_url or cfg["base_url"] or "https://api.openai.com/v1").rstrip("/"), model or cfg["model"], api_key or cfg["api_key"]
    if not key or not name:
        return {"ok": False, "error": "Model name and API key are required"}
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=60) as http:
            response = await http.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {key}"},
                                       json={"model": name, "messages": [{"role": "user", "content": "Reply with the single word PONG."}], "max_tokens": 200})
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"Cannot reach {base}: {str(exc) or type(exc).__name__}"}
    latency = int((time.perf_counter() - started) * 1000)
    if response.status_code != 200:
        return {"ok": False, "error": f"HTTP {response.status_code}: {response.text[:300]}", "latency_ms": latency}
    body = response.json()
    choice = (body.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    reply = (message.get("content") or message.get("reasoning_content") or "").strip()
    usage = body.get("usage") or {}
    result = {"model": name, "latency_ms": latency, "reply": reply[:80], "finish_reason": choice.get("finish_reason") or "", "tokens": (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)}
    if not reply:  # a name the proxy lists is not proof that it answers
        return {**result, "ok": False, "error": f"{name} answered with nothing (finish reason: {result['finish_reason'] or 'none'}). It is listed but does not work here with a short reply."}
    return {**result, "ok": True}


async def proxy_models() -> list[str]:
    """Names the configured endpoint lists at /models. A * entry stands for a pattern, not a model, so it is dropped. Listing a name does not mean it works."""
    cfg = current()
    if not cfg["api_key"]:
        raise LLMNotConfigured("No API key configured. Save the base URL and API key first.")
    base = (cfg["base_url"] or "https://api.openai.com/v1").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.get(f"{base}/models", headers={"Authorization": f"Bearer {cfg['api_key']}"})
    except httpx.HTTPError as exc:
        raise ModelEndpointError(f"Cannot reach {base}: {str(exc) or type(exc).__name__}") from exc
    if response.status_code != 200:
        raise ModelEndpointError(f"The endpoint answered HTTP {response.status_code} for /models: {response.text[:200]}")
    found = {str(item.get("id") or "").strip() for item in response.json().get("data", []) if isinstance(item, dict)}
    return sorted(name for name in found if name and "*" not in name)


TOOL_CHECK_MAX_TOKENS = 2000  # 400 left Claude and GPT models with nothing: reasoning used the whole limit


def _scrubbed(text: str, key: str) -> str:
    return redact(text.replace(key, "[key]") if key else text)[:300]


async def tool_check(model: str, *, max_tokens: int = TOOL_CHECK_MAX_TOKENS, transport: httpx.AsyncBaseTransport | None = None) -> dict:
    """One real tool-call round trip through the endpoint, to see whether this model can use tools here.

    The model is offered one tool with a unique name. The tool's reply holds a unique token. It passes only if the model called
    exactly that tool and its final reply holds the token. Measured on 2026-11-01, models called tools never offered and ignored
    tool results, so a name on the proxy's list proves nothing. The result is stored on the model row. `transport` is a test seam.
    """
    cfg = current()
    base, key = (cfg["base_url"] or "https://api.openai.com/v1").rstrip("/"), cfg["api_key"]
    if not key:
        raise LLMNotConfigured("No API key configured. Save the base URL and API key first.")
    tool, token = f"aqe_probe_{secrets.token_hex(4)}", f"AQE-{secrets.token_hex(6)}"
    tools = [{"type": "function", "function": {"name": tool, "description": "Returns a short reference value for this check.", "parameters": {"type": "object", "properties": {}}}}]
    messages: list[dict] = [{"role": "user", "content": f"Please use the function {tool} once, with no arguments. When it returns, tell me the reference value it gave you and nothing else."}]
    seen: list[str] = []
    started = time.perf_counter()

    def finish(passed: bool, reason: str) -> dict:
        reason = _scrubbed(reason, key)
        result = {"model": model, "status": "passed" if passed else "failed", "reason": reason, "max_tokens": max_tokens, "tools_called": seen, "latency_ms": int((time.perf_counter() - started) * 1000)}
        try:
            result["checked_at"] = models.set_tool_check(model, passed, reason, max_tokens)["tools_checked_at"]
        except KeyError:
            result["checked_at"] = None  # not in the model list, so there is no row to keep it on
        return result

    async def ask(http: httpx.AsyncClient) -> tuple[dict | None, str]:
        response = await http.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {key}"},
                                   json={"model": model, "messages": messages, "tools": tools, "max_tokens": max_tokens})
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}: {_scrubbed(response.text, key)}"
        choice = (response.json().get("choices") or [{}])[0]
        return choice, ""

    try:
        async with httpx.AsyncClient(timeout=90, transport=transport) as http:
            first, problem = await ask(http)
            if first is None:
                return finish(False, problem)
            message = first.get("message") or {}
            calls = message.get("tool_calls") or []
            seen.extend(str((c.get("function") or {}).get("name") or "") for c in calls)
            if not calls:
                said = " ".join((message.get("content") or "").split())
                return finish(False, f"Did not call the tool. It said: {said[:160]}" if said else f"Did not call the tool and returned nothing (finish reason {first.get('finish_reason') or 'none'}, max_tokens {max_tokens}).")
            if seen != [tool]:
                other = [n for n in seen if n != tool]
                return finish(False, f"Called {', '.join(other) or 'the tool more than once'} instead of exactly {tool}" + (", which was not offered." if other else "."))
            messages.append({"role": "assistant", "content": message.get("content") or None, "tool_calls": [{"id": c.get("id"), "type": "function", "function": c.get("function")} for c in calls]})
            messages.append({"role": "tool", "tool_call_id": calls[0].get("id"), "content": json.dumps({"reference": token})})
            second, problem = await ask(http)
            if second is None:
                return finish(False, f"The call to the tool worked, but sending its result failed. {problem}")
    except httpx.HTTPError as exc:
        raise ModelEndpointError(f"Cannot reach {base}: {_scrubbed(str(exc) or type(exc).__name__, key)}") from exc
    reply = ((second.get("message") or {}).get("content") or "").strip()
    if token in reply:
        return finish(True, "Called the offered tool and used its result.")
    if not reply:
        return finish(False, f"Called the tool, then returned nothing (finish reason {second.get('finish_reason') or 'none'}, max_tokens {max_tokens}).")
    return finish(False, f"Called the tool but ignored its result. It said: {' '.join(reply.split())[:160]}")
