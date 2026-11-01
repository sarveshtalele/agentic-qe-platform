"""Model provider settings. Environment wins on first run; the Settings page can override and encrypts the key."""
from __future__ import annotations

import os
import time

import httpx
from agent_framework.openai import OpenAIChatCompletionClient
from openai import AsyncOpenAI

from backend.config import MODEL_TIMEOUT
from backend.core.errors import ModelEndpointError
from backend.core.security import decrypt, encrypt
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
    message = response.json()["choices"][0]["message"]
    return {"ok": True, "model": name, "latency_ms": latency, "reply": (message.get("content") or message.get("reasoning_content") or "")[:80]}
