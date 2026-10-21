# 06 Business Rules
Status: agreed
Source: Part 3.1 (A4), Part 4.4, Part 6 Step 8, Part 8.3 [BASELINE + EXTENSION]

## Purpose
Extract candidate business rules per section with structured conditions, exceptions, approvals, and outcomes, storing conflicting rules as separate distinct records rather than auto-resolving.

## Requirements
- SPEC-06-01 The system shall extract business rules per document section, ensuring each rule has a clear description, structured condition, and outcome.
- SPEC-06-02 Conflicting rules (such as two conflicting deadlines or eligibility criteria across sections or documents) shall be stored as TWO separate records in `business_rules`, both marked `status = 'needs_review'`.
- SPEC-06-03 The system shall never silently resolve or merge conflicting rules using timestamps, document order, or heuristics.
- SPEC-06-04 Each rule shall have a unique readable key `BR-nnn` minted via `project_counters` and linked to supporting evidence in `rule_evidence`.

## Acceptance criteria
- AC-06-01 (covers SPEC-06-02/03) Given two document sections stating "Deadline is 31 March" and "Deadline is 15 April", when rule extraction runs, then two distinct `business_rules` rows (`BR-001` and `BR-002`) are stored, each linked to its respective quote.
- AC-06-02 (covers SPEC-06-04) Given extracted rules, each rule record contains valid `condition_json` with condition, outcome, and exceptions fields.

## Design notes
- Files: `app/agents/rules.py`, `app/schemas/rules.py`.
- Rule status initial value: `needs_review`.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-06-01
  - `test_gap_detection_conflicting_dates` (`tests/test_rules_gaps.py`)
- SPEC-06-02
  - `test_planted_conflicting_values_are_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_fixture_conflicting_dates_detected_by_gap_agent` (`tests/test_fixtures.py`)
  - `test_conflicting_rules_preserved_as_separate_rows` (`tests/test_rules_gaps.py`)
- SPEC-06-03
  - `test_clear_facts_are_not_flagged` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_conflicting_values_are_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_fixture_conflicting_dates_detected_by_gap_agent` (`tests/test_fixtures.py`)
  - `test_gap_detection_conflicting_dates` (`tests/test_rules_gaps.py`)
- SPEC-06-04
  - `test_conflicting_rules_preserved_as_separate_rows` (`tests/test_rules_gaps.py`)
  - `test_rules_are_never_linked_to_unrelated_evidence` (`tests/test_security_hardening.py`)
