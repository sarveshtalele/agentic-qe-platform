"""
Real LLM Client for Agentic QE Platform.
Directly interfaces with LiteLLM Proxy / Azure AI / OpenAI / Anthropic endpoints.
Strictly enforces:
- ZERO mock/dummy fallback data.
- If credentials are not configured, raises an explicit descriptive error.
- When credentials are present, performs real inference via the configured LLM.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from backend.logger import logger

SETTINGS_FILE = Path(__file__).resolve().parents[3] / "data" / "settings.json"


class LLMNotConfiguredError(Exception):
    """Raised when an agent tries to invoke an LLM without configured credentials."""
    pass


class LLMClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ):
        settings = self._load_settings()
        self.base_url = (
            base_url
            or os.environ.get("OPENAI_BASE_URL")
            or settings.get("base_url")
            or "https://litellm-proxy-app-gfajczbbf7fjfyfw.eastus2-01.azurewebsites.net/v1"
        ).rstrip("/")
        
        if api_key is not None:
            self.api_key = api_key.strip()
        else:
            self.api_key = (
                os.environ.get("OPENAI_API_KEY")
                or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                or settings.get("api_key", "")
            ).strip()
        
        self.model_name = (
            model_name
            or os.environ.get("DEFAULT_MODEL")
            or settings.get("model_name")
            or "deepseek-v4-flash-global"
        ).strip()
        
        self.temperature = temperature
        self.max_tokens = max_tokens

    @staticmethod
    def _load_settings() -> Dict[str, Any]:
        if SETTINGS_FILE.exists():
            try:
                return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def is_configured(self) -> bool:
        """Checks if a valid, non-empty API key is present."""
        return bool(self.api_key and not self.api_key.startswith("sk-..."))

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,
    ) -> str:
        """
        Executes a real chat completion against the configured endpoint.
        Raises LLMNotConfiguredError if no credentials exist.
        """
        if not self.is_configured():
            raise LLMNotConfiguredError(
                "LLM Provider Not Configured: No valid API key provided. "
                "Please open Platform Settings and configure your Custom LLM Base URL, API Key, and Model Name."
            )

        payload_messages = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages.extend(messages)

        # Normalize URL to /v1/chat/completions
        endpoint = f"{self.base_url}/chat/completions" if not self.base_url.endswith("/chat/completions") else self.base_url

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Agentic-QE-Platform/2.0",
        }

        req_body: Dict[str, Any] = {
            "model": self.model_name,
            "messages": payload_messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
        }

        if response_format == "json":
            req_body["response_format"] = {"type": "json_object"}

        start_time = time.perf_counter()
        preview = payload_messages[-1]["content"][:80].replace("\n", " ") if payload_messages else "empty"
        logger.info(f"[LLM REQ] Model={self.model_name} Endpoint={endpoint} Prompt='{preview}...'")

        async with httpx.AsyncClient(timeout=45.0) as client:
            try:
                resp = await client.post(endpoint, headers=headers, json=req_body)
            except httpx.RequestError as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                logger.error(f"[LLM ERR] Connect failed after {duration_ms}ms to {endpoint}: {exc}")
                raise RuntimeError(f"Failed to connect to LLM endpoint at {self.base_url}: {exc}")

            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if resp.status_code != 200:
                err_text = resp.text[:300]
                logger.error(f"[LLM ERR] HTTP {resp.status_code} ({duration_ms}ms): {err_text}")
                raise RuntimeError(
                    f"LLM API returned error HTTP {resp.status_code}: {err_text}"
                )

            data = resp.json()
            try:
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                tokens_info = f"tokens={usage.get('total_tokens', 'N/A')}" if usage else f"chars={len(content)}"
                logger.info(f"[LLM RES] HTTP 200 ({duration_ms}ms, {tokens_info}) Response='{content[:60].replace(chr(10), ' ')}...'")
                return content.strip()
            except (KeyError, IndexError):
                logger.error(f"[LLM ERR] Unexpected structure ({duration_ms}ms): {data}")
                raise RuntimeError(f"Unexpected LLM API response structure: {data}")

    async def test_connection(self) -> Dict[str, Any]:
        """Probes the configured endpoint with a minimal ping prompt."""
        if not self.is_configured():
            return {
                "success": False,
                "error": "No API key configured. Please enter a valid API key.",
                "latency_ms": 0,
            }

        import time
        start = time.perf_counter()
        try:
            content = await self.chat_completion(
                messages=[{"role": "user", "content": "Ping. Respond with PONG."}],
                max_tokens=10,
            )
            latency = int((time.perf_counter() - start) * 1000)
            return {
                "success": True,
                "message": f"Successfully connected to {self.model_name} via {self.base_url}!",
                "reply": content,
                "latency_ms": latency,
            }
        except Exception as exc:
            latency = int((time.perf_counter() - start) * 1000)
            return {
                "success": False,
                "error": str(exc),
                "latency_ms": latency,
            }
