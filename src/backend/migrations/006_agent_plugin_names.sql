-- Agents take the agentic-qe plugin names (hyphenated keys). Stored history moves to the new keys and nothing is deleted.
-- doc_reviewer joins confidence-reviewer and gherkin_author joins business-analyst. Their old prompt versions are kept on the
-- target, numbered after the target's own versions, so the (agent, version) key never collides and every body and hash stays readable.
-- NOT touched, on purpose: ledger (hash-chained, rewriting it would break verification), document_versions (immutable records whose
-- author and prompt_ref match the ledger), run_events, runs.state and approvals.payload (history as it happened).
-- Safe to run again: every statement matches only rows still under an old key.
BEGIN;
DROP TABLE IF EXISTS temp._ren;
DROP TABLE IF EXISTS temp._fold;
CREATE TEMP TABLE _ren (old TEXT PRIMARY KEY, new TEXT NOT NULL, merged INTEGER NOT NULL, off INTEGER NOT NULL DEFAULT 0);
INSERT INTO _ren (old, new, merged) VALUES
  ('repo_analyst', 'repo-intelligence-analyst', 0), ('requirements_analyst', 'requirements-analyst', 0),
  ('test_architect', 'principal-test-architect', 0), ('test_designer', 'test-design-architect', 0),
  ('test_automation', 'test-automation-engineer', 0), ('defect_diagnostician', 'defect-diagnostician', 0),
  ('confidence_reviewer', 'confidence-reviewer', 0), ('business_analyst', 'business-analyst', 0),
  ('bug_reviewer', 'bug-reviewer', 0), ('feature_engineer', 'feature-engineer', 0), ('copilot', 'project-copilot', 0),
  ('doc_reviewer', 'confidence-reviewer', 1), ('gherkin_author', 'business-analyst', 1);

-- prompts, one agent per old key. A one-to-one rename keeps version numbers unless the new key already has versions.
UPDATE _ren SET off = COALESCE((SELECT MAX(version) FROM prompts WHERE agent = _ren.new), 0) WHERE merged = 0;
UPDATE prompts SET
  version = version + (SELECT off FROM _ren WHERE old = prompts.agent),
  active = CASE WHEN (SELECT off FROM _ren WHERE old = prompts.agent) > 0 THEN 0 ELSE active END,
  note = CASE WHEN (SELECT off FROM _ren WHERE old = prompts.agent) > 0 THEN 'Moved from ' || agent || ' v' || version || '. ' || note ELSE note END,
  agent = (SELECT new FROM _ren WHERE old = prompts.agent)
WHERE agent IN (SELECT old FROM _ren WHERE merged = 0);
-- merged agents: versions go after the target's own and none stays active, so the merged prompt file seeds the next active version
UPDATE _ren SET off = COALESCE((SELECT MAX(version) FROM prompts WHERE agent = _ren.new), 0) WHERE merged = 1;
UPDATE prompts SET
  version = version + (SELECT off FROM _ren WHERE old = prompts.agent),
  active = 0,
  note = 'Moved from ' || agent || ' v' || version || ' when the agents were merged. ' || note,
  agent = (SELECT new FROM _ren WHERE old = prompts.agent)
WHERE agent IN (SELECT old FROM _ren WHERE merged = 1);

-- agent_settings: a one-to-one rename first
UPDATE OR IGNORE agent_settings SET agent = (SELECT new FROM _ren WHERE old = agent_settings.agent)
WHERE agent IN (SELECT old FROM _ren WHERE merged = 0);
-- a merged agent's restrictive setting folds into the target: disabled stays disabled, the lower token limit wins, and the reason says so
CREATE TEMP TABLE _fold AS
  SELECT r.new AS agent, r.old AS old, s.enabled AS enabled, s.max_tokens AS max_tokens, s.updated_by AS updated_by, s.reason AS reason, s.updated_at AS updated_at
  FROM agent_settings s JOIN _ren r ON r.old = s.agent WHERE r.merged = 1 AND (s.enabled = 0 OR s.max_tokens IS NOT NULL);
