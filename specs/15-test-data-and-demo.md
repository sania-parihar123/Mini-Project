# 15 Test Data and Demo Scripts
Status: agreed
Source: Part 7.10, Part 9.1 [EXTENSION + PROPOSED]

## Purpose
Provide synthetic multi-process test fixtures with planted defects (two different college processes: scholarships and hostel allotment), seed scripts for demo accounts, and automated end-to-end verification.

## Requirements
- SPEC-15-01 The system shall include at least two synthetic test fixture documents from two different processes in `tests/fixtures/`:
  - `scholarship_sop.txt` (Scholarship application process)
  - `hostel_allotment_policy.txt` (Hostel room allotment process)
- SPEC-15-02 Each test document shall contain deliberately planted defects:
  1. Two conflicting values for the same rule (e.g. conflicting submission deadlines or fee amounts).
  2. One step with an unnamed actor (e.g. "The form is verified" or "The room key is issued").
  3. One vague term ("eligible students", "appropriate authority", "as soon as possible").
  4. One repeated step.
  5. Clear, unambiguous facts that must NOT be flagged.
- SPEC-15-03 The test documents shall have an accompanying manifest/comment file recording the planted defects for automated test assertions.
- SPEC-15-04 A demo seeding script `scripts/seed_demo.py` shall provision standard demo users:
  - `aditi@example.com` (password: `Process123!`, Analyst)
  - `rao@example.com` (password: `Process123!`, Process Owner)
  - `anil@example.com` (password: `Process123!`, Technical Reviewer)
  and an initial demo project with Aditi as creator.

## Acceptance criteria
- AC-15-01 (covers SPEC-15-01/02) Given both test fixtures, when the discovery and gap analysis pipelines run on each, the planted conflicts, unnamed actors, and vague terms are detected with zero process-specific code branches.
- AC-15-02 (covers SPEC-15-04) Given `scripts/seed_demo.py`, when run, all demo users and initial project exist in the database and can sign in.

## Design notes
- Files: `tests/fixtures/scholarship_sop.txt`, `tests/fixtures/hostel_allotment_policy.txt`, `tests/fixtures/manifest.json`, `scripts/seed_demo.py`.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-15-01
  - `test_every_planted_defect_class_is_covered` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_conflicting_values_are_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_missing_piece_is_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_repeated_step_is_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_unnamed_actor_is_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_vague_term_is_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_fixture_parsing_detects_all_sections` (`tests/test_fixtures.py`)
- SPEC-15-02
  - `test_every_planted_defect_class_is_covered` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_conflicting_values_are_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_missing_piece_is_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_repeated_step_is_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_unnamed_actor_is_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_vague_term_is_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_fixture_conflicting_dates_detected_by_gap_agent` (`tests/test_fixtures.py`)
  - `test_fixture_vague_term_detected_in_evidence` (`tests/test_fixtures.py`)
- SPEC-15-03
  - `test_fixture_document_sha256_checksum_is_deterministic` (`tests/test_fixtures.py`)
- SPEC-15-04
  - `test_the_demo_seed_script_matches_the_brief` (`tests/test_spec_coverage.py`)
