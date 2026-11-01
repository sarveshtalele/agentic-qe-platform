"""Typed errors. Each says what happened, what to do next, and whether a plain retry may help.

Old exception types subclass these, so `except RuntimeError` and `except ValueError` callers keep working.
`retryable` means a retry may succeed without any change. The run page offers Retry failed stage for every
failed run, because the fix named in `action` may already be done.
"""
from __future__ import annotations

import asyncio
import re
import traceback

import httpx
import openai

from backend.core.security import redact


class AqeError(RuntimeError):
    code = "AQE-INT-001"
    action = "Copy the diagnostics and report it."
    retryable = False

    def __init__(self, message: str, *, action: str | None = None, retryable: bool | None = None, **detail):
        super().__init__(message)
        self.message = message
        if action is not None:
            self.action = action
        if retryable is not None:
            self.retryable = retryable
        self.detail = detail  # agent, attempt, reply, parse_pos, provider_status ... filled where they are known

    def public(self) -> dict:
        return {"code": self.code, "message": redact(self.message), "action": self.action, "retryable": self.retryable}


class ModelJsonError(AqeError):
    code, retryable = "AQE-MODEL-001", True
    action = "Retry the stage. The saved reply shows the exact character that broke."


class ModelTruncated(AqeError):
    code = "AQE-MODEL-002"
    action = "Raise the agent's token limit on the Agents page, then retry the stage."


class ModelSchemaError(AqeError):
    code, retryable = "AQE-MODEL-003", True
    action = "Retry the stage. The message names the missing or wrong field."


class ModelTimeout(AqeError):
    code, retryable = "AQE-MODEL-004", True
    action = "Check the model endpoint, or raise ATLAS_MODEL_TIMEOUT, then retry the stage."


class ModelRefused(AqeError):
    code = "AQE-MODEL-005"
    action = "Remove the flagged text from the input or the repository, then retry the stage."


class ModelEndpointError(AqeError):
    code = "AQE-MODEL-006"
    action = "Open Settings and check the base URL, model, and API key, then retry the stage."


class AllowanceError(AqeError):
    """The project's owner has no time or tokens left, or the run reached its token limit."""

    code = "AQE-ALLOW-001"
    action = "Ask your administrator to raise the allocation or limit, then retry the stage."


class LimitReached(AllowanceError):
    """A daily, weekly, or monthly token limit is reached. The message names the limit and when it resets."""

    code = "AQE-ALLOW-002"
    action = "Wait for the reset time in the message, or ask your administrator to raise the limit, then use Retry failed stage."


class RepoError(AqeError):
    code = "AQE-REPO-001"
    action = "Check the repository address and access token, then try again."


class EvidenceError(AqeError):
    code = "AQE-EVID-001"
    action = "Review the requirements and the repository, then retry the stage."


class ExecutionError(AqeError):
    code = "AQE-TEST-001"
    action = "Tick install dependencies for this run, or fix the environment, then retry the stage."


class InternalError(AqeError):
    pass


def stack_of(exc: BaseException) -> str:
    """A redacted stack trace. Logging exc_info directly would bypass the log mask."""
    return redact("".join(traceback.format_exception(exc)))[-20000:]


def _chain(exc: BaseException):
    seen: list[BaseException] = []
    while exc is not None and exc not in seen:
        seen.append(exc)
        yield exc
        exc = exc.__cause__ or getattr(exc, "inner_exception", None)


def classify(exc: BaseException) -> AqeError:
    """Map any exception to a typed one. Provider status and request id are kept, not cut to a sentence."""
    if isinstance(exc, AqeError):
        return exc
    text = redact(str(exc))
    chain = list(_chain(exc))
    status = next((e for e in chain if isinstance(e, openai.APIStatusError)), None)
    facts = {"technical": text[:2000]}
    if status is not None:
        facts["provider_status"] = status.status_code
        facts["provider_request_id"] = status.request_id or status.response.headers.get("x-request-id") or ""
    if "content_filter" in text:
        label = re.search(r"blocked by label '([^']+)'", text)
        return ModelRefused(f"The model provider blocked this request ({label.group(1) if label else 'content policy'}). Reword the input or remove that text from the source.", **facts)
    if any(isinstance(e, (openai.APITimeoutError, asyncio.TimeoutError, httpx.TimeoutException)) for e in chain):
        return ModelTimeout("The model did not reply in time.", **facts)
    if status is not None:
        code = status.status_code
        if code in (401, 403):
            return ModelEndpointError(f"The model endpoint rejected the API key (HTTP {code}).", **facts)
        if code == 429 or code >= 500:
            return ModelEndpointError(f"The model endpoint is busy or failing (HTTP {code}).", action="Wait a moment and retry the stage. If it keeps happening, check the provider.", retryable=True, **facts)
        return ModelEndpointError(f"The model endpoint refused the request (HTTP {code}): {text[:200]}", **facts)
    if any(isinstance(e, openai.APIConnectionError) for e in chain):
        return ModelEndpointError("Cannot reach the model endpoint.", retryable=True, **facts)
    return InternalError(f"{type(exc).__name__}: {text[:300]}", **facts)
