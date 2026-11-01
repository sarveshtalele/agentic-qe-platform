"""Real servers on separate ports with their own build folder, so a running copy of the app is never touched."""
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs" / "evidence"
UI = "http://127.0.0.1:3010"
API = "http://127.0.0.1:8010"
state: dict = {}


def wait_http(url: str, seconds: int = 90) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"{url} did not start")


@pytest.fixture(scope="session")
def servers():
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "ATLAS_BACKEND_URL": API, "ATLAS_DIST_DIR": ".next-e2e", "ATLAS_ALLOWED_ORIGINS": UI}
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    frontend_dir = ROOT / "src" / "frontend"
    npm = shutil.which("npm")
    subprocess.run([npm, "run", "build"], cwd=frontend_dir, env=env, check=True, capture_output=True)
    log = (EVIDENCE / "server.log").open("w")
    backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app:app", "--port", "8010"], cwd=ROOT, env=env, stdout=log, stderr=log)
    frontend = subprocess.Popen([npm, "run", "start", "--", "--hostname", "127.0.0.1", "--port", "3010"], cwd=frontend_dir, env=env, stdout=log, stderr=log)
    try:
        wait_http(f"{API}/api/health")
        wait_http(UI)
        yield
    finally:
        backend.terminate()
        frontend.terminate()
        log.close()


@pytest.fixture(scope="session")
def page(servers):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as driver:
        browser = driver.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        tab = context.new_page()
        state["console_errors"] = []
        tab.on("pageerror", lambda e: state["console_errors"].append(str(e)))
        yield tab
        browser.close()


