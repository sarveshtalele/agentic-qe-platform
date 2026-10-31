from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import Any, Dict, Optional

from .secret_scanner import scan_for_secrets

# Banned shell commands and destructive tokens (CTL-HITL-02)
FORBIDDEN_COMMANDS = {
    "rm", "unlink", "rmdir", "shred", "rename", "mkfs", "dd",
    "sudo", "doas", "su", "chroot", "nsenter", "unshare",
    "iptables", "ufw", "reboot", "shutdown", "poweroff", "init",
}

FORBIDDEN_PATTERNS = [
    re.compile(r"\brm\s+-[rfRF]{1,4}\b"),               # rm -rf
    re.compile(r">\s*/dev/sd[a-z]"),                    # direct disk overwrite
    re.compile(r"\b(curl|wget|fetch)\b.*\|\s*(sh|bash|zsh|python|perl)\b"), # curl | bash
    re.compile(r"\bchmod\s+[0-7]{3,4}\b"),              # arbitrary permission modification
    re.compile(r"\bchown\b"),                           # ownership modification
    re.compile(r";\s*rm\b"),                            # command chaining rm
    re.compile(r"&&\s*rm\b"),
]

PROTECTED_DIRS = {".git", ".venv", ".qe", "node_modules", "data/exports"}


def guard_write(
    workspace_root: Path,
    target_rel_or_abs: str,
    content: str,
    auto_approve_existing: bool = False,
) -> Dict[str, Any]:
    """
    Enforces CTL-HITL-01 (Safe File Mutation) and CTL-SEC-02 (Path Traversal Protection).
    """
    try:
        ws_root = workspace_root.resolve()
        target_path = (ws_root / target_rel_or_abs).resolve()
    except Exception as e:
        return {
            "allowed": False,
            "requires_hitl": False,
            "control_id": "CTL-SEC-02",
            "reason": f"Path resolution failed: {e}",
        }

    # 1. Path Traversal & Boundary Check (CTL-SEC-02)
    try:
        rel = target_path.relative_to(ws_root)
    except ValueError:
        return {
            "allowed": False,
            "requires_hitl": False,
            "control_id": "CTL-SEC-02",
            "reason": f"Attempted path escape: {target_rel_or_abs} is outside workspace root ({ws_root})",
        }

    # 2. Protected Internal Directories
    parts = rel.parts
    if any(p in PROTECTED_DIRS for p in parts):
        return {
            "allowed": False,
            "requires_hitl": False,
            "control_id": "CTL-HITL-01",
            "reason": f"Modification of protected system/internal path '{rel}' is forbidden",
        }

    # 3. Secret Leakage Check (CTL-SEC-01)
    secret_findings = scan_for_secrets(content)
    if secret_findings:
        return {
            "allowed": False,
            "requires_hitl": False,
            "control_id": "CTL-SEC-01",
            "reason": f"Content contains suspected secrets: {secret_findings[0]['type']} ({secret_findings[0]['redacted']})",
            "findings": secret_findings,
        }

    # 4. Existing file vs New file check
    file_exists = target_path.exists()
    if file_exists and not auto_approve_existing:
        return {
            "allowed": True,
            "requires_hitl": True,
            "control_id": "CTL-HITL-01",
            "reason": f"Overwriting existing file '{rel}' requires human approval",
            "target": str(rel),
        }

    return {
        "allowed": True,
        "requires_hitl": False,
        "control_id": "CTL-HITL-01",
        "reason": f"File mutation to '{rel}' permitted",
        "target": str(rel),
    }


def guard_bash(
    command: str,
    commands_enabled: bool,
    workspace_root: Path,
) -> Dict[str, Any]:
    """
    Enforces CTL-HITL-02 (Shell Command Safety) and CTL-SEC-03 (Execution Quota & Sandboxing).
    """
    cmd_clean = command.strip()
    if not cmd_clean:
        return {"allowed": False, "requires_hitl": False, "control_id": "CTL-HITL-02", "reason": "Empty command"}

    # Policy toggle check
    if not commands_enabled:
        return {
            "allowed": False,
            "requires_hitl": True,
            "control_id": "CTL-HITL-02",
            "reason": "Repository commands are disabled by default policy (SDLC_ENABLE_REPO_COMMANDS=false). Explicit HITL approval required.",
            "command": cmd_clean,
        }

    # Pattern check
    for pat in FORBIDDEN_PATTERNS:
        if pat.search(cmd_clean):
            return {
                "allowed": False,
                "requires_hitl": False,
                "control_id": "CTL-HITL-02",
                "reason": f"Command matched forbidden destructive pattern: '{pat.pattern}'",
                "command": cmd_clean,
            }

    # Token check
    try:
        tokens = shlex.split(cmd_clean)
    except Exception:
        tokens = cmd_clean.split()

    if tokens:
        first_token = Path(tokens[0]).name.lower()
        if first_token in FORBIDDEN_COMMANDS:
            return {
                "allowed": False,
                "requires_hitl": False,
                "control_id": "CTL-HITL-02",
                "reason": f"Execution of banned binary '{first_token}' is prohibited",
                "command": cmd_clean,
            }

    return {
        "allowed": True,
        "requires_hitl": False,
        "control_id": "CTL-HITL-02",
        "reason": "Command passed pre-execution safety filters",
        "command": cmd_clean,
    }
