"""Static pre-run checks of generated tests (qe/emit.py), on small real modules in tmp_path. Nothing is mocked and nothing is run."""
import sys

import pytest

from backend.qe import emit, execution

PKG = {
    "fin/__init__.py": "from .core import required_monthly_savings, Account\nfrom .more import *\n",
    "fin/core.py": (
        "import functools\n\n\ndef required_monthly_savings(goal, months, rate=0.0):\n    return goal\n\n\n"
        "class Account:\n    def __init__(self, balance, owner='x'):\n        self.balance = balance\n\n    def deposit(self, amount):\n        pass\n\n"
        "    @classmethod\n    def make(cls, n):\n        return cls(n)\n\n    @staticmethod\n    def util(a, *, b):\n        pass\n\n\n"
        "def logged(f):\n    return f\n\n\n@logged\ndef decorated(a):\n    pass\n\n\ndef spread(*args, **kwargs):\n    pass\n\n\n"
        "@functools.lru_cache(maxsize=None)\ndef cached(x):\n    return x\n"),
    "fin/more.py": "def extra(a):\n    return a\n",
    "tests/agentic_qe/conftest.py": "",
}


@pytest.fixture
def repo(tmp_path):
    for name, text in PKG.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding="utf-8")
    return tmp_path


@pytest.fixture(scope="module")
def env():
    found = execution.inventory if hasattr(execution, "inventory") else emit.inventory
    return found(sys.executable)


def check(repo, code, env=None, declared=frozenset()):
    return emit.check_python(repo, "tests/agentic_qe/test_x.py", code, env, declared)


def test_inventory_is_read_by_the_sandbox_python_itself(env):
    assert env and "pytest" in env["modules"] and "os" in env["stdlib"] and env["versions"].get("pytest")


def test_a_bad_keyword_is_found_with_the_real_signature(repo):
    found = check(repo, "from fin.core import required_monthly_savings\n\n\ndef test_a():\n    required_monthly_savings(1, 2, ratee=3)\n")
    assert len(found) == 1 and "'ratee'" in found[0] and "required_monthly_savings(goal, months, rate=0.0)" in found[0] and ":5:" in found[0]


def test_missing_and_extra_arguments(repo):
    code = "from fin.core import required_monthly_savings as r\n\n\ndef test_a():\n    r(1)\n    r(1, 2, 3, 4)\n    r(1, 2, goal=5)\n"
    found = check(repo, code)
    assert any("required argument 'months'" in f for f in found) and any("4 positional" in f for f in found) and any("twice" in f for f in found)


def test_a_missing_local_module_and_a_missing_name(repo):
    found = check(repo, "import fin.gone\nfrom fin.gone2 import x\nfrom fin.core import invented\n")
    assert any("fin.gone does not exist" in f for f in found) and any("fin.gone2 does not exist" in f for f in found) and any("no name 'invented'" in f for f in found)


def test_a_missing_third_party_package_is_found_and_installed_ones_are_not(repo, env):
    found = check(repo, "import flask\nimport pytest\nimport os\nfrom flask import Flask\n", env)
    assert len(found) == 2 and all("'flask' is not installed" in f for f in found)
    assert check(repo, "import flask\n", None) == [], "without an inventory nothing is claimed"
    assert check(repo, "import flask\n", env, {"flask"}) == [], "a declared package of a run that installs dependencies is allowed"
    assert check(repo, "try:\n    import flask\nexcept ImportError:\n    flask = None\n", env) == [], "an import that is expected to fail is left alone"


def test_args_kwargs_and_pass_through_decorators_are_accepted_without_false_alarms(repo):
    code = ("from fin.core import spread, decorated, cached, Account, required_monthly_savings\n\n\ndef test_a():\n"
            "    spread(1, 2, 3, x=1)\n    decorated(1, 2, 3, z=4)\n    cached(1)\n    required_monthly_savings(*[1, 2])\n    required_monthly_savings(**{'goal': 1, 'months': 2})\n"
            "    Account.make(3)\n    Account.util(1, b=2)\n    acct = Account(5)\n    acct.deposit(10)\n")
    assert check(repo, code) == []


def test_class_methods_instances_and_constructors(repo):
    code = "from fin.core import Account\n\n\ndef test_a():\n    Account(1, 2, 3)\n    Account.make(1, 2)\n    Account.util(1)\n    a = Account(1)\n    a.deposit()\n"
    found = check(repo, code)
    assert len(found) == 4 and any("Account(balance, owner='x')" in f for f in found) and any("Account.deposit(amount)" in f for f in found) and any("Account.make(n)" in f for f in found)


def test_re_exports_and_star_imports_resolve(repo):
    assert check(repo, "from fin import required_monthly_savings, extra, Account\nimport fin\n\n\ndef test_a():\n    extra(1)\n    fin.extra(2)\n    fin.required_monthly_savings(1, 2)\n") == []
    found = check(repo, "from fin import extra\n\n\ndef test_a():\n    extra()\n")
    assert len(found) == 1 and "extra(a)" in found[0]


def test_a_call_that_is_meant_to_raise_is_not_reported(repo):
    code = "import pytest\nfrom fin.core import required_monthly_savings\n\n\ndef test_a():\n    with pytest.raises(TypeError):\n        required_monthly_savings()\n"
    assert check(repo, code) == []


def test_a_module_that_cannot_be_known_is_not_reported(repo):
    (repo / "dyn.py").write_text("def __getattr__(name):\n    return name\n")
    assert check(repo, "from dyn import anything\n") == []


def test_httpx_app_keyword_is_found_on_a_new_httpx(repo):
    code = "import httpx\nfrom httpx import AsyncClient\n\n\ndef test_a():\n    httpx.AsyncClient(app=None)\n    AsyncClient(app=None)\n    httpx.Client(base_url='x')\n"
    new = {"modules": {"httpx"}, "stdlib": set(sys.stdlib_module_names), "versions": {"httpx": "0.28.1"}}
    old = {**new, "versions": {"httpx": "0.24.0"}}
    assert len(check(repo, code, new)) == 2 and "ASGITransport" in check(repo, code, new)[0]
    assert check(repo, code, old) == []


def test_javascript_gets_only_a_relative_import_path_check(repo):
    (repo / "tests/agentic_qe/helper.ts").write_text("export const x = 1\n")
    code = "import { x } from './helper'\nimport y from './gone'\nimport z from 'vitest'\n"
    found = emit.check(repo, "tests/agentic_qe/a.test.ts", code)
    assert found == ["tests/agentic_qe/a.test.ts: the import './gone' does not exist"]


def test_signatures_for_the_prompt_are_real_and_bounded(repo):
    text = emit.signatures(repo, ["fin/core.py", "fin/more.py"])
    assert "from fin.core import" in text and "required_monthly_savings(goal, months, rate=0.0)" in text and "class Account(balance, owner='x')" in text and "decorated" not in text
    assert emit.signatures(repo, ["fin/core.py", "fin/more.py"], budget=10) == ""
    assert emit.signatures(repo, ["nothing.py"]) == ""


def test_declared_dependencies_are_read_from_manifests(tmp_path):
    (tmp_path / "requirements.txt").write_text("Flask>=2.0\n# c\n-r other.txt\nslowapi[extra]==1\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\nversion="1"\ndependencies=["httpx>=0.2"]\n[project.optional-dependencies]\ndev=["pytest-asyncio"]\n')
    assert emit.declared_dependencies(tmp_path) == {"flask", "slowapi", "httpx", "pytest-asyncio"}
