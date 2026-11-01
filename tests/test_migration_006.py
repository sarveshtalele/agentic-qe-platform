"""Migration 006 renames agent keys to the plugin names. A database at schema 005 with history under the old keys must lose nothing."""
import sqlite3

import pytest

from backend import db as database
from backend.config import PROMPTS_DIR
from backend.core import ledger, prompts
from backend.core.security import sha256
from backend.maf.agents import POLICIES

ONE_TO_ONE = {
    "repo_analyst": "repo-intelligence-analyst", "requirements_analyst": "requirements-analyst", "test_architect": "principal-test-architect",
    "test_designer": "test-design-architect", "test_automation": "test-automation-engineer", "defect_diagnostician": "defect-diagnostician",
    "confidence_reviewer": "confidence-reviewer", "business_analyst": "business-analyst", "bug_reviewer": "bug-reviewer",
    "feature_engineer": "feature-engineer", "copilot": "project-copilot",
}
MERGED = {"doc_reviewer": "confidence-reviewer", "gherkin_author": "business-analyst"}
EVERY_OLD = {**ONE_TO_ONE, **MERGED}
TABLES = ["projects", "prompts", "agent_calls", "tool_calls", "agent_settings", "evaluations", "chat_threads", "chat_messages", "guardrail_events",
          "ledger", "document_versions", "documents", "runs", "run_events"]
SHA_A = "a" * 12


def counts(path) -> dict:
    con = sqlite3.connect(path)
    try:
        return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}
    finally:
        con.close()


@pytest.fixture
def old_db(tmp_path, monkeypatch):
    """A database exactly as migrations 001 to 005 leave it, filled with history under every old key."""
    path = tmp_path / "old.sqlite3"
    monkeypatch.setattr(database, "DB_PATH", path)
    con = sqlite3.connect(path)
    for sql in sorted(database.MIGRATIONS.glob("*.sql")):
        if int(sql.name.split("_")[0]) <= 5:
            con.executescript(sql.read_text(encoding="utf-8"))
    con.execute("PRAGMA user_version=5")
    con.execute("INSERT INTO projects (id, name, description, created_at, updated_at, archived) VALUES ('p1','P','',?,?,0)", (database.now(), database.now()))
    for old in EVERY_OLD:
        for version, active in ((1, 0), (2, 1)):
            body = f"{old} body v{version}"
            con.execute("INSERT INTO prompts VALUES (?,?,?,?,?,?,?,?)", (old, version, body, sha256(body), f"note {version}", "repo", active, database.now()))
        con.execute("INSERT INTO agent_calls (agent, project_id, source, prompt_ref, status, created_at) VALUES (?,?,?,?,?,?)", (old, "p1", "run", f"{old}@v2:{SHA_A}", "ok", database.now()))
        con.execute("INSERT INTO evaluations VALUES (?,?,?,?,?,?,?)", (f"evl_{old}", old, f"{old}@v1:{SHA_A}", 1, 2, "[]", database.now()))
        con.execute("INSERT INTO tool_calls (agent, project_id, source, tool, status, created_at) VALUES (?,?,?,?,?,?)", (old, "p1", "chat", "read_file", "ok", database.now()))
        con.execute("INSERT INTO guardrail_events (agent, project_id, kind, action, detail, created_at) VALUES (?,?,?,?,?,?)", (old, "p1", "secret", "redacted", "x", database.now()))
        con.execute("INSERT INTO chat_threads VALUES (?,?,?,?,?,?)", (f"thr_{old}", "p1", "t", old, database.now(), database.now()))
        con.execute("INSERT INTO chat_messages VALUES (?,?,?,?,?,?,?)", (f"thr_{old}", 1, "m", "assistant", "hi", old, database.now()))
    # a disabled merged agent, a merged agent with only a token limit, and a plain rename with a limit
    con.execute("INSERT INTO agent_settings VALUES ('doc_reviewer', 0, NULL, 'admin', 'Too many false alarms', ?)", (database.now(),))
    con.execute("INSERT INTO agent_settings VALUES ('gherkin_author', 1, 3000, 'admin', '', ?)", (database.now(),))
    con.execute("INSERT INTO agent_settings VALUES ('copilot', 1, 9000, 'admin', 'Cheaper', ?)", (database.now(),))
    con.execute("INSERT INTO agent_settings VALUES ('business_analyst', 1, 12000, 'admin', 'Own limit', ?)", (database.now(),))
    con.execute("INSERT INTO documents VALUES ('d1','p1','brd','D','draft',1,NULL,NULL,?,?)", (database.now(), database.now()))
    con.execute("INSERT INTO document_versions VALUES ('d1',1,'c','null',?,?,'','business_analyst@v2:' || ?,NULL,?)", (sha256("c"), "agent:business_analyst", SHA_A, database.now()))
    con.commit()
    con.close()
    for old in ("doc_reviewer", "gherkin_author", "copilot"):  # ledger entries naming old agents
        ledger.append("p1", f"agent:{old}", "agent.run", f"{old}@v2:{SHA_A}", {"agent": old})
    return path


