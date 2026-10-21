# 07 Gap and Conflict Analysis
Status: agreed
Source: Part 3.1 (A5), Part 6 Step 9, Part 7.5, Part 7.12 [BASELINE + PROPOSED]

## Purpose
Deterministically detect ambiguities, missing actors, vague terms, and contradictory rules from evidence, creating structured clarification questions routed to specific project roles.

## Requirements
- SPEC-07-01 The system shall run deterministic checks across steps, rules, and evidence before any LLM gap pass:
  - Step with `actor = NULL` -> `missing_actor` question.
  - Two rules with conflicting values for the same topic/deadline -> `conflicting_rules` question.
  - Vague terms ("eligible", "appropriate", "as soon as possible") -> `ambiguous_term` question.
  - Step with unknowns or missing paths -> `missing_info` question.
- SPEC-07-02 Every clarification item shall have a unique readable key `Q-nnn` and a unique fingerprint `fingerprint` to ensure the same problem is never asked twice.
- SPEC-07-03 Clarification items shall link to their subjects (rules, steps, evidence) via `clarification_links`.
- SPEC-07-04 A `conflicting_rules` question shall link to BOTH conflicting rules and provide options for each source value plus "Other".
- SPEC-07-05 Each question shall be routed to the appropriate role:
  - Business rules, missing actors, policy ambiguities -> `process_owner`
  - Extraction/parsing issues, duplicate evidence -> `analyst`
  - Architecture/data model/tests -> `technical_reviewer`

## Acceptance criteria
- AC-07-01 (covers SPEC-07-01/04) Given two conflicting rules with dates "31 March" and "15 April", when gap analysis runs, then a question of kind `conflicting_rules` is created showing both quotes, sections, and filenames, with options `["31 March", "15 April", "Other"]`.
- AC-07-02 (covers SPEC-07-01/05) Given a step with `actor = NULL`, when gap analysis runs, then a `missing_actor` question is generated and assigned to `process_owner`.
- AC-07-03 (covers SPEC-07-02) Given a repeated analysis run over the same source data, when gap analysis runs again, then duplicate questions with the same fingerprint are ignored.

## Design notes
- Files: `app/agents/gaps.py`, `app/schemas/clarification.py`.
- Routing table: plain Python mapping function `route_question_to_role(kind: str) -> str`.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-07-01
  - `test_every_planted_defect_class_is_covered` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_conflicting_values_are_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_missing_piece_is_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_repeated_step_is_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_unnamed_actor_is_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_planted_vague_term_is_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_fixture_conflicting_dates_detected_by_gap_agent` (`tests/test_fixtures.py`)
  - `test_fixture_vague_term_detected_in_evidence` (`tests/test_fixtures.py`)
  - `test_an_ambiguous_term_question_is_created` (`tests/test_questions_endpoint.py`)
  - `test_list_project_questions_returns_200_with_evidence_linked_questions` (`tests/test_questions_endpoint.py`)
  - `test_waiting_for_me_returns_200_with_evidence_linked_questions` (`tests/test_questions_endpoint.py`)
  - `test_gap_detection_conflicting_dates` (`tests/test_rules_gaps.py`)
  - `test_gap_detection_missing_actor` (`tests/test_rules_gaps.py`)
  - `test_gap_detection_vague_terms` (`tests/test_rules_gaps.py`)
- SPEC-07-02
  - `test_no_extra_conflicts_are_invented` (`tests/test_fixture_defect_coverage.py`)
  - `test_a_second_run_on_an_unchanged_document_adds_no_rows` (`tests/test_full_loop_e2e.py`)
  - `test_fingerprints_are_stable_across_runs` (`tests/test_full_loop_e2e.py`)
  - `test_question_fingerprint_uniqueness` (`tests/test_rules_gaps.py`)
- SPEC-07-03
  - `test_conflicting_rules_question_shows_both_passages_with_letters` (`tests/test_questions_endpoint.py`)
  - `test_every_question_carries_the_context_brief_7_12_requires` (`tests/test_questions_endpoint.py`)
  - `test_list_project_questions_returns_200_with_evidence_linked_questions` (`tests/test_questions_endpoint.py`)
  - `test_the_evidence_quote_is_findable_in_the_response` (`tests/test_questions_endpoint.py`)
- SPEC-07-04
  - `test_an_ambiguous_term_question_is_created` (`tests/test_questions_endpoint.py`)
  - `test_conflicting_rules_question_shows_both_passages_with_letters` (`tests/test_questions_endpoint.py`)
  - `test_every_question_carries_the_context_brief_7_12_requires` (`tests/test_questions_endpoint.py`)
  - `test_list_project_questions_returns_200_with_evidence_linked_questions` (`tests/test_questions_endpoint.py`)
  - `test_gap_detection_conflicting_dates` (`tests/test_rules_gaps.py`)
- SPEC-07-05
  - `test_waiting_for_me_returns_200_with_evidence_linked_questions` (`tests/test_questions_endpoint.py`)
  - `test_gap_detection_missing_actor` (`tests/test_rules_gaps.py`)
