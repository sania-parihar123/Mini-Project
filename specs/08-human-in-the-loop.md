# 08 Human-in-the-Loop Clarification
Status: agreed
Source: Part 3.6, Part 7.1, Part 7.2, Part 7.8, Part 7.11 [BASELINE + PROPOSED]

## Purpose
Pause downstream generation when critical questions are open, present contextual source excerpts to authorized roles, record human answers with full audit history, create verified facts, and resume execution.

## Requirements
- SPEC-08-01 When critical questions (`conflicting_rules`, `missing_actor`) exist and are `open`, the run state shall transition to `waiting_for_human` and halt downstream artifact generation.
- SPEC-08-02 An authorized user whose active project role matches the question's `assigned_role` can submit an answer or mark the question `unknown`.
- SPEC-08-03 Submitting an answer shall:
  1. Record the answer in `clarification_answers` (with user, role, timestamp).
  2. Update `clarification_items` status to `answered`.
  3. Create a record in `verified_facts` with readable key `FACT-nnn`.
  4. For conflicting rules, mark the selected rule confirmed and the unselected rule `superseded` with reason.
  5. For missing actors, update the corresponding `process_steps.actor` and remove "actor not stated" from `unknowns`.
- SPEC-08-04 "Mark unknown" shall set `clarification_items.status = 'unknown'`, allowing the run to resume while keeping dependent downstream requirements flagged as "Needs clarification".
- SPEC-08-05 When all critical questions are resolved or marked unknown, the paused run shall resume and rebuild affected downstream models.

## Acceptance criteria
- AC-08-01 (covers SPEC-08-01) Given a run with an open `conflicting_rules` question, when checked, the run status is `waiting_for_human` and final requirements are not generated.
- AC-08-02 (covers SPEC-08-02/03) Given an open deadline question assigned to `process_owner`, when a Process Owner answers "31 March", then a `verified_facts` row is created, the chosen rule is updated, the superseded rule is marked `superseded`, and the question is marked `answered`.
- AC-08-03 (covers SPEC-08-02) Given an Analyst attempting to answer a question assigned to `process_owner`, then the operation is refused with HTTP 403 Forbidden.

## Design notes
- Files: `app/agents/hitl.py`, `app/api/questions.py`, `app/repositories/clarification.py`.
- History preserved: re-answering updates existing record as `superseded = TRUE` and inserts a new answer.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-08-01
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
  - `test_router_pauses_on_critical_conflicting_rules` (`tests/test_graph_routing.py`)
  - `test_router_pauses_on_critical_missing_actor` (`tests/test_graph_routing.py`)
- SPEC-08-02
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
- SPEC-08-03
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
- SPEC-08-04
  - `test_mark_unknown_unblocks_the_run` (`tests/test_full_loop_e2e.py`)
- SPEC-08-05
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
