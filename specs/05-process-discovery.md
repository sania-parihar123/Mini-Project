# 05 Process Discovery (As-Is)
Status: agreed
Source: Part 3.1 (A3), Part 4.4, Part 6 Step 7, Part 8.3 [BASELINE + EXTENSION]

## Purpose
Synthesize verified evidence items into a sequential As-Is process model containing ordered steps, actors, handoffs, inputs, and outputs, explicitly preserving missing/unknown actors as `NULL` without guessing.

## Requirements
- SPEC-05-01 The system shall synthesize verified evidence into an As-Is process model consisting of ordered `process_steps` linked to `process_versions`.
- SPEC-05-02 If a source sentence describes a step but does NOT name an actor (e.g. "The form is verified."), the system shall store `actor = NULL` and add `"actor not stated"` to `unknowns`. The system shall never guess or fabricate an actor.
- SPEC-05-03 Each step shall be assigned a project-unique readable key `STEP-nnn` and linked to its supporting `evidence_items` via `step_evidence`.
- SPEC-05-04 Process steps shall capture `sequence`, `name`, `step_type`, `inputs`, `outputs`, and `unknowns`.

## Acceptance criteria
- AC-05-01 (covers SPEC-05-02) Given source evidence stating "The form is verified.", when As-Is process discovery runs, then the created step has `actor = None` and `unknowns` contains "actor not stated".
- AC-05-02 (covers SPEC-05-01/03) Given extracted steps, each step has a valid `STEP-nnn` key and at least one supporting link in `step_evidence`.

## Design notes
- Files: `app/agents/discovery.py`, `app/schemas/process.py`.
- Schema: `ProcessStepSchema`, `AsIsProcessSchema`.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-05-01
  - `test_as_is_steps_are_stored_against_a_process_version` (`tests/test_spec_coverage.py`)
- SPEC-05-02
  - `test_planted_unnamed_actor_is_found` (`tests/test_fixture_defect_coverage.py`)
  - `test_gap_detection_missing_actor` (`tests/test_rules_gaps.py`)
- SPEC-05-03
  - `test_every_step_has_a_readable_key_and_evidence_link` (`tests/test_spec_coverage.py`)
- SPEC-05-04
  - `test_steps_capture_sequence_type_inputs_outputs_and_unknowns` (`tests/test_spec_coverage.py`)