def test_migration_moves_every_row_and_keeps_the_ledger_valid(old_db):
    ledger_before = sqlite3.connect(old_db).execute("SELECT * FROM ledger ORDER BY seq").fetchall()
    before = counts(old_db)
    assert ledger.verify("p1")["valid"] and before["ledger"] == 3

    database.migrate()
    assert sqlite3.connect(old_db).execute("PRAGMA user_version").fetchone()[0] == 6
    after = counts(old_db)
    assert after.pop("agent_settings") == 3 and before.pop("agent_settings") == 4, "two merged settings rows fold into their targets, with their content kept in the reason"
    assert after == before, "no other row is gained or lost"
    con = sqlite3.connect(old_db)
    # nothing is left under an old key, in any table that names an agent
    for table in ("prompts", "agent_calls", "tool_calls", "agent_settings", "evaluations", "chat_threads", "chat_messages", "guardrail_events"):
        column = "agent"
        left = con.execute(f"SELECT DISTINCT {column} FROM {table} WHERE {column} IN ({','.join('?' * len(EVERY_OLD))})", list(EVERY_OLD)).fetchall()
        assert left == [], (table, left)

    # the ledger is byte-for-byte what it was and still verifies
    assert con.execute("SELECT * FROM ledger ORDER BY seq").fetchall() == ledger_before
    assert ledger.verify("p1") == {"valid": True, "entries": 3, "broken_at": None}
    # immutable document versions keep their author and prompt reference, which match the ledger
    assert con.execute("SELECT author, prompt_ref FROM document_versions").fetchone() == ("agent:business_analyst", f"business_analyst@v2:{SHA_A}")

    # one-to-one renames keep version numbers, bodies, hashes, and the active version
    for old, new in ONE_TO_ONE.items():
        got = con.execute("SELECT version, body, sha256, active FROM prompts WHERE agent=? ORDER BY version", (new,)).fetchall()
        wanted = [(v, f"{old} body v{v}", sha256(f"{old} body v{v}"), int(v == 2)) for v in (1, 2)]
        if new in ("confidence-reviewer", "business-analyst"):
            assert got[:2] == wanted
        else:
            assert got == wanted
    assert con.execute("SELECT prompt_ref FROM agent_calls WHERE agent='project-copilot'").fetchone()[0] == f"project-copilot@v2:{SHA_A}"
    assert con.execute("SELECT prompt_ref FROM evaluations WHERE id='evl_copilot'").fetchone()[0] == f"project-copilot@v1:{SHA_A}"
    assert con.execute("SELECT agent FROM chat_threads WHERE id='thr_copilot'").fetchone()[0] == "project-copilot"

    # merged versions follow the target's own, with their bodies and hashes intact, and none is active
    for old, new in MERGED.items():
        moved = con.execute("SELECT version, body, sha256, active, note FROM prompts WHERE agent=? AND body LIKE ? ORDER BY version", (new, f"{old} body%")).fetchall()
        assert [(m[0], m[1], m[2], m[3]) for m in moved] == [(3, f"{old} body v1", sha256(f"{old} body v1"), 0), (4, f"{old} body v2", sha256(f"{old} body v2"), 0)]
        assert f"Moved from {old} v1" in moved[0][4]
        assert con.execute("SELECT COUNT(*) FROM prompts WHERE agent=? AND active=1", (new,)).fetchone()[0] == 1, "only the target's own active version stays active"
        assert con.execute("SELECT prompt_ref FROM agent_calls WHERE project_id='p1' AND prompt_ref LIKE ? AND agent=?", (f"{new}@v4:{SHA_A}", new)).fetchone(), "references follow the moved version"
        assert con.execute("SELECT COUNT(*) FROM evaluations WHERE prompt_ref=?", (f"{new}@v3:{SHA_A}",)).fetchone()[0] == 1

    # settings: a disable is never lost, the lower token limit wins, and the reason says where it came from
    reviewer = con.execute("SELECT enabled, max_tokens, updated_by, reason FROM agent_settings WHERE agent='confidence-reviewer'").fetchone()
    assert reviewer[0] == 0 and reviewer[2] == "migration 006" and "Merged from doc_reviewer" in reviewer[3] and "Too many false alarms" in reviewer[3] and "stays disabled" in reviewer[3]
    analyst = con.execute("SELECT enabled, max_tokens, reason FROM agent_settings WHERE agent='business-analyst'").fetchone()
    assert analyst[0] == 1 and analyst[1] == 3000 and "Own limit" in analyst[2] and "Merged from gherkin_author" in analyst[2] and "stays disabled" not in analyst[2]
    assert con.execute("SELECT enabled, max_tokens FROM agent_settings WHERE agent='project-copilot'").fetchone() == (1, 9000)
    assert con.execute("SELECT COUNT(*) FROM agent_settings").fetchone()[0] == 3
    con.close()