UPDATE agent_settings SET
  enabled = MIN(enabled, (SELECT f.enabled FROM _fold f WHERE f.agent = agent_settings.agent)),
  max_tokens = CASE WHEN (SELECT f.max_tokens FROM _fold f WHERE f.agent = agent_settings.agent) IS NULL THEN max_tokens
                    WHEN max_tokens IS NULL THEN (SELECT f.max_tokens FROM _fold f WHERE f.agent = agent_settings.agent)
                    ELSE MIN(max_tokens, (SELECT f.max_tokens FROM _fold f WHERE f.agent = agent_settings.agent)) END,
  reason = (CASE WHEN reason = '' THEN '' ELSE reason || ' | ' END) || (SELECT 'Merged from ' || f.old || ' (enabled ' || f.enabled || ', token limit ' || COALESCE(f.max_tokens, 'none') || ', set by ' || f.updated_by || ' at ' || f.updated_at || CASE WHEN f.reason = '' THEN '' ELSE ': ' || f.reason END || '). ' || CASE WHEN f.enabled = 0 THEN 'It stays disabled here until someone enables this agent.' ELSE '' END FROM _fold f WHERE f.agent = agent_settings.agent),
  updated_by = 'migration 006',
  updated_at = strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')
WHERE agent IN (SELECT agent FROM _fold);
INSERT OR IGNORE INTO agent_settings (agent, enabled, max_tokens, updated_by, reason, updated_at)
  SELECT agent, enabled, max_tokens, 'migration 006',
    'Merged from ' || old || ' (enabled ' || enabled || ', token limit ' || COALESCE(max_tokens, 'none') || ', set by ' || updated_by || ' at ' || updated_at || CASE WHEN reason = '' THEN '' ELSE ': ' || reason END || '). ' || CASE WHEN enabled = 0 THEN 'It stays disabled here until someone enables this agent.' ELSE '' END,
    strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')
  FROM _fold;
DELETE FROM agent_settings WHERE agent IN (SELECT old FROM _ren WHERE merged = 1);

-- telemetry that carries a prompt reference (agent@vN:hash): the reference follows the moved version
UPDATE agent_calls SET
  prompt_ref = CASE WHEN substr(prompt_ref, 1, length(agent) + 2) = agent || '@v' AND instr(substr(prompt_ref, length(agent) + 3), ':') > 0
    THEN (SELECT new FROM _ren WHERE old = agent_calls.agent) || '@v'
      || (CAST(substr(prompt_ref, length(agent) + 3, instr(substr(prompt_ref, length(agent) + 3), ':') - 1) AS INTEGER) + (SELECT off FROM _ren WHERE old = agent_calls.agent))
      || substr(prompt_ref, length(agent) + 2 + instr(substr(prompt_ref, length(agent) + 3), ':'))
    ELSE prompt_ref END,
  agent = (SELECT new FROM _ren WHERE old = agent_calls.agent)
WHERE agent IN (SELECT old FROM _ren);
UPDATE evaluations SET
  prompt_ref = CASE WHEN substr(prompt_ref, 1, length(agent) + 2) = agent || '@v' AND instr(substr(prompt_ref, length(agent) + 3), ':') > 0
    THEN (SELECT new FROM _ren WHERE old = evaluations.agent) || '@v'
      || (CAST(substr(prompt_ref, length(agent) + 3, instr(substr(prompt_ref, length(agent) + 3), ':') - 1) AS INTEGER) + (SELECT off FROM _ren WHERE old = evaluations.agent))
      || substr(prompt_ref, length(agent) + 2 + instr(substr(prompt_ref, length(agent) + 3), ':'))
    ELSE prompt_ref END,
  agent = (SELECT new FROM _ren WHERE old = evaluations.agent)
WHERE agent IN (SELECT old FROM _ren);

-- tables that only name the agent
UPDATE tool_calls SET agent = (SELECT new FROM _ren WHERE old = tool_calls.agent) WHERE agent IN (SELECT old FROM _ren);
UPDATE guardrail_events SET agent = (SELECT new FROM _ren WHERE old = guardrail_events.agent) WHERE agent IN (SELECT old FROM _ren);
UPDATE chat_threads SET agent = (SELECT new FROM _ren WHERE old = chat_threads.agent) WHERE agent IN (SELECT old FROM _ren);
UPDATE chat_messages SET agent = (SELECT new FROM _ren WHERE old = chat_messages.agent) WHERE agent IN (SELECT old FROM _ren);

DROP TABLE temp._fold;
DROP TABLE temp._ren;
COMMIT;
