# 11 Traceability and Quality Validation
Status: agreed
Source: Part 3.1 (A13), Part 4.3, Part 8.2, Part 8.5 [BASELINE]

## Purpose
Validate relational integrity across the entire project graph, detecting dangling links, orphan requirements, tests without requirements, or ungrounded claims, and generating a traceable matrix.

## Requirements
- SPEC-11-01 The system shall compute a complete traceability graph linking:
  `Source Document` -> `Document Section` -> `Evidence Item` -> `Business Rule` -> `Requirement` -> `Process Step` -> `Test Case`.
- SPEC-11-02 The validator shall detect and report any requirement that lacks supporting evidence or rules.
- SPEC-11-03 The validator shall detect and report any test case that is not linked to a requirement.
- SPEC-11-04 The validator shall verify that all evidence quotes exist as exact substrings within their associated document sections (error count must be 0).
- SPEC-11-05 Traceability reports shall be queryable via API and renderable in the UI as an interactive matrix.

## Acceptance criteria
- AC-11-01 (covers SPEC-11-01) Given a valid project, the traceability query returns the full chain for each requirement.
- AC-11-02 (covers SPEC-11-02) Given a requirement inserted without supporting evidence or rule links, when the traceability validator runs, it reports the requirement key as an orphan requirement.
- AC-11-03 (covers SPEC-11-03) Given a test case with a missing or invalid requirement foreign key, the validator flags the defect.
- AC-11-04 (covers SPEC-11-04) Given all stored evidence records, the quote verification audit passes with 0 mismatches.

## Design notes
- Files: `app/agents/quality.py`, `app/api/traceability.py`, `app/services/validators.py`.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-11-01
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
  - `test_the_traceability_chain_links_source_to_test` (`tests/test_spec_coverage.py`)
  - `test_quote_audit_zero_mismatches_on_valid_evidence` (`tests/test_traceability.py`)
- SPEC-11-02
  - `test_orphan_requirement_detected` (`tests/test_traceability.py`)
- SPEC-11-03
  - `test_a_test_case_without_a_requirement_is_flagged` (`tests/test_spec_coverage.py`)
- SPEC-11-04
  - `test_quote_audit_zero_mismatches_on_valid_evidence` (`tests/test_traceability.py`)
- SPEC-11-05
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
  - `test_the_traceability_get_writes_nothing` (`tests/test_security_hardening.py`)
  - `test_quote_audit_zero_mismatches_on_valid_evidence` (`tests/test_traceability.py`)