def test_upgraded_and_fresh_databases_end_with_the_files_active(old_db, tmp_path, monkeypatch):
    database.migrate()
    prompts.seed()
    for path in PROMPTS_DIR.glob("*.md"):
        assert prompts.active(path.stem)["sha256"] == sha256(path.read_text(encoding="utf-8").strip()), path.name
    assert prompts.active("business-analyst")["version"] == 5 and prompts.active("confidence-reviewer")["version"] == 5
    assert prompts.active("project-copilot")["version"] == 3, "a renamed agent whose file is new gets one new version after its history"
    # the merged agents' old text stays readable
    assert {h["body"] for h in prompts.history("confidence-reviewer")} >= {"doc_reviewer body v1", "doc_reviewer body v2"}

    fresh = tmp_path / "fresh.sqlite3"
    monkeypatch.setattr(database, "DB_PATH", fresh)
    database.migrate()
    prompts.seed()
    assert {p["agent"] for p in prompts.list_all()} == set(POLICIES)
    assert all(prompts.active(key)["version"] == 1 for key in POLICIES)


def test_migration_can_run_again_without_changes(old_db):
    database.migrate()
    snapshot = sqlite3.connect(old_db).execute("SELECT agent, version, sha256, active, note FROM prompts ORDER BY agent, version").fetchall()
    settings = sqlite3.connect(old_db).execute("SELECT * FROM agent_settings ORDER BY agent").fetchall()
    con = sqlite3.connect(old_db)
    con.executescript((database.MIGRATIONS / "006_agent_plugin_names.sql").read_text(encoding="utf-8"))
    con.close()
    after = sqlite3.connect(old_db)
    assert after.execute("SELECT agent, version, sha256, active, note FROM prompts ORDER BY agent, version").fetchall() == snapshot
    assert after.execute("SELECT * FROM agent_settings ORDER BY agent").fetchall() == settings
    assert ledger.verify("p1")["valid"]


def test_merged_agents_hold_no_more_than_their_old_selves():
    assert POLICIES["confidence-reviewer"].workflow_tools == frozenset() and POLICIES["confidence-reviewer"].chat_tools is None
    assert POLICIES["business-analyst"].workflow_tools == frozenset() and not POLICIES["business-analyst"].can_change_code
    assert next(iter(POLICIES)) == "project-copilot"
    assert not {"doc_reviewer", "gherkin_author"} & set(POLICIES)
