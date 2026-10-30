from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple

# Pre-compiled high-confidence secret patterns (CTL-SEC-01)
SECRET_PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9]{32,64}"), "OpenAI API Key"),
    (re.compile(r"sk-ant-[a-zA-Z0-9]{32,64}"), "Anthropic API Key"),
    (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "GitHub Personal Access Token"),
    (re.compile(r"gho_[a-zA-Z0-9]{36}"), "GitHub OAuth Access Token"),
    (re.compile(r"glpat-[a-zA-Z0-9_\-]{20}"), "GitLab Personal Access Token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS Access Key ID"),
    (re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}['\"]?"), "AWS Secret Key"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), "Private Key Header"),
    (re.compile(r"(?i)(?:api[_-]?key|secret[_-]?key|auth[_-]?token|access[_-]?token)\s*[:=]\s*['\"][a-zA-Z0-9_\-]{24,}['\"]"), "Generic Hardcoded Secret"),
    (re.compile(r"(?i)password\s*[:=]\s*['\"][^\s'\"]{8,}['\"]"), "Hardcoded Password Assignment"),
]


def shannon_entropy(data: str) -> float:
    """Calculates the Shannon entropy of a string."""
    if not data:
        return 0.0
    entropy = 0.0
    for x in set(data):
        p_x = float(data.count(x)) / len(data)
        entropy += -p_x * math.log2(p_x)
    return entropy


def scan_for_secrets(text: str, entropy_threshold: float = 4.5) -> List[Dict[str, str]]:
    """
    Scans content for embedded secrets, API keys, private keys, or high-entropy tokens.
    Returns a list of findings with secret type and redacted excerpt.
    """
    findings: List[Dict[str, str]] = []

    # 1. Pattern Matching
    for pattern, name in SECRET_PATTERNS:
        matches = pattern.finditer(text)
        for m in matches:
            val = m.group(0)
            redacted = val[:4] + "*" * (len(val) - 8) + val[-4:] if len(val) > 8 else "***"
            findings.append({
                "type": name,
                "redacted": redacted,
                "reason": f"Matched sensitive pattern for {name}",
            })

    # 2. Entropy Check on suspicious alphanumeric word tokens (length >= 32)
    tokens = re.findall(r"\b[A-Za-z0-9+/=_-]{32,}\b", text)
    for token in tokens:
        # Ignore common long hex strings like git commit hashes or standard base64 if low entropy
        if any(f["redacted"] in token for f in findings):
            continue
        ent = shannon_entropy(token)
        if ent > entropy_threshold:
            redacted = token[:4] + "..." + token[-4:]
            findings.append({
                "type": "High Entropy Token",
                "redacted": redacted,
                "reason": f"High Shannon entropy ({ent:.2f} > {entropy_threshold}) indicates potential secret",
            })

    return findings
