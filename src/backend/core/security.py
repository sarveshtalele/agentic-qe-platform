"""Secrets at rest, secret detection, redaction, path confinement, and shell-free command policy."""
from __future__ import annotations

import base64
import hashlib
import hmac
import math
import os
import re
from pathlib import Path

from cryptography.fernet import Fernet

from backend.config import DATA_DIR

KEY_FILE = DATA_DIR / ".secret.key"

SECRET_PATTERNS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "Anthropic API key"),
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "OpenAI-style API key"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "GitHub fine-grained token"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"), "GitHub token"),
    (re.compile(r"glpat-[A-Za-z0-9_\-]{20}"), "GitLab token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key id"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), "Private key"),
    (re.compile(r"(?i)\b(?:api[_-]?key|secret[_-]?key|auth[_-]?token|access[_-]?token|password)\b\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"), "Hardcoded secret"),
]
ENTROPY_TOKEN = re.compile(r"\b[A-Za-z0-9+/_\-]{40,}\b")
PLACEHOLDER = re.compile(r"(?i)example|changeme|placeholder|dummy|xxxx|your[_-]")


def _key() -> bytes:
    env = os.environ.get("ATLAS_SECRET_KEY")
    if env:
        return base64.urlsafe_b64encode(hashlib.sha256(env.encode()).digest())
    if not KEY_FILE.exists():
        KEY_FILE.write_bytes(Fernet.generate_key())
        try:
            KEY_FILE.chmod(0o600)
        except OSError:
            pass  # Windows ACLs govern access instead of POSIX mode bits
    return KEY_FILE.read_bytes()


def encrypt(value: str) -> bytes:
    return Fernet(_key()).encrypt(value.encode())


def decrypt(token: bytes) -> str:
    return Fernet(_key()).decrypt(token).decode()


def sign(message: str) -> str:
    return hmac.new(_key(), message.encode(), hashlib.sha256).hexdigest()


def verify_signature(message: str, signature: str) -> bool:
    return hmac.compare_digest(sign(message), signature)


def sha256(text: str | bytes) -> str:
    return hashlib.sha256(text.encode() if isinstance(text, str) else text).hexdigest()


def _entropy(token: str) -> float:
    return -sum((n := token.count(c)) / len(token) * math.log2(n / len(token)) for c in set(token))


def scan_secrets(text: str) -> list[dict]:
    """Return findings with 1-based line and redacted evidence. Placeholder values are ignored."""
    found: list[dict] = []
    for number, line in enumerate(text.splitlines(), 1):
        if len(line) > 2000:
            continue
        hit = False
        for pattern, name in SECRET_PATTERNS:
            match = pattern.search(line)
            if match and not PLACEHOLDER.search(match.group(0)):
                found.append({"type": name, "line": number, "redacted": redact_value(match.group(0))})
                hit = True
                break
        if hit:
            continue
        for token in ENTROPY_TOKEN.findall(line):
            if not PLACEHOLDER.search(token) and "/" not in token and _entropy(token) > 4.8:
                found.append({"type": "High-entropy token", "line": number, "redacted": redact_value(token)})
                break
    return found


def redact_value(value: str) -> str:
    return value[:4] + "…" + value[-2:] if len(value) > 10 else "***"


def has_masked_secret(text: str) -> bool:
    """A model reply passes through redact(), so a secret an agent writes arrives in redact_value's shape."""
    return bool(re.search(r"\S{4}…\w{2}\b", text))


def redact(text: str) -> str:
    """Mask anything secret-shaped before it reaches logs, the ledger, or an LLM prompt."""
    for pattern, _ in SECRET_PATTERNS:
        text = pattern.sub(lambda m: redact_value(m.group(0)), text)
    return text


class PathEscape(ValueError):
    pass


PROTECTED = {".git", ".venv", "venv", "node_modules", ".qe"}


def safe_path(root: Path, relative: str, *, for_write: bool = False) -> Path:
    """Resolve relative inside root, following symlinks, and refuse any escape."""
    if "\x00" in relative:
        raise PathEscape("Path contains a NUL byte")
    base = root.resolve()
    target = (base / relative.replace("\\", "/")).resolve()
    if not target.is_relative_to(base):
        raise PathEscape(f"Path escapes the workspace: {relative}")
    if for_write and PROTECTED & {p.lower() for p in target.relative_to(base).parts}:
        raise PathEscape(f"Protected path: {relative}")
    return target
