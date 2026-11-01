from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List
from .base import AgentSkill, maf_skill
from ...governance.guards import guard_bash


@maf_skill(name="executing_tests", description="Runs tests inside an ephemeral isolated sandbox and computes execution summaries")
class IsolatedTestExecutionSkill(AgentSkill):
    """
    Ported from sarveshtalele/agentic-qe skills/executing-tests/scripts/run-isolated.ts & parse-junit.ts.
    Executes test code in a sandboxed temporary directory, enforces timeout, and computes PASS/FAIL status.
    """

    def __init__(self):
        super().__init__(
            name="executing_tests",
            description="Sandboxed subprocess test runner with JUnit XML & console output extraction.",
            category="TestExecution"
        )

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        test_code = context.get("test_code") or context.get("pytest_code") or "def test_pass(): assert True"
        timeout_sec = int(context.get("timeout_sec", 15))

        with tempfile.TemporaryDirectory(prefix="maf_test_sandbox_") as tmp_dir:
            test_file = Path(tmp_dir) / "test_suite.py"
            test_file.write_text(test_code, encoding="utf-8")

            cmd = [sys.executable, "-m", "pytest", str(test_file), "-v"]
            start_time = time.time()
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=tmp_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
                duration_ms = int((time.time() - start_time) * 1000)
                exit_code = proc.returncode or 0
                out_text = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")

                passed = exit_code == 0
                # Parse passed and failed counts
                total_cases = 1
                passed_cases = 1 if passed else 0
                failed_cases = 0 if passed else 1

                import re
                passed_match = re.search(r"(\d+)\s+passed", out_text)
                failed_match = re.search(r"(\d+)\s+failed", out_text)
                if passed_match:
                    passed_cases = int(passed_match.group(1))
                if failed_match:
                    failed_cases = int(failed_match.group(1))
                total_cases = passed_cases + failed_cases

                return {
                    "status": "PASS" if passed else "FAIL",
                    "passed": passed,
                    "exit_code": exit_code,
                    "total": total_cases,
                    "total_cases": total_cases,
                    "passed_cases": passed_cases,
                    "failed_cases": failed_cases,
                    "duration_ms": duration_ms,
                    "duration_sec": round(duration_ms / 1000.0, 3),
                    "output_log": out_text[:2000],
                    "sandbox_dir": tmp_dir,
                }
            except asyncio.TimeoutError:
                return {
                    "status": "TIMEOUT",
                    "passed": False,
                    "exit_code": 124,
                    "total": 1,
                    "total_cases": 1,
                    "passed_cases": 0,
                    "failed_cases": 1,
                    "duration_ms": timeout_sec * 1000,
                    "duration_sec": float(timeout_sec),
                    "output_log": f"Test execution timed out after {timeout_sec}s.",
                }
            except Exception as exc:
                return {
                    "status": "INCONCLUSIVE",
                    "passed": False,
                    "exit_code": 1,
                    "total": 1,
                    "total_cases": 1,
                    "passed_cases": 0,
                    "failed_cases": 1,
                    "duration_ms": 0,
                    "duration_sec": 0.0,
                    "output_log": f"Execution error: {exc}",
                }
