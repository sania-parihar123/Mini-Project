# 09 Graph and Routing
Status: agreed
Source: Part 3.3, Part 3.4, Part 3.5 [BASELINE]

## Purpose
Define the LangGraph workflow structure, state schema, conditional routing edges, retry limits, and deterministic state transitions.

## Requirements
- SPEC-09-01 The pipeline shall be structured as a LangGraph StateGraph operating on `ProcessFoundryState`.
- SPEC-09-02 Routing rules shall be written in explicit deterministic Python code, never delegated to an LLM.
- SPEC-09-03 The pipeline shall execute stages in order:
  `ingest` -> `evidence` -> `as_is` -> `rules` -> `gaps` -> `check_critical_gaps`:
  - If open critical questions exist -> pause with status `waiting_for_human`.
  - If no open critical questions -> `to_be` -> `automation` -> `requirements` -> `artifacts` -> `validate_traceability`.
- SPEC-09-04 Invalid schemas or traceability violations shall be subject to at most 2 repair attempts before marking state `needs_review` and halting. Indefinite loops are strictly prohibited.
- SPEC-09-05 Graph execution state shall be serialized to `runs.state_json` so it can be resumed after human interaction.

## Acceptance criteria
- AC-09-01 (covers SPEC-09-01/03) Given parsed documents, when graph execution begins, it progresses through evidence, As-Is, rules, and gap detection.
- AC-09-02 (covers SPEC-09-03/05) Given open critical questions, the graph halts at the `check_critical_gaps` router, sets run status to `waiting_for_human`, and saves checkpoint state.
- AC-09-03 (covers SPEC-09-04) Given persistent schema validation errors, after 2 repair retries the graph terminates gracefully with `needs_review`.

## Design notes
- Files: `app/graph/state.py`, `app/graph/routing.py`, `app/graph/build_graph.py`.
- State class: `ProcessFoundryState(TypedDict, total=False)`.

## Tests

Generated from the test suite, not written by hand: every test below cites
this spec's requirement ids in its docstring, and
`tests/test_spec_coverage.py::test_every_spec_id_has_a_covering_test` fails if
any requirement here loses its coverage.

- SPEC-09-01
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
- SPEC-09-02
  - `test_router_pauses_on_critical_conflicting_rules` (`tests/test_graph_routing.py`)
  - `test_router_pauses_on_critical_missing_actor` (`tests/test_graph_routing.py`)
  - `test_router_proceeds_when_critical_questions_resolved` (`tests/test_graph_routing.py`)
- SPEC-09-03
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
  - `test_router_proceeds_when_critical_questions_resolved` (`tests/test_graph_routing.py`)
- SPEC-09-04
  - `test_quality_repair_router_bounded_iterations` (`tests/test_graph_routing.py`)
- SPEC-09-05
  - `test_answering_does_not_create_a_second_run` (`tests/test_full_loop_e2e.py`)
  - `test_full_loop_upload_run_answer_approve_generates_every_document` (`tests/test_full_loop_e2e.py`)
  - `test_interrupted_runs_are_reconciled` (`tests/test_full_loop_e2e.py`)
  - `test_background_run_execution_and_cancellation` (`tests/test_new_features.py`)
