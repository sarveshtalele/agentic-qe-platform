#!/usr/bin/env python3
"""One cross-platform entry point. Standard library only, so it runs before any install.

  python scripts/dev.py setup      create .venv, install Python and Node dependencies
  python scripts/dev.py backend    FastAPI on 127.0.0.1:8000
  python scripts/dev.py frontend   Next.js dev server on 127.0.0.1:3000
  python scripts/dev.py up         install if needed, build, run backend and UI, open the browser
  python scripts/dev.py start      production: build the UI, run backend and UI together
  python scripts/dev.py test       unit and integration tests (no network, no model)
  python scripts/dev.py e2e        Playwright end-to-end tests against real servers and the real model
"""
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "src" / "frontend"
VENV = ROOT / ".venv"
PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
BACKEND = [str(PYTHON), "-m", "uvicorn", "backend.app:app", "--host", os.environ.get("ATLAS_HOST", "127.0.0.1"), "--port", os.environ.get("ATLAS_PORT", "8000")]


def run(command: list[str], cwd: Path = ROOT) -> None:
    subprocess.run(command, cwd=cwd, env=ENV, check=True)


def npm() -> str:
    found = shutil.which("npm")  # resolves npm.cmd on Windows, which subprocess cannot find alone
    if not found:
        sys.exit("Node.js 20+ with npm is required: https://nodejs.org")
    return found


def setup() -> None:
    if sys.version_info < (3, 12):
        sys.exit(f"Python 3.12+ is required, found {sys.version.split()[0]}")
    if not shutil.which("git"):
        sys.exit("Git is required: https://git-scm.com")
    if not PYTHON.exists():
        venv.create(VENV, with_pip=True)
    run([str(PYTHON), "-m", "pip", "install", "-q", "-r", "requirements.txt"])
    run([str(PYTHON), "-m", "playwright", "install", "chromium"])
    run([npm(), "ci"], FRONTEND)
    if not (ROOT / ".env").exists():
        shutil.copy(ROOT / ".env.example", ROOT / ".env")
        print("Created .env from .env.example. Add your model settings there or in the Settings page.")


def start() -> None:
    run([npm(), "run", "build"], FRONTEND)
    backend = subprocess.Popen(BACKEND, cwd=ROOT, env=ENV)
    try:
        run([npm(), "run", "start", "--", "--hostname", "127.0.0.1"], FRONTEND)
    finally:
        backend.terminate()


def _port_free(port: int) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


def _spawn(command: list[str], cwd: Path, env: dict) -> subprocess.Popen:
    # each server gets its own process group, because npm starts child processes that must stop with it
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    return subprocess.Popen(command, cwd=cwd, env=env, **options)


def _stop(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=30)
    else:
        os.killpg(process.pid, signal.SIGTERM)


def _needs_build(dist: Path) -> bool:
    built = dist / "BUILD_ID"
    if not built.exists():
        return True
    stamp = built.stat().st_mtime
    watched = [FRONTEND / name for name in ("app", "components", "lib", "next.config.ts", "package-lock.json")]
    return any(f.stat().st_mtime > stamp for item in watched for f in ([item] if item.is_file() else item.rglob("*")) if f.is_file())


def up() -> None:
    """The launchers call this: one command from a fresh checkout to the app in a browser."""
    api_port, ui_port = int(os.environ.get("ATLAS_PORT", "8000")), int(os.environ.get("ATLAS_UI_PORT", "3000"))
    for port in (api_port, ui_port):
        if not _port_free(port):
            sys.exit(f"Port {port} is in use. Stop what is using it, or set ATLAS_PORT and ATLAS_UI_PORT to free ports.")
    if not PYTHON.exists() or not (FRONTEND / "node_modules").exists():
        print("First run: installing dependencies. This takes a few minutes.")
        setup()
    env = {**ENV, "ATLAS_BACKEND_URL": os.environ.get("ATLAS_BACKEND_URL", f"http://127.0.0.1:{api_port}"), "NEXT_TELEMETRY_DISABLED": "1"}
    env.setdefault("ATLAS_ALLOWED_ORIGINS", f"http://127.0.0.1:{ui_port},http://localhost:{ui_port}")
    if _needs_build(FRONTEND / os.environ.get("ATLAS_DIST_DIR", ".next")):
        print("Building the UI.")
        subprocess.run([npm(), "run", "build"], cwd=FRONTEND, env=env, check=True)
    backend = _spawn([str(PYTHON), "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", str(api_port)], ROOT, env)
    frontend = _spawn([npm(), "run", "start", "--", "--hostname", "127.0.0.1", "--port", str(ui_port)], FRONTEND, env)
    url = f"http://127.0.0.1:{ui_port}"
    try:
        for _ in range(120):
            if backend.poll() is not None or frontend.poll() is not None:
                sys.exit("A server stopped during startup. See the messages above.")
            try:
                urllib.request.urlopen(f"{url}/api/health", timeout=2).close()
                break
            except OSError:
                time.sleep(1)
        else:
            sys.exit(f"The app did not answer at {url} within two minutes.")
        print(f"\nAgentic QE Platform is running at {url}. Press Ctrl+C to stop.\n")
        if not os.environ.get("ATLAS_NO_BROWSER"):
            webbrowser.open(url)
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(1)
    finally:
        _stop(frontend)
        _stop(backend)


COMMANDS = {
    "up": up,
    "setup": setup,
    "backend": lambda: run(BACKEND),
    "frontend": lambda: run([npm(), "run", "dev", "--", "--hostname", "127.0.0.1"], FRONTEND),
    "start": start,
    "test": lambda: run([str(PYTHON), "-m", "pytest", "tests", "-q", "-m", "not e2e and not live"]),
    "e2e": lambda: run([str(PYTHON), "-m", "pytest", "tests/e2e", "-v", "-m", "e2e", "-s"]),
}

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action not in COMMANDS:
        sys.exit(__doc__)
    try:
        COMMANDS[action]()
    except KeyboardInterrupt:
        pass
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
