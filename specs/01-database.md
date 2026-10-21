# 01 Database
Status: agreed
Source: Part 8 (Database, Tables, Rules, Schema SQL) [BASELINE + EXTENSION + PROPOSED]

## Purpose
Define the persistent relational data model, constraints, table relationships, key-minting sequences, and query isolation ensuring strong project boundaries and traceable records.

## Requirements
- SPEC-01-01 Every project-owned table shall carry a `project_id` foreign key referencing `projects(id)` with cascade delete, and all application queries shall filter by `project_id`.
- SPEC-01-02 Primary keys shall be UUIDs. Readable entity keys (`EVD-nnn`, `BR-nnn`, `STEP-nnn`, `REQ-nnn`, `TEST-nnn`, `UAT-nnn`, `Q-nnn`, `FACT-nnn`) shall be unique per project (`UNIQUE(project_id, key)`).
- SPEC-01-03 Readable keys shall be safely minted atomically using the `project_counters` table.
- SPEC-01-04 Approval constraints shall be enforced: `business_rules`, `process_versions`, `requirements`, and `artifacts` cannot have `status = 'approved'` without a non-null `approved_by` user reference.
- SPEC-01-05 Clarification items shall enforce `UNIQUE (project_id, fingerprint)` to prevent duplicate questions for the same gap.
- SPEC-01-06 The database layer shall connect to PostgreSQL via `DATABASE_URL` (Supabase or local PostgreSQL) and provide a repository interface with an automated local SQLite fallback for isolated zero-setup testing.

## Acceptance criteria
- AC-01-01 (covers SPEC-01-01) Given records in project A and project B, when querying records for project A, then zero records belonging to project B are returned.
- AC-01-02 (covers SPEC-01-02/03) Given multiple concurrent entity inserts in project A, when readable keys are generated, then keys are formatted with entity prefix and zero-padded integer (e.g. `EVD-001`) and are strictly unique.
- AC-01-03 (covers SPEC-01-04) Given an attempt to set `status = 'approved'` on a requirement or rule with `approved_by = NULL`, then the database/validation layer rejects the operation with a constraint violation.
- AC-01-04 (covers SPEC-01-05) Given two identical planted conflicts triggering the same fingerprint, when clarification items are stored, then only one question is stored.

## Design notes
- Files: `schema.sql`, `app/repositories/base.py`, `app/repositories/database.py`, `app/repositories/projects.py`.
- Tables: 28 tables defined in `schema.sql`.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-01-01
  - `test_question_list_costs_one_query_regardless_of_question_count` (`tests/test_questions_endpoint.py`)
  - `test_the_audit_chain_is_continuous` (`tests/test_security_hardening.py`)
  - `test_the_audit_chain_locks_the_previous_event_on_postgres` (`tests/test_security_hardening.py`)
  - `test_postgres_audit_log_is_append_only` (`tests/test_spec_coverage.py`)
  - `test_batch_upload_is_closed_to_non_members` (`tests/test_uploads.py`)
- SPEC-01-02
  - `test_evidence_extraction_verbatim_quote_saved` (`tests/test_evidence.py`)
  - `test_conflicting_rules_preserved_as_separate_rows` (`tests/test_rules_gaps.py`)
  - `test_every_step_has_a_readable_key_and_evidence_link` (`tests/test_spec_coverage.py`)
  - `test_postgres_rejects_a_duplicate_readable_key_in_one_project` (`tests/test_spec_coverage.py`)
- SPEC-01-03
  - `test_evidence_extraction_verbatim_quote_saved` (`tests/test_evidence.py`)
  - `test_every_step_has_a_readable_key_and_evidence_link` (`tests/test_spec_coverage.py`)
- SPEC-01-04
  - `test_ai_can_never_set_approved` (`tests/test_security_hardening.py`)
  - `test_an_unapproved_draft_is_still_updated_in_place` (`tests/test_security_hardening.py`)
  - `test_regenerating_does_not_discard_an_approval` (`tests/test_security_hardening.py`)
  - `test_postgres_refuses_approved_without_an_approver` (`tests/test_spec_coverage.py`)
- SPEC-01-05
  - `test_a_second_run_on_an_unchanged_document_adds_no_rows` (`tests/test_full_loop_e2e.py`)
  - `test_fingerprints_are_stable_across_runs` (`tests/test_full_loop_e2e.py`)
  - `test_question_fingerprint_uniqueness` (`tests/test_rules_gaps.py`)
- SPEC-01-06
  - `test_pool_lifecycle_cleanup` (`tests/test_new_features.py`)
  - `test_sqlite_allowed_with_explicit_flag` (`tests/test_new_features.py`)
  - `test_sqlite_fallback_fails_fast_in_production` (`tests/test_new_features.py`)
  - `test_is_test_environment_detects_this_run` (`tests/test_test_isolation.py`)
  - `test_repository_is_in_sqlite_mode_with_a_temporary_path` (`tests/test_test_isolation.py`)
  - `test_settings_cannot_see_a_database_url_from_dotenv` (`tests/test_test_isolation.py`)
