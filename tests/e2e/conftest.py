"""Real servers on separate ports with their own build folder, so a running copy of the app is never touched."""
import json
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


def api_get(path: str) -> bytes:
    """Reads the API as the admin, for checks that do not go through the browser."""
    login = urllib.request.Request(f"{API}/api/auth/login", data=json.dumps({"username": os.environ["ATLAS_ADMIN_USERNAME"], "password": os.environ["ATLAS_ADMIN_PASSWORD"]}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(login) as response:
        cookie = response.headers["set-cookie"].split(";")[0]
    with urllib.request.urlopen(urllib.request.Request(f"{API}/api{path}", headers={"Cookie": cookie})) as response:
        return response.read()


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
        tab.goto(UI)
        tab.get_by_label("Username").fill(os.environ["ATLAS_ADMIN_USERNAME"])
        tab.get_by_label("Password").fill(os.environ["ATLAS_ADMIN_PASSWORD"])
        tab.get_by_role("button", name="Sign in").click()
        tab.get_by_role("heading", name="Projects").wait_for(timeout=30_000)
        state["console_errors"] = []
        tab.on("pageerror", lambda e: state["console_errors"].append(str(e)))
        yield tab
        browser.close()


