"""Browser smoke test with no model: a built app, an empty throwaway data folder, and a real browser.

Runs in CI on every push (`python scripts/dev.py smoke`). It uses its own ports (3011 and 8011) and data folder, so it never touches
a running copy of the app or the model-backed e2e suite. The administrator password is generated for each run and never written to a file.
"""
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from tests.e2e.conftest import ROOT, wait_http

pytestmark = pytest.mark.smoke

UI, API = "http://127.0.0.1:3011", "http://127.0.0.1:8011"
ADMIN = {"username": "smoke-admin", "password": secrets.token_urlsafe(18)}
MEMBER = {"username": "smoke-member", "password": secrets.token_urlsafe(18)}
PAGES = [("Projects", "Projects"), ("Approvals", "Approvals"), ("Agents", "Agents"), ("Observability", "Observability"), ("Templates", "Templates"), ("Settings", "Settings"), ("Users", "Users"), ("Documentation", None)]


def _dev():
    spec = importlib.util.spec_from_file_location("atlas_dev", ROOT / "scripts" / "dev.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def app():
    dev = _dev()
    data = Path(tempfile.mkdtemp(prefix="atlas-smoke-"))
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "ATLAS_DATA_DIR": str(data), "ATLAS_SECRET_KEY": secrets.token_urlsafe(24),
           "ATLAS_ADMIN_USERNAME": ADMIN["username"], "ATLAS_ADMIN_PASSWORD": ADMIN["password"], "ATLAS_BACKEND_URL": API, "ATLAS_ALLOWED_ORIGINS": UI,
           "ATLAS_DIST_DIR": ".next-smoke", "NEXT_TELEMETRY_DISABLED": "1", "OPENAI_API_KEY": "", "OPENAI_BASE_URL": "", "DEFAULT_MODEL": ""}  # no model, even if a .env has one
    frontend_dir = ROOT / "src" / "frontend"
    subprocess.run([dev.npm(), "run", "build"], cwd=frontend_dir, env=env, check=True, capture_output=True)
    log = (data / "servers.log").open("w")
    group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}  # so dev._stop ends npm's child too
    backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "8011"], cwd=ROOT, env=env, stdout=log, stderr=log, **group)
    frontend = subprocess.Popen([dev.npm(), "run", "start", "--", "--hostname", "127.0.0.1", "--port", "3011"], cwd=frontend_dir, env=env, stdout=log, stderr=log, **group)
    try:
        wait_http(f"{API}/api/health")
        wait_http(UI)
        yield data
    finally:
        dev._stop(frontend)
        dev._stop(backend)
        log.close()
        shutil.rmtree(data, ignore_errors=True)


@pytest.fixture(scope="module")
def browser(app):
    with sync_playwright() as driver:
        chromium = driver.chromium.launch()
        yield chromium
        chromium.close()


def sign_in(browser, who):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    tab = context.new_page()
    tab.goto(f"{UI}/login")
    tab.get_by_label("Username").fill(who["username"])
    tab.get_by_label("Password").fill(who["password"])
    tab.get_by_role("button", name="Sign in").click()
    return tab


def test_a_wrong_password_is_refused_and_the_right_one_signs_in(browser):
    tab = sign_in(browser, {"username": ADMIN["username"], "password": secrets.token_urlsafe(12)})
    expect(tab.get_by_text("The username or password is not correct")).to_be_visible(timeout=15_000)
    expect(tab).to_have_url(re.compile(r"/login$"))
    expect(tab.get_by_test_id("signed-in-user")).to_have_count(0)
    tab.get_by_label("Password").fill(ADMIN["password"])
    tab.get_by_role("button", name="Sign in").click()
    expect(tab.get_by_role("heading", name="Projects")).to_be_visible(timeout=30_000)
    expect(tab.get_by_test_id("signed-in-user")).to_contain_text("smoke-admin")
    tab.context.close()


def test_main_pages_open_and_show_their_empty_state(browser):
    tab = sign_in(browser, ADMIN)
    errors = []
    tab.on("pageerror", lambda e: errors.append(str(e)))
    expect(tab.get_by_role("heading", name="Projects")).to_be_visible(timeout=30_000)
    expect(tab.get_by_text("No projects yet")).to_be_visible()
    nav = tab.get_by_role("navigation", name="Workspace")
    for link, heading in PAGES:
        nav.get_by_role("link", name=re.compile(f"^{link}")).click()
        expect(tab.get_by_role("heading", name=heading, exact=True) if heading else tab.get_by_role("heading", level=1)).to_be_visible(timeout=20_000)  # the docs page is titled by its article
    tab.goto(UI)  # the docs section has its own frame, so go back to the workspace by address
    nav.get_by_role("link", name="Approvals").click()
    expect(tab.get_by_text("Nothing needs your approval")).to_be_visible(timeout=15_000)
    nav.get_by_role("link", name="Observability").click()
    expect(tab.get_by_text("Nothing recorded for these filters")).to_be_visible(timeout=15_000)
    nav.get_by_role("link", name="Users").click()
    expect(tab.get_by_text("No users yet")).to_be_visible(timeout=15_000)
    nav.get_by_role("link", name="Settings").click()
    expect(tab.get_by_role("heading", name="Settings", exact=True)).to_be_visible(timeout=15_000)
    expect(tab.get_by_text("Model missing")).to_be_visible(timeout=15_000)  # the health card: the app runs without a model
    assert not errors, errors
    tab.context.close()


def test_a_non_admin_is_refused_on_users(browser, app):
    admin = urllib.request.Request(f"{API}/api/auth/login", data=json.dumps(ADMIN).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(admin) as response:
        cookie = response.headers["set-cookie"].split(";")[0]
    made = urllib.request.Request(f"{API}/api/users", data=json.dumps(MEMBER).encode(), headers={"Content-Type": "application/json", "Cookie": cookie})
    assert urllib.request.urlopen(made).status == 201
    tab = sign_in(browser, MEMBER)
    expect(tab.get_by_role("heading", name="Projects")).to_be_visible(timeout=30_000)
    nav = tab.get_by_role("navigation", name="Workspace")
    expect(nav.get_by_role("link", name="Users")).to_have_count(0)
    expect(nav.get_by_role("link", name="Settings")).to_have_count(0)
    tab.goto(f"{UI}/users")
    expect(tab.get_by_text("Only an administrator can do this")).to_be_visible(timeout=15_000)
    expect(tab.get_by_test_id("user-card")).to_have_count(0)
    status = tab.evaluate("fetch('/api/users').then(r => r.status)")
    assert status == 403
    assert tab.evaluate("fetch('/api/logs').then(r => r.status)") == 403
    tab.context.close()
